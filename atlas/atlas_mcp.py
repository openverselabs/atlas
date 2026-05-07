import os
import json
import asyncio
import threading
from typing import Dict, Any, List
# Try importing mcp, if it's not installed yet it might fail, so we wrap it
try:
    from mcp import StdioServerParameters, ClientSession
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
except ImportError:
    StdioServerParameters = None
    ClientSession = None
    stdio_client = None
    sse_client = None

class AtlasMCPWrapper:
    def __init__(self, config_path: str = "~/Atlas/mcp_servers.json"):
        self.config_path = os.path.expanduser(config_path)
        self.servers: Dict[str, Any] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Any]] = {}  # Map of server name to list of tools
        self._loop = None
        self._thread = None
        self._ready_event = threading.Event()
        self._mcp_installed = stdio_client is not None
        
    def is_available(self):
        return self._mcp_installed

    def start(self):
        """Start the background asyncio loop and load servers."""
        if not self._mcp_installed:
            return
            
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, args=(self._loop,), daemon=True)
        self._thread.start()
        
        # Load the JSON config
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    self.servers = data.get("mcpServers", {})
                except Exception as e:
                    print(f"Error parsing {self.config_path}: {e}")

        # Async initialize servers
        asyncio.run_coroutine_threadsafe(self._init_servers(), self._loop)
        
    def _run_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _init_servers(self):
        for name, config in self.servers.items():
            self._loop.create_task(self._server_worker(name, config))
            
        # Give them some time to establish
        self._loop.call_later(2.0, self._ready_event.set)

    async def _server_worker(self, name, config):
        cmd = config.get("command")
        url = config.get("url")
        
        try:
            if url:
                # Check if specific timeout is requested in config (expected in seconds or ms)
                cfg_timeout = config.get("timeout", 60 * 60 * 24) # 24 hr default
                if isinstance(cfg_timeout, (int, float)):
                    if cfg_timeout > 1000:  # likely ms
                        read_timeout = float(cfg_timeout) / 1000.0
                    else:
                        read_timeout = float(cfg_timeout)
                else:
                    read_timeout = 60.0 * 60.0 * 24.0
                    
                async with sse_client(url, timeout=5.0, sse_read_timeout=read_timeout) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.sessions[name] = session
                        result = await session.list_tools()
                        self.tools[name] = result.tools
                        
                        # Keep context open
                        while True:
                            await asyncio.sleep(3600)
            else:
                args = config.get("args", [])
                env = config.get("env", None)
                if env:
                    current_env = os.environ.copy()
                    current_env.update(env)
                    env = current_env
                    
                server_params = StdioServerParameters(command=cmd, args=args, env=env)
                
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.sessions[name] = session
                        result = await session.list_tools()
                        self.tools[name] = result.tools
                        
                        # Keep context open
                        while True:
                            await asyncio.sleep(3600)
        except Exception as e:
            err_msg = f"\n[MCP Error] Failed to initialize server '{name}': {e}"
            if hasattr(e, 'exceptions'):
                for sub_e in e.exceptions:
                    err_msg += f"\n  -> {sub_e}"
                    if hasattr(sub_e, '__cause__') and sub_e.__cause__:
                        err_msg += f"\n     Cause: {sub_e.__cause__}"
            
            # Silence common connection/timeout errors to avoid terminal clutter
            silence_keywords = ["timeout", "readtimeout", "connecterror", "connection attempts failed", "taskgroup", "burp", "connection"]
            if any(kw in err_msg.lower() for kw in silence_keywords):
                return

            print(err_msg)

    def get_loaded_servers(self):
        """Returns a list of loaded server names and their tools count synchronously."""
        out = []
        for name in self.servers.keys():
            if name in self.tools:
                out.append(f"{name} (Status: Connected, Tools: {len(self.tools[name])})")
            else:
                out.append(f"{name} (Status: Failed/Connecting)")
        return out

    def get_all_tools_sync(self):
        """Returns a combined list of tools compatible with GenAI definition."""
        self._ready_event.wait(timeout=2.0) # Wait up to 2 seconds for initial connection
        all_tools = []
        for name, tools_list in self.tools.items():
            for t in tools_list:
                all_tools.append({
                    "server": name,
                    "name": t.name,
                    "description": f"[{name}] {t.description}",
                    "inputSchema": t.inputSchema
                })
        return all_tools

    def call_tool_sync(self, name: str, arguments: dict):
        """Synchronously dispatch a tool call to the correct server."""
        # Find which server has this tool
        target_server = None
        for srv, tools_list in self.tools.items():
            for t in tools_list:
                if t.name == name:
                    target_server = srv
                    break
            if target_server:
                break
                
        if not target_server:
            return f"Error: Tool '{name}' not found on any MCP server."
            
        session = self.sessions.get(target_server)
        if not session:
            return f"Error: Session for MCP server '{target_server}' is not active."
            
        # Dispatch async call using threadsafe
        future = asyncio.run_coroutine_threadsafe(
            session.call_tool(name, arguments), 
            self._loop
        )
        try:
            # Wait for execution result
            result = future.result(timeout=60.0) 
            text_contents = []
            if getattr(result, "content", None):
                for c in result.content:
                    if getattr(c, "type", None) == "text":
                        text_contents.append(c.text)
            return "\n".join(text_contents)
        except Exception as e:
            return f"Error executing '{name}' on MCP server '{target_server}': {e}"
