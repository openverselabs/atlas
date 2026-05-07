import os
import sys
import subprocess
import json
import argparse
import re
import time
import threading
from dotenv import load_dotenv
import warnings
import logging

# Suppress third-party warnings and noisy logs
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

from google import genai
from google.genai import types
from ollamafreeapi import OllamaFreeAPI
from atlas_mcp import AtlasMCPWrapper

try:
    from colorama import init as colorama_init, Fore, Back, Style
    colorama_init(autoreset=True)
except Exception:
    class _F:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class _B:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class _S:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""
    Fore, Back, Style = _F(), _B(), _S()
    def colorama_init(autoreset=True): pass

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.shortcuts import confirm
from prompt_toolkit.document import Document

class FileCompleter(Completer):
    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        
        # Slash Command completion
        if text.startswith('/'):
            if ' ' in text:
                # Sub-command completion
                parts = text.split(' ')
                cmd = parts[0].lower()
                if cmd == '/prompt':
                    sub_text = parts[1].lower()
                    prompt_types = ['pentest', 'ctf', 'vuln-research']
                    for p in prompt_types:
                        if p.startswith(sub_text):
                            yield Completion(p, start_position=-len(sub_text))
                return

            cmd_text = text.split(' ')[0].lower()
            commands = ['/help', '/mcp', '/clear', '/prompt']
            for cmd in commands:
                if cmd.startswith(cmd_text):
                    yield Completion(cmd, start_position=-len(cmd_text))
            return
            
        # Check if we are typing a file path starting with @
        if '@' in text:
            # Find the last @ position
            at_index = text.rfind('@')
            # content after @
            path_input = text[at_index+1:]
            
            # If there is a space after @, we assume it's not a file path anymore unless it's escaped (simplified)
            if ' ' in path_input:
                return

            dirname = os.path.dirname(path_input)
            basename = os.path.basename(path_input)
            
            search_dir = dirname if dirname else '.'
            
            if not os.path.isdir(search_dir):
                return

            try:
                for name in os.listdir(search_dir):
                    if name.startswith(basename):
                        full_path = os.path.join(dirname, name) if dirname else name
                        if os.path.isdir(os.path.join(search_dir, name)):
                            yield Completion(name + '/', start_position=-len(basename))
                        else:
                            yield Completion(name, start_position=-len(basename))
            except OSError:
                pass

PALETTE = {

    "accent": Fore.CYAN + Style.BRIGHT,
    "muted": Fore.WHITE + Style.DIM,
    "success": Fore.GREEN + Style.BRIGHT,
    "placeholder": Fore.BLACK + Style.DIM,
    "error": Fore.RED + Style.BRIGHT,
    "command": Fore.YELLOW + Style.NORMAL,
    "banner_bg": Back.MAGENTA,
    "user_input": Fore.MAGENTA + Style.BRIGHT,
    "ai_response": Fore.CYAN + Style.NORMAL,
    "tool_call": Fore.YELLOW + Style.DIM,
    "tool_output": Fore.BLUE + Style.BRIGHT,
    "reset": Style.RESET_ALL
}

def get_palette(prompt_type: str = None):
    """Return appropriate palette based on the prompt type"""
    if prompt_type == "ctf":
        return {
            "accent": Fore.GREEN + Style.BRIGHT,
            "muted": Fore.GREEN + Style.DIM,
            "success": Fore.GREEN + Style.BRIGHT,
            "placeholder": Fore.BLACK + Style.DIM,
            "error": Fore.RED + Style.BRIGHT,
            "command": Fore.GREEN + Style.NORMAL,
            "banner_bg": Back.GREEN,
            "user_input": Fore.GREEN + Style.BRIGHT,
            "ai_response": Fore.GREEN + Style.NORMAL,
            "tool_call": Fore.GREEN + Style.DIM,
            "tool_output": Fore.GREEN + Style.BRIGHT,
            "reset": Style.RESET_ALL
        }
    elif prompt_type == "vuln-research":
        return {
            "accent": Fore.YELLOW + Style.BRIGHT,
            "muted": Fore.YELLOW + Style.DIM,
            "success": Fore.YELLOW + Style.BRIGHT,
            "placeholder": Fore.BLACK + Style.DIM,
            "error": Fore.RED + Style.BRIGHT,
            "command": Fore.YELLOW + Style.NORMAL,
            "banner_bg": Back.YELLOW,
            "user_input": Fore.YELLOW + Style.BRIGHT,
            "ai_response": Fore.YELLOW + Style.NORMAL,
            "tool_call": Fore.YELLOW + Style.DIM,
            "tool_output": Fore.YELLOW + Style.BRIGHT,
            "reset": Style.RESET_ALL
        }
    
    # Default (pentest)
    return {
        "accent": Fore.CYAN + Style.BRIGHT,
        "muted": Fore.WHITE + Style.DIM,
        "success": Fore.GREEN + Style.BRIGHT,
        "placeholder": Fore.BLACK + Style.DIM,
        "error": Fore.RED + Style.BRIGHT,
        "command": Fore.YELLOW + Style.NORMAL,
        "banner_bg": Back.MAGENTA,
        "user_input": Fore.MAGENTA + Style.BRIGHT,
        "ai_response": Fore.CYAN + Style.NORMAL,
        "tool_call": Fore.YELLOW + Style.DIM,
        "tool_output": Fore.BLUE + Style.BRIGHT,
        "reset": Style.RESET_ALL
    }


dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)


def get_yes_no_input(message: str) -> bool:
    """Get yes/no input using prompt_toolkit with proper color support"""
    try:
        from prompt_toolkit.formatted_text import ANSI
        colored_message = ANSI(message)
        return confirm(colored_message)
    except ImportError:
        return input(message).strip().lower() in ['y', 'yes']


def get_text_input(prompt_text: str) -> str:
    """Get text input using prompt_toolkit with proper color support"""
    try:
        from prompt_toolkit.formatted_text import ANSI
        colored_prompt = ANSI(prompt_text)
        return prompt(colored_prompt).strip()
    except ImportError:
        return input(prompt_text).strip()


def ensure_env_file():
    # Use path relative to this script's directory
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(env_path):
        print(PALETTE["accent"] + f"\nCreating .env file at: {env_path}" + PALETTE["reset"])
        with open(env_path, 'w') as f:
            f.write("# Atlas AI Configuration File\n")
            f.write("# Add your API keys below\n")
            f.write("# GOOGLE_API_KEY=your_google_api_key_here\n")
            f.write("# OPENAI_API_KEY=your_openai_api_key_here\n")
            f.write("# ANTHROPIC_API_KEY=your_anthropic_api_key_here\n")
            f.write("# GROQ_API_KEY=your_groq_api_key_here\n")
            f.write("# MISTRAL_API_KEY=your_mistral_api_key_here\n")
            f.write("# TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here\n")
        print(PALETTE["success"] + f"Empty .env file created. Please add your API keys to {env_path}" + PALETTE["reset"])

    return env_path


def select_ai_model(prompt_type: str = None, model_override: str = None):

    ensure_env_file()

    palette = get_palette(prompt_type)

    env_path = ensure_env_file()
    load_dotenv(env_path, override=True)

    if model_override:
        print(palette["accent"] + f"\nUsing model override: {model_override}" + palette["reset"])

    direct_model_map = {
        "gemini-2.5-flash": ("gemini", os.getenv("GOOGLE_API_KEY"), "gemini-2.5-flash"),
        "gemini-2.0-flash": ("gemini", os.getenv("GOOGLE_API_KEY"), "gemini-2.0-flash"),
        "gemini-1.5-pro": ("gemini", os.getenv("GOOGLE_API_KEY"), "gemini-1.5-pro"),
        "gemini-1.5-pro-exp": ("gemini", os.getenv("GOOGLE_API_KEY"), "gemini-1.5-pro-exp"),
        "gemini-1.0-pro": ("gemini", os.getenv("GOOGLE_API_KEY"), "gemini-1.0-pro"),
        "gpt-4": ("openai", os.getenv("OPENAI_API_KEY"), "gpt-4"),
        "gpt-4-turbo": ("openai", os.getenv("OPENAI_API_KEY"), "gpt-4-turbo"),
        "gpt-4o": ("openai", os.getenv("OPENAI_API_KEY"), "gpt-4o"),
        "gpt-4o-mini": ("openai", os.getenv("OPENAI_API_KEY"), "gpt-4o-mini"),
        "gpt-3.5-turbo": ("openai", os.getenv("OPENAI_API_KEY"), "gpt-3.5-turbo"),
        "claude-3-sonnet": ("anthropic", os.getenv("ANTHROPIC_API_KEY"), "claude-3-sonnet"),
        "claude-3-opus": ("anthropic", os.getenv("ANTHROPIC_API_KEY"), "claude-3-opus"),
        "claude-3-haiku": ("anthropic", os.getenv("ANTHROPIC_API_KEY"), "claude-3-haiku"),
        "claude-2.1": ("anthropic", os.getenv("ANTHROPIC_API_KEY"), "claude-2.1"),
        "llama3-70b-8192": ("groq", os.getenv("GROQ_API_KEY"), "llama3-70b-8192"),
        "llama-3.1-8b": ("groq", os.getenv("GROQ_API_KEY"), "llama-3.1-8b"),
        "llama-3.1-70b": ("groq", os.getenv("GROQ_API_KEY"), "llama-3.1-70b"),
        "mixtral-8x7b": ("groq", os.getenv("GROQ_API_KEY"), "mixtral-8x7b"),
        "gemma-7b": ("groq", os.getenv("GROQ_API_KEY"), "gemma-7b"),
        "mistral-small-latest": ("mistral", os.getenv("MISTRAL_API_KEY"), "mistral-small-latest"),
        "mistral-large": ("mistral", os.getenv("MISTRAL_API_KEY"), "mistral-large"),
        "mistral-medium": ("mistral", os.getenv("MISTRAL_API_KEY"), "mistral-medium"),
        "mistral-nemo": ("mistral", os.getenv("MISTRAL_API_KEY"), "mistral-nemo"),
        # OllamaFreeAPI Models
        "llama3.2:3b": ("ollama", None, "llama3.2:3b"),
        "deepseek-r1:latest": ("ollama", None, "deepseek-r1:latest"),
        "gpt-oss:20b": ("ollama", None, "gpt-oss:20b"),
        "mistral:latest": ("ollama", None, "mistral:latest"),
        "mistral-nemo:custom": ("ollama", None, "mistral-nemo:custom"),
        "bakllava:latest": ("ollama", None, "bakllava:latest"),
        "smollm2:135m": ("ollama", None, "smollm2:135m"),
        "qwen2.5:latest": ("ollama", None, "qwen2.5:latest"),
        "gemma2:latest": ("ollama", None, "gemma2:latest"),
    }

    if model_override:
        print(palette["accent"] + f"\nUsing model override: {model_override}" + palette["reset"])
        if model_override in direct_model_map:
            return direct_model_map[model_override]
        else:
            # Check if it's potentially an Ollama model (most start with llama, deepseek, etc.)
            return "ollama", None, model_override

    model_choice = os.getenv("STRIX_MODEL_CHOICE")
    default_model = model_choice if (model_choice and model_choice in direct_model_map) else ("gemini-2.5-flash" if os.getenv("GOOGLE_API_KEY") else "llama3.2:3b")

    print(palette["accent"] + f"\nSelect AI Model (Type to search, use Up/Down arrows, default: {default_model}):" + palette["reset"])
    
    available_models = list(direct_model_map.keys())
    
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.completion import WordCompleter
        completer = WordCompleter(available_models, ignore_case=True)
        session = PromptSession(completer=completer)
        choice = session.prompt(
            ANSI(palette["accent"] + "Model: " + palette["reset"]),
            complete_while_typing=True
        ).strip()
    except Exception as e:
        # Fallback if prompt_toolkit fails
        choice = input(palette["accent"] + f"Enter model name [default: {default_model}]: " + palette["reset"]).strip() or default_model

    if not choice:
        choice = default_model

    from dotenv import set_key
    set_key(env_path, "STRIX_MODEL_CHOICE", choice)

    if choice in direct_model_map:
        return direct_model_map[choice]
    else:
        # If the choice is not empty and not in the map, it's invalid
        if choice and choice != default_model:
            print(palette["error"] + f"\nError: Model '{choice}' not recognized. Falling back to {default_model}." + palette["reset"])
        return direct_model_map[default_model]

def validate_api_key(ai_type, api_key, prompt_type: str = None):
    palette = get_palette(prompt_type)

    if ai_type == "ollama":
        return True # Ollama is free, no key needed

    env_key_name = f"{ai_type.upper()}_API_KEY"
    if ai_type == "gemini":
        env_key_name = "GOOGLE_API_KEY"

    if not api_key or api_key.strip() == "":
        env_path = ensure_env_file()
        print(palette["error"] + f"\nError: {env_key_name} not found in .env file." + palette["reset"])
        print(palette["muted"] + f"Please add your {ai_type} API key to {env_path} file." + palette["reset"])
        print(palette["muted"] + "Example: " + env_key_name + "=your_api_key_here" + palette["reset"])


        setup_choice = "y" if get_yes_no_input(palette["accent"] + "\nWould you like to add your API key now? (y/N): " + palette["reset"]) else "n"

        if setup_choice == 'y':
            api_key_value = get_text_input(palette["accent"] + f"Enter your {ai_type} API key: " + palette["reset"])
            if api_key_value:
                from dotenv import set_key
                set_key(env_path, env_key_name, api_key_value)
                print(palette["success"] + f"API key added to {env_path}. Please restart the application." + palette["reset"])
                sys.exit(0)
            else:
                print(palette["error"] + "No API key provided." + palette["reset"])
                return False
        else:
            print(palette["error"] + f"No API key for {ai_type}. Falling back to Ollama." + palette["reset"])
            return False
    return True

def initialize_ai(prompt_type: str = None, model_override: str = None):
    ai_type, API_KEY, MODEL = select_ai_model(prompt_type, model_override)
    
    if not validate_api_key(ai_type, API_KEY, prompt_type):
        print(get_palette(prompt_type)["accent"] + "Switching to Ollama (llama3.2:3b)..." + get_palette(prompt_type)["reset"])
        ai_type, API_KEY, MODEL = "ollama", None, "llama3.2:3b"

    if ai_type == "gemini":
        # Avoid double warning from google-genai SDK if both keys exist in env
        if os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
            os.environ.pop("GEMINI_API_KEY", None)
            
        try:
            client = genai.Client(api_key=API_KEY)
            # Simple call to verify key
            # client.models.generate_content(model=MODEL, contents="Hello")
        except Exception as e:
             # If validation fails, we might want to catch it.
             # But for now, let's just return as before.
             pass
        return ai_type, API_KEY, MODEL
    elif ai_type == "openai":
        try:
            import openai
            client = openai.OpenAI(api_key=API_KEY)
            return ai_type, API_KEY, MODEL
        except ImportError:
            palette = get_palette(prompt_type)
            print(palette["error"] + "Error: openai package not installed. Run 'pip install openai'" + palette["reset"])
            sys.exit(1)
    elif ai_type == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=API_KEY)
            return ai_type, API_KEY, MODEL
        except ImportError:
            palette = get_palette(prompt_type)
            print(palette["error"] + "Error: anthropic package not installed. Run 'pip install anthropic'" + palette["reset"])
            sys.exit(1)
    elif ai_type == "groq":
        try:
            import groq
            client = groq.Groq(api_key=API_KEY)
            return ai_type, API_KEY, MODEL
        except ImportError:
            palette = get_palette(prompt_type)
            print(palette["error"] + "Error: groq package not installed. Run 'pip install groq'" + palette["reset"])
            sys.exit(1)
    elif ai_type == "mistral":
        try:
            import mistralai
            from mistralai import Mistral
            client = Mistral(api_key=API_KEY)
            return ai_type, API_KEY, MODEL
        except ImportError:
            palette = get_palette(prompt_type)
            print(palette["error"] + "Error: mistralai package not installed. Run 'pip install mistralai>=1.0.0'" + palette["reset"])
            sys.exit(1)
    elif ai_type == "ollama":
        client = OllamaFreeAPI()
        return ai_type, None, MODEL


def define_tools(mcp_wrapper=None):
    run_command_func = types.FunctionDeclaration(
        name="run_command", description="Execute a generic terminal command.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"command": types.Schema(type=types.Type.STRING, description="Command to execute.")},
            required=["command"]
        )
    )
    scan_subdomains_func = types.FunctionDeclaration(
        name="scan_subdomains", description="Enumerate subdomains using 'subfinder'. Output is shown in terminal (not saved automatically).",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"domain": types.Schema(type=types.Type.STRING, description="Target domain (e.g. example.com).")},
            required=["domain"]
        )
    )
    scan_ports_func = types.FunctionDeclaration(
        name="scan_ports", description="Scan all ports with version detection using 'nmap'. Output is shown in terminal.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"target": types.Schema(type=types.Type.STRING, description="Target IP or domain.")},
            required=["target"]
        )
    )
    enum_web_func = types.FunctionDeclaration(
        name="enum_web", description="Enumerate web directories using 'gobuster'. Output is shown in terminal.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"url": types.Schema(type=types.Type.STRING, description="Target URL.")},
            required=["url"]
        )
    )
    read_file_func = types.FunctionDeclaration(
        name="read_file", description="Read contents of a text file.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"path": types.Schema(type=types.Type.STRING, description="Full path to the file.")},
            required=["path"]
        )
    )
    write_file_func = types.FunctionDeclaration(
        name="write_file", description="Write content to a file.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "path": types.Schema(type=types.Type.STRING, description="Full path to the file."),
                "content": types.Schema(type=types.Type.STRING, description="Content to write.")
            },
            required=["path", "content"]
        )
    )
    list_files_func = types.FunctionDeclaration(
        name="list_files", description="List all files and directories in the current working directory.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={}
        )
    )
    clear_screen_func = types.FunctionDeclaration(
        name="clear_screen", description="Clear the terminal screen.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={}
        )
    )

    tools_list = [
        run_command_func, scan_subdomains_func, scan_ports_func,
        enum_web_func, read_file_func, write_file_func,
        list_files_func, clear_screen_func
    ]

    if mcp_wrapper and mcp_wrapper.is_available():
        mcp_tools = mcp_wrapper.get_all_tools_sync()
        for mt in mcp_tools:
            properties = {}
            required_fields = []
            
            input_schema = mt.get("inputSchema", {})
            props = input_schema.get("properties", {})
            required_fields = input_schema.get("required", [])
            for key, val in props.items():
                v_type = val.get("type", "string")
                desc = val.get("description", "")
                t_enum = types.Type.STRING
                if v_type == "integer": t_enum = types.Type.INTEGER
                elif v_type == "boolean": t_enum = types.Type.BOOLEAN
                elif v_type == "array": t_enum = types.Type.ARRAY
                elif v_type == "object": t_enum = types.Type.OBJECT
                properties[key] = types.Schema(type=t_enum, description=desc)
            
            tools_list.append(types.FunctionDeclaration(
                name=mt["name"],
                description=mt["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties if properties else None,
                    required=required_fields if required_fields else None
                )
            ))

    return types.Tool(
        function_declarations=tools_list
    )


def run_command(command: str, auto_save: bool = False) -> str:
    if not command or len(command.strip()) == 0:
        return "Error: Empty command provided."

    dangerous_patterns = [';', '&&', '||', '|', '`', '$(', '>', '<', '>>', '>>>', ';&', ';&;']
    for pattern in dangerous_patterns:
        if pattern in command:
            return f"Error: Command contains potentially dangerous pattern: {pattern}"

    if '..' in command or command.startswith('/') or command.startswith('../'):
        return "Error: Command contains invalid path pattern."

    if not auto_save:
        print(PALETTE["command"] + "\n[AI PROPOSED COMMAND]\n  $ " + command + "\n" + PALETTE["reset"])
        confirmation = "y" if get_yes_no_input("Are you sure you want to execute this command? [y/N]: ") else "n"
        if confirmation != 'y':
            return "Command cancelled by user."
    else:
        print(PALETTE["muted"] + f"\n[AUTO-SAVE MODE ON] Executing: $ {command}" + PALETTE["reset"])

    try:
        import shlex
        cmd_parts = shlex.split(command)
        result = subprocess.run(cmd_parts, check=True, text=True, capture_output=True, encoding='utf-8')
        stdout, stderr = result.stdout or "", result.stderr or ""
        combined = stdout + ("\n[STDERR]\n" + stderr if stderr else "")
        return combined.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: Command failed. Exit code {e.returncode}.\nStderr: {e.stderr}"
    except ValueError as e:
        return f"Error: Invalid command format: {e}"
    except Exception as e:
        return f"Error occurred: {e}"

def scan_subdomains(domain: str, auto_save: bool = False) -> str:
    return run_command(f"subfinder -d {domain} -silent", auto_save)

def scan_ports(target: str, auto_save: bool = False) -> str:
    return run_command(f"nmap -sV -p- {target}", auto_save)

def enum_web(url: str, auto_save: bool = False) -> str:
    wordlist_path = os.getenv("GOBUSTER_WORDLIST", "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt")
    return run_command(f"gobuster dir -u {url} -w {wordlist_path} -x php,txt,bak,html -t 50", auto_save)

def read_file(path: str) -> str:
    max_file_size = 1 * 1024 * 1024
    try:
        if os.path.getsize(path) > max_file_size:
            return f"Error: File '{path}' is too large."
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found at path '{path}'."
    except Exception as e:
        return f"Error: Cannot read file '{path}'. {e}"

def write_file(path: str, content: str, auto_save: bool = False, palette=None) -> str:
    if palette is None:
        palette = get_palette()

    if not auto_save:
        lines = content.splitlines()
        preview_lines = 20
        content_preview = "\n".join(lines[:preview_lines])
        if len(lines) > preview_lines:
            content_preview += f"\n... (and {len(lines) - preview_lines} more lines)"

        print(palette["command"] + f"\n[AI PROPOSED WRITE]\n  Path: {path}" + palette["reset"])

        bubble_content = f"Content preview:\n{content_preview}"
        print(format_chat_bubble(bubble_content, "File Content Preview", palette=palette))

        confirmation = "y" if get_yes_no_input("Are you sure you want to write this file? [y/N]: ") else "n"
        if confirmation != 'y':
            return "File write cancelled by user."
    else:
        print(palette["muted"] + f"\n[AUTO-SAVE MODE ON] Writing to file: {path}" + palette["reset"])
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to file '{path}'."
    except Exception as e:
        return f"Error: Cannot write to file '{path}'. {e}"

def list_files() -> str:
    try:
        items = sorted(os.listdir('.'))
        files = [f"[F] {item}" for item in items if os.path.isfile(item)]
        dirs = [f"[D] {item}/" for item in items if os.path.isdir(item)]
        if not files and not dirs:
            return "Current directory is empty."
        output = ""
        if dirs:
            output += "Directories:\n" + "\n".join(dirs)
        if files:
            if output:
                output += "\n\n"
            output += "Files:\n" + "\n".join(files)
        return output
    except Exception as e:
        return f"Error listing files: {e}"

def clear_screen() -> str:
    os.system('clear' if os.name == 'posix' else 'cls')
    return "Screen cleared."

def call_function(func_call, auto_save: bool, palette=None, mcp_wrapper=None):
    function_name = func_call.name
    function_args = getattr(func_call, 'args', {})

    if function_name == "run_command":
        return run_command(function_args.get("command", ""), auto_save)
    if function_name == "scan_subdomains":
        return scan_subdomains(function_args.get("domain", ""), auto_save)
    if function_name == "scan_ports":
        return scan_ports(function_args.get("target", ""), auto_save)
    if function_name == "enum_web":
        return enum_web(function_args.get("url", ""), auto_save)
    if function_name == "read_file":
        return read_file(function_args.get("path", ""))
    if function_name == "write_file":
        return write_file(function_args.get("path", ""), function_args.get("content", ""), auto_save, palette=palette)
    if function_name == "list_files":
        return list_files()
    if function_name == "clear_screen":
        return clear_screen()
        
    if mcp_wrapper and mcp_wrapper.is_available():
        all_tools = mcp_wrapper.get_all_tools_sync()
        if any(t['name'] == function_name for t in all_tools):
            print(palette["tool_call"] + f"\n[MCP TOOL DETECTED] {function_name}({function_args})" + palette["reset"])
            result = mcp_wrapper.call_tool_sync(function_name, function_args)
            return result

    return f"Error: Function '{function_name}' not recognized."

def get_responsive_width():
    """Get responsive width for chat bubbles based on terminal size"""
    try:
        terminal_width = os.get_terminal_size().columns
        bubble_width = int(terminal_width * 0.8)
        bubble_width = min(bubble_width, 120)
        bubble_width = max(bubble_width, 60)
        return bubble_width
    except OSError:
        return 80

def parse_and_execute_tool_from_text(text: str, auto_save: bool = False):
    """
    Parse text output from AI and execute appropriate tools if detected.
    This function looks for command patterns in the AI's text response
    and executes the corresponding tools directly.
    """
    import re

    subfinder_match = re.search(r'\b(?:subfinder\s+-d\s+|--domain\s+)([^\s\]\n]+)', text, re.IGNORECASE)
    if subfinder_match:
        domain = subfinder_match.group(1).strip('"`\'')
        print(PALETTE["tool_call"] + f"\n[TOOL DETECTED] scan_subdomains({domain})" + PALETTE["reset"])
        result = scan_subdomains(domain, auto_save)
        print(PALETTE["tool_output"] + f"\n[TOOL OUTPUT]\n{result}" + PALETTE["reset"])
        return result

    nmap_patterns = [
        r'nmap\s+([^\n]+?)\s+(-p-|-p\s+\d+|\s)--target\s+([^\s\n]+)',
        r'nmap\s+([^\n]+?)\s+([^\s\n]+)',
        r'nmap\s+([^\s\n]+)'
    ]

    for pattern in nmap_patterns:
        nmap_matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in nmap_matches:
            cmd_parts = match.group(0).split()
            target = None
            for part in reversed(cmd_parts):
                if not part.startswith('-') and part.lower() != 'nmap':
                    target = part.strip('"`\'')
                    break
            if target:
                print(PALETTE["tool_call"] + f"\n[TOOL DETECTED] scan_ports({target})" + PALETTE["reset"])
                result = scan_ports(target, auto_save)
                print(PALETTE["tool_output"] + f"\n[TOOL OUTPUT]\n{result}" + PALETTE["reset"])
                return result

    gobuster_match = re.search(r'\bgobuster\s+dir\s+-u\s+([^\s\n]+)', text, re.IGNORECASE)
    if gobuster_match:
        url = gobuster_match.group(1).strip('"`\'')
        print(PALETTE["tool_call"] + f"\n[TOOL DETECTED] enum_web({url})" + PALETTE["reset"])
        result = enum_web(url, auto_save)
        print(PALETTE["tool_output"] + f"\n[TOOL OUTPUT]\n{result}" + PALETTE["reset"])
        return result

    read_file_match = re.search(r'\b(?:read_file|cat|less|more|head|tail)\s+([^\s\n]+)', text, re.IGNORECASE)
    if read_file_match:
        file_path = read_file_match.group(1).strip('"`\'')
        print(PALETTE["tool_call"] + f"\n[TOOL DETECTED] read_file({file_path})" + PALETTE["reset"])
        result = read_file(file_path)
        print(PALETTE["tool_output"] + f"\n[TOOL OUTPUT]\n{result}" + PALETTE["reset"])
        return result

    command_lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in command_lines:
        if line.startswith('$ ') or line.startswith('```') or any(cmd in line for cmd in ['sudo ', 'python ', 'curl ', 'wget ', 'ls ', 'pwd ', 'ps ', 'netstat ', 'whois ']):
            if line.startswith('$ '):
                command = line[2:].strip()
            elif line.startswith('```'):
                command = line[3:].strip() if len(line) > 3 else ''
                if command.endswith('```'):
                    command = command[:-3].strip()
            else:
                command = line.strip()

            command = command.strip('`')

            if command and not command.startswith('#'):
                print(PALETTE["tool_call"] + f"\n[TOOL DETECTED] run_command({command})" + PALETTE["reset"])
                result = run_command(command, auto_save)
                print(PALETTE["tool_output"] + f"\n[TOOL OUTPUT]\n{result}" + PALETTE["reset"])
                return result

    return None

def strip_ansi(text: str) -> str:
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def pad_to_width(text: str, width: int) -> str:
    visible_length = len(strip_ansi(text))
    padding = width - visible_length
    if padding < 0: padding = 0
    return text + " " * padding

def format_chat_bubble(content: str, sender: str = "AI", width: int = None, color: str = None, palette=None) -> str:
    if palette is None:
        palette = get_palette()

    if width is None:
        width = get_responsive_width()

    lines = content.split('\n')
    formatted_lines = []

    content_color = Fore.WHITE + Style.NORMAL

    border_color = palette["accent"]

    formatted_lines.append(border_color + "┌" + "─" * (width - 2) + "┐" + palette["reset"])

    if sender:
        sender_prefix = f"┌─ {sender} "
        remaining_width = width - len(sender_prefix) - 1
        if remaining_width > 0:
            sender_line = sender_prefix + "─" * remaining_width + "┐"
            formatted_lines[0] = border_color + sender_line + palette["reset"]

    import textwrap
    in_code_block = False
    code_border_color = Fore.CYAN + Style.DIM
    text_width = width - 4
    inner_text_width = text_width - 4

    for line in lines:
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                lang = line.strip()[3:]
                if lang:
                    prefix = f"┌─ {lang[:15]} "
                    remaining = text_width - len(prefix) - 1
                    if remaining > 0:
                        inner_top = prefix + "─" * remaining + "┐"
                    else:
                        inner_top = "┌" + "─" * (text_width - 2) + "┐"
                else:
                    inner_top = "┌" + "─" * (text_width - 2) + "┐"
                formatted_lines.append(f"{border_color}│{palette['reset']} {code_border_color}{inner_top}{palette['reset']} {border_color}│{palette['reset']}")
            else:
                in_code_block = False
                inner_bottom = "└" + "─" * (text_width - 2) + "┘"
                formatted_lines.append(f"{border_color}│{palette['reset']} {code_border_color}{inner_bottom}{palette['reset']} {border_color}│{palette['reset']}")
            continue

        if in_code_block:
            code_line = line.rstrip() 
            if not code_line:
                 formatted_lines.append(f"{border_color}│{palette['reset']} {code_border_color}│ {Fore.WHITE}{' ' * inner_text_width} {code_border_color}│{palette['reset']} {border_color}│{palette['reset']}")
                 continue
                 
            while len(code_line) > inner_text_width:
                 part = code_line[:inner_text_width]
                 code_line = code_line[inner_text_width:]
                 formatted_lines.append(f"{border_color}│{palette['reset']} {code_border_color}│ {Fore.WHITE}{part}{palette['reset']} {code_border_color}│{palette['reset']} {border_color}│{palette['reset']}")
            
            padded_code = code_line.ljust(inner_text_width)
            formatted_lines.append(f"{border_color}│{palette['reset']} {code_border_color}│ {Fore.WHITE}{padded_code}{palette['reset']} {code_border_color}│{palette['reset']} {border_color}│{palette['reset']}")
            continue

        if line.strip() == "":
            formatted_lines.append(border_color + "│" + " " * (width - 2) + "│" + palette["reset"])
        else:
            clean_line = line
            if clean_line.startswith('#') or clean_line.startswith('---'):
                if clean_line.startswith('---'):
                    continue
                else:
                    clean_line = clean_line.lstrip('# ')

            wrapped = textwrap.fill(clean_line, text_width, break_long_words=True, break_on_hyphens=True)
            for wrapped_line in wrapped.split('\n'):
                padded_line = pad_to_width(wrapped_line, text_width)
                formatted_lines.append(f"{border_color}│{palette['reset']} {content_color}{padded_line}{palette['reset']} {border_color}│{palette['reset']}")

    formatted_lines.append(border_color + "└" + "─" * (width - 2) + "┘" + palette["reset"])

    bubble_str = "\n".join(formatted_lines)
    return "\n" + bubble_str

def render_markdown(text: str, palette=None) -> str:
    if palette is None:
        palette = get_palette()

    lines = text.split('\n')
    processed_lines = []

    for line in lines:
        if line.strip() == '---' or line.strip().startswith('--- '):
            continue
        elif line.strip().startswith('# ') or line.strip().startswith('## ') or line.strip().startswith('### '):
            clean_line = line.lstrip('# ')
            processed_lines.append(clean_line)
        elif line.strip().startswith('#') and not line.strip().startswith('# '):
            processed_lines.append(line)
        else:
            processed_lines.append(line)

    text = '\n'.join(processed_lines)

    text = re.sub(r'^\*\s+(.+)', palette["accent"] + '- ' + r'\1' + palette["reset"], text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', lambda match: palette["accent"] + Style.BRIGHT + match.group(1) + palette["reset"], text)
    text = re.sub(r'\*(.*?)\*', lambda match: palette["accent"] + match.group(1) + palette["reset"], text)
    return text

def show_loading_indicator(stop_event, prompt_type: str = None):
    palette = get_palette(prompt_type)
    animation = ['⣾', '⣷', '⣯', '⣟', '⡿', '⢿', '⣻', '⣽']
    idx = 0
    while not stop_event.is_set():
        print(f"\r{palette['accent']}{animation[idx % len(animation)]} Thinking...{palette['reset']}", end="", flush=True)
        idx += 1
        time.sleep(0.1)
    print("\r" + " " * 30 + "\r", end="", flush=True)


def chat_loop(ai_type, API_KEY, MODEL, auto_save: bool, prompt_type: str = None):
    PALETTE = get_palette(prompt_type)

    SYSTEM_PROMPTS = {
        "ctf": """
You are Atlas, a Capture The Flag (CTF) competition assistant.

Rules:
1. Help users solve CTF challenges ethically and educationally.
2. Break down complex problems into understandable steps.
3. Explain methodologies and reasoning clearly.
4. Suggest multiple approaches when applicable.
5. Point out common pitfalls and how to avoid them.
6. Encourage learning and understanding over quick solutions.
7. Respect challenge categories (crypto, forensics, web, etc.).
8. USE TOOLS DIRECTLY when appropriate to assist with CTF challenges (e.g., run_command, read_file, write_file). Do not just describe the command in text - call the tool directly.
9. If you need to analyze a file, use read_file directly. If you need to run a command, use run_command directly.
10. Do not suggest commands for the user to run - instead, execute them yourself using tools when appropriate.
11. Do not use markdown heading formats (###, ##, #, ---) in your responses. Use regular text formatting instead.
12. Use • instead of * for lists.
13. For complex tasks, start with a <plan>...</plan> block to outline your approach.
        """,
        "vuln-research": """
You are Atlas, a vulnerability research assistant.

Rules:
1. Assist with vulnerability analysis and research methodologies.
2. NEVER exploit vulnerabilities in real systems without authorization.
3. Explain vulnerability concepts with practical examples.
4. Guide users through secure coding practices.
5. Help with CVE analysis and PoC development in controlled environments.
6. Provide guidance on responsible disclosure procedures.
7. Detail attack vectors and mitigation strategies.
8. Emphasize ethical considerations in all recommendations.
9. USE TOOLS DIRECTLY when appropriate to assist with vulnerability analysis (e.g., scan_subdomains, scan_ports, enum_web, run_command). Do not just describe the scan in text - call the tool directly.
10. If you need to enumerate subdomains, use scan_subdomains directly. If you need to scan ports, use scan_ports directly.
11. Do not suggest commands for the user to run - instead, execute them yourself using tools when appropriate.
12. Do not use markdown heading formats (###, ##, #, ---) in your responses. Use regular text formatting instead.
13. Use • instead of * for lists.
14. For complex tasks, start with a <plan>...</plan> block to outline your approach.
        """,
        "pentest": """
You are Atlas, a technical penetration testing assistant.

Rules:
1. NEVER save scan results to a file automatically.
2. ONLY save to a file if the user explicitly asks (e.g., "save to file.txt" or "write this to output.txt").
3. When scanning (subdomains, ports, web), show output in the terminal only.
4. If the user provides a list and says "save to X", use 'write_file' with that content.
5. Be precise, technical, and do not hallucinate actions.
6. Match the user's language.
7. Use markdown: **bold**, *italic*, * lists.
8. You can create any script according to user requests, and can save the script via the save file function.
9. USE TOOLS DIRECTLY when appropriate (e.g., scan_subdomains, scan_ports, enum_web, run_command, read_file, write_file). Do not just describe the command in text - call the tool directly.
10. If you need to enumerate subdomains, use scan_subdomains directly. If you need to scan ports, use scan_ports directly.
11. Do not suggest commands for the user to run - instead, execute them yourself using tools when appropriate.
12. Do not use markdown heading formats (###, ##, #, ---) in your responses. Use regular text formatting instead.
13. Use • instead of * for lists.
14. For complex tasks, start with a <plan>...</plan> block to outline your approach.
        """
    }

    current_prompt_type = prompt_type if prompt_type in SYSTEM_PROMPTS else "pentest"
    system_prompt = SYSTEM_PROMPTS[current_prompt_type]

    from atlas_mcp import AtlasMCPWrapper
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_servers.json")
    mcp_wrapper = AtlasMCPWrapper(config_path=config_path)
    if mcp_wrapper.is_available():
        mcp_wrapper.start()
        
    if ai_type == "gemini":
        try:
            client = genai.Client(api_key=API_KEY)
            pentest_tool = define_tools(mcp_wrapper=mcp_wrapper)
            # Create chat with tools and system instruction
            chat = client.chats.create(
                model=MODEL,
                config=types.GenerateContentConfig(
                    tools=[pentest_tool],
                    system_instruction=system_prompt,
                    temperature=0.7, # Add some creativity
                )
            )
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize Gemini client: {e}" + PALETTE["reset"])
            return
    elif ai_type == "openai":
        try:
            import openai
            client = openai.OpenAI(api_key=API_KEY)
            chat_history = [
                {"role": "system", "content": system_prompt}
            ]
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize OpenAI client: {e}" + PALETTE["reset"])
            return
    elif ai_type == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=API_KEY)
            chat_history = [
                {"role": "system", "content": system_prompt}
            ]
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize Anthropic client: {e}" + PALETTE["reset"])
            return
    elif ai_type == "groq":
        try:
            import groq
            client = groq.Groq(api_key=API_KEY)
            chat_history = [
                {"role": "system", "content": system_prompt}
            ]
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize Groq client: {e}" + PALETTE["reset"])
            return
    elif ai_type == "mistral":
        try:
            import mistralai
            from mistralai import Mistral
            client = Mistral(api_key=API_KEY)
            chat_history = [
                {"role": "system", "content": system_prompt}
            ]
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize Mistral client: {e}" + PALETTE["reset"])
            return
    elif ai_type == "ollama":
        try:
            client = OllamaFreeAPI()
        except Exception as e:
            print(PALETTE["error"] + f"\n[ERROR] Failed to initialize Ollama client: {e}" + PALETTE["reset"])
            return

    mode_text = " (Auto-Save MODE ON)" if auto_save else ""
    banner_lines = [
        "    |     |''||''| '||'          |      .|'''.|  ",
        "   |||       ||     ||          |||     ||..  '  ",
        "  |  ||      ||     ||         |  ||     ''|||.  ",
        " .''''|.     ||     ||        .''''|.  .     '|| ",
        ".|.  .||.   .||.   .||.....| .|.  .||. |'....|'  ",
        "                                                 ",
        "            v0.1.4 - openverselabs               "
    ]
    os.system('clear' if os.name == 'posix' else 'cls')
    print(PALETTE["banner_bg"] + PALETTE["accent"])
    for line in banner_lines:
        print("  " + line)
    print(PALETTE["reset"])
    print(PALETTE["accent"] + f"\nAtlas with {ai_type.upper()} ({MODEL}) model is ready{mode_text}!" + PALETTE["reset"])
    print(PALETTE["muted"] + "Type '!exit' or 'quit' to leave.\n" + PALETTE["reset"])

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.formatted_text import ANSI

        session = PromptSession(history=InMemoryHistory(), completer=FileCompleter())
        use_prompt_toolkit = True
    except ImportError:
        print(PALETTE["error"] + "Warning: 'prompt_toolkit' not installed. Arrow keys and history disabled." + PALETTE["reset"])
        use_prompt_toolkit = False

    while True:
        try:
            if use_prompt_toolkit:
                placeholder_text = ANSI(PALETTE["placeholder"] + "Type your message or @path/to/file" + PALETTE["reset"])

                user_input = session.prompt(
                    "\n> ",
                    placeholder=placeholder_text
                )
            else:
                user_input = input("\n> ")

            if user_input.lower() in ['!exit', 'quit']:
                print(PALETTE["success"] + "Goodbye!" + PALETTE["reset"])
                break
            if not user_input.strip():
                continue

            if user_input.startswith('/'):
                cmd_parts = user_input.strip().split()
                cmd_name = cmd_parts[0].lower()
                if cmd_name == "/help":
                    print(PALETTE["accent"] + "\n[SLASH COMMANDS]" + PALETTE["reset"])
                    print("  /help   - Show this help menu")
                    print("  /mcp    - List configured MCP servers and their tools")
                    print("  /clear  - Clear the terminal screen")
                    print("  /prompt - Switch system prompt (pentest, ctf, vuln-research)")
                    print(PALETTE["accent"] + "\n[BUILT-IN TOOLS]" + PALETTE["reset"])
                    print("  @<file/path> - Read a file into context")
                    print("  !exit or quit - Exit the program")
                elif cmd_name == "/mcp":
                    if mcp_wrapper and mcp_wrapper.is_available():
                        servers = mcp_wrapper.get_loaded_servers()
                        print(PALETTE["accent"] + "\n[MCP SERVERS]" + PALETTE["reset"])
                        if servers:
                            for s in servers:
                                print(f"  - {s}")
                        else:
                            print(PALETTE["muted"] + "  No servers configured or loaded." + PALETTE["reset"])
                        
                        tools = mcp_wrapper.get_all_tools_sync()
                        if tools:
                            print(PALETTE["accent"] + "\n[MCP TOOLS]" + PALETTE["reset"])
                            for t in tools:
                                print(f"  - [{t['server']}] {t['name']} : {t['description']}")
                        else:
                            print(PALETTE["muted"] + "  No tools loaded." + PALETTE["reset"])
                    else:
                        print(PALETTE["error"] + "mcp Python library is not installed. 'pip install mcp'" + PALETTE["reset"])
                elif cmd_name == "/clear":
                    clear_screen()
                elif cmd_name == "/prompt":
                    if len(cmd_parts) > 1:
                        new_type = cmd_parts[1].lower()
                        if new_type in SYSTEM_PROMPTS:
                            current_prompt_type = new_type
                            system_prompt = SYSTEM_PROMPTS[new_type]
                            PALETTE = get_palette(new_type) # Update palette
                            
                            # Reload effect: Clear screen and reprint banner
                            os.system('clear' if os.name == 'posix' else 'cls')
                            print(PALETTE["banner_bg"] + PALETTE["accent"])
                            for line in banner_lines:
                                print("  " + line)
                            print(PALETTE["reset"])
                            print(PALETTE["success"] + f"System prompt & theme switched to: {new_type}" + PALETTE["reset"])
                            
                            # Update the AI session
                            if ai_type == "gemini":
                                chat = client.chats.create(
                                    model=MODEL,
                                    config=types.GenerateContentConfig(
                                        tools=[pentest_tool],
                                        system_instruction=system_prompt,
                                        temperature=0.7,
                                    )
                                )
                                print(PALETTE["muted"] + "Chat session restarted with new instructions." + PALETTE["reset"])
                            else:
                                if 'chat_history' in locals() or 'chat_history' in globals():
                                    if chat_history and chat_history[0]["role"] == "system":
                                        chat_history[0]["content"] = system_prompt
                                        print(PALETTE["muted"] + "System prompt updated in history." + PALETTE["reset"])
                        else:
                            print(PALETTE["error"] + f"Invalid prompt type. Choices: {', '.join(SYSTEM_PROMPTS.keys())}" + PALETTE["reset"])
                    else:
                        print(PALETTE["accent"] + f"Current prompt: {current_prompt_type}" + PALETTE["reset"])
                        print(f"Available prompts: {', '.join(SYSTEM_PROMPTS.keys())}")
                        print("Usage: /prompt <type>")
                else:
                    print(PALETTE["error"] + f"Unknown slash command: {cmd_name}. Type /help for a list of commands." + PALETTE["reset"])
                continue

            if user_input.startswith('@'):
                parts = user_input[1:].split(' ', 1)
                file_path = parts[0].strip()
                user_query = parts[1].strip() if len(parts) > 1 else ""
                
                if file_path:
                    file_content = read_file(file_path)
                    if file_content.startswith("Error:"):
                         print(PALETTE["error"] + file_content + PALETTE["reset"])
                         continue
                         
                    if user_query:
                        print(PALETTE["muted"] + f"Loaded file: {file_path}" + PALETTE["reset"])
                        user_input = f"{user_query}\n\n---\nFile: {file_path}\nContent:\n{file_content}"
                    else:
                        print(format_chat_bubble(file_content, f"File Content: {file_path}", palette=PALETTE))
                        continue
                else:
                    print(PALETTE["error"] + "Please provide a file path after @ (e.g., @atlas/main.py)" + PALETTE["reset"])
                    continue

            stop_event = threading.Event()
            loader_thread = threading.Thread(target=show_loading_indicator, args=(stop_event, prompt_type))
            loader_thread.daemon = True
            loader_thread.start()


            if ai_type == "gemini":
                try:
                    response = chat.send_message(user_input)
                except Exception as e:
                    stop_event.set()
                    loader_thread.join()
                    print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                    continue
                finally:
                    stop_event.set()
                    loader_thread.join()

                while True:
                    if not response.candidates:
                        break
                    
                    candidate = response.candidates[0]
                    # Check for finish reason if needed, but usually parts check is enough
                    
                    parts = candidate.content.parts
                    function_call = None
                    for part in parts:
                        if part.function_call:
                            function_call = part.function_call
                            break
                    
                    if function_call:
                        user_request_lower = user_input.lower()
                        is_text_request = any(keyword in user_request_lower for keyword in
                                            ['strategi', 'strategy', 'how to', 'explain', 'how can i', 'tips',
                                             'advice', 'tutorial', 'guide', 'write', 'buatkan', 'buat',
                                             'what is', 'describe', 'buatkan strategi', 'cara', 'step by step'])

                        # Intercept tool calls if user asked for explanation
                        if is_text_request and function_call.name in ['run_command', 'scan_subdomains', 'scan_ports', 'enum_web']:
                            # But only if it's the FIRST turn? 
                            # The original code logic was a bit aggressive. 
                            # Let's keep it but maybe refine it. 
                            # Actually, let's keep it as is to preserve behavior.
                            
                            try:
                                guidance_text = f"Please provide the requested information in text format instead of suggesting commands. User requested: {user_input}"
                                
                                stop_event = threading.Event()
                                loader_thread = threading.Thread(target=show_loading_indicator, args=(stop_event, prompt_type))
                                loader_thread.daemon = True
                                loader_thread.start()
                                
                                response = chat.send_message(guidance_text)
                            except Exception as guidance_err:
                                stop_event.set()
                                loader_thread.join()
                                print(PALETTE["error"] + f"\n[GUIDANCE ERROR] {guidance_err}" + PALETTE["reset"])
                                break
                            finally:
                                stop_event.set()
                                loader_thread.join()
                            continue

                        try:
                            # Execute the tool
                            function_response = call_function(function_call, auto_save, palette=PALETTE, mcp_wrapper=mcp_wrapper)
                            print(PALETTE["command"] + f"\n[OUTPUT]\n{function_response}" + PALETTE["reset"])

                            stop_event = threading.Event()
                            loader_thread = threading.Thread(target=show_loading_indicator, args=(stop_event, prompt_type))
                            loader_thread.daemon = True
                            loader_thread.start()
                            
                            try:
                                # Send tool output back to model
                                # Construct the response part
                                response_part = types.Part(
                                    function_response=types.FunctionResponse(
                                        name=function_call.name,
                                        response={"result": function_response}
                                    )
                                )
                                response = chat.send_message(response_part)
                            finally:
                                stop_event.set()
                                loader_thread.join()
                        except Exception as call_err:
                            print(PALETTE["error"] + f"\n[FUNCTION ERROR] {call_err}" + PALETTE["reset"])
                            break
                    else:
                        # Text response
                        final_text = "".join([part.text for part in parts if part.text])
                        if final_text.strip():
                            # Check for Planning section
                            import re
                            plan_match = re.search(r'<plan>(.*?)</plan>', final_text, re.DOTALL)
                            if plan_match:
                                plan_content = plan_match.group(1).strip()
                                # Render plan content
                                width = get_responsive_width()
                                print("\n" + PALETTE["muted"] + "┌─ Planning " + "─" * (width - 13) + "┐" + PALETTE["reset"])
                                for line in plan_content.split('\n'):
                                    import textwrap
                                    wrapped_lines = textwrap.wrap(line, width - 4)
                                    if not wrapped_lines:
                                        print(PALETTE["muted"] + "│" + " " * (width - 2) + "│" + PALETTE["reset"])
                                    for w_line in wrapped_lines:
                                        padded = pad_to_width(w_line, width - 4)
                                        print(PALETTE["muted"] + "│ " + padded + " │" + PALETTE["reset"])
                                print(PALETTE["muted"] + "└" + "─" * (width - 2) + "┘" + PALETTE["reset"])
                                
                                # Remove plan from final text
                                final_text = final_text.replace(plan_match.group(0), "").strip()
                                
                            if final_text.strip():
                                rendered_text = render_markdown(final_text, PALETTE)
                                print(format_chat_bubble(rendered_text, "Atlas", palette=PALETTE))
                        break
            else:
                if ai_type == "openai":
                    try:
                        chat_history.append({"role": "user", "content": user_input})
                        response = client.chat.completions.create(
                            model=MODEL,
                            messages=chat_history,
                            temperature=0.7,
                            max_tokens=2048
                        )
                        ai_response = response.choices[0].message.content
                        chat_history.append({"role": "assistant", "content": ai_response})

                        tool_result = parse_and_execute_tool_from_text(ai_response, auto_save)
                        if tool_result is None:
                            rendered_ai_response = render_markdown(ai_response, PALETTE)
                            print(format_chat_bubble(rendered_ai_response, "Atlas", palette=PALETTE))

                    except Exception as e:
                        stop_event.set()
                        loader_thread.join()
                        print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                        continue
                    finally:
                        stop_event.set()
                        loader_thread.join()

                elif ai_type == "anthropic":
                    try:
                        chat_history.append({"role": "user", "content": user_input})
                        response = client.messages.create(
                            model=MODEL,
                            messages=chat_history[1:],
                            max_tokens=2048,
                            temperature=0.7
                        )
                        ai_response = response.content[0].text
                        chat_history.append({"role": "assistant", "content": ai_response})

                        tool_result = parse_and_execute_tool_from_text(ai_response, auto_save)
                        if tool_result is None:
                            rendered_ai_response = render_markdown(ai_response, PALETTE)
                            print(format_chat_bubble(rendered_ai_response, "Atlas", palette=PALETTE))

                    except Exception as e:
                        stop_event.set()
                        loader_thread.join()
                        print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                        continue
                    finally:
                        stop_event.set()
                        loader_thread.join()

                elif ai_type == "groq":
                    try:
                        chat_history.append({"role": "user", "content": user_input})
                        response = client.chat.completions.create(
                            model=MODEL,
                            messages=chat_history,
                            temperature=0.7,
                            max_tokens=2048
                        )
                        ai_response = response.choices[0].message.content
                        chat_history.append({"role": "assistant", "content": ai_response})

                        tool_result = parse_and_execute_tool_from_text(ai_response, auto_save)
                        if tool_result is None:
                            rendered_ai_response = render_markdown(ai_response, PALETTE)
                            print(format_chat_bubble(rendered_ai_response, "Atlas", palette=PALETTE))

                    except Exception as e:
                        stop_event.set()
                        loader_thread.join()
                        print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                        continue
                    finally:
                        stop_event.set()
                        loader_thread.join()

                elif ai_type == "mistral":
                    try:
                        chat_history.append({"role": "user", "content": user_input})
                        response = client.chat.complete(
                            model=MODEL,
                            messages=chat_history,
                            temperature=0.7,
                            max_tokens=2048
                        )
                        ai_response = response.choices[0].message.content
                        chat_history.append({"role": "assistant", "content": ai_response})

                        tool_result = parse_and_execute_tool_from_text(ai_response, auto_save)
                        if tool_result is None:
                            rendered_ai_response = render_markdown(ai_response, PALETTE)
                            print(format_chat_bubble(rendered_ai_response, "Atlas", palette=PALETTE))

                    except Exception as e:
                        stop_event.set()
                        loader_thread.join()
                        print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                        continue
                    finally:
                        stop_event.set()
                        loader_thread.join()

                elif ai_type == "ollama":
                    try:
                        # Initialize history if not present
                        if 'chat_history' not in globals() and 'chat_history' not in locals():
                            chat_history = [
                                {"role": "system", "content": system_prompt}
                            ]

                        chat_history.append({"role": "user", "content": user_input})
                        
                        
                        width = get_responsive_width()
                        full_response = ""
                        in_think = False
                        bubble_started = False
                        loader_stopped = False
                        
                        try:
                            # explicitly set num_predict to 4096 since ollamafreeapi defaults to 128
                            for chunk in client.stream_chat(prompt=user_input, model=MODEL, messages=chat_history, num_predict=4096):
                                if chunk:
                                    full_response += chunk

                        except Exception as stream_err:
                            # Fallback if streaming fails
                            full_response = client.chat(prompt=user_input, model=MODEL, messages=chat_history, num_predict=4096)
                        
                        if not loader_stopped:
                            stop_event.set()
                            if loader_thread.is_alive():
                                loader_thread.join()
                            loader_stopped = True
                        
                        print("\r" + " " * 30 + "\r", end="", flush=True)

                        # Clean response
                        import re
                        full_response_clean = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()
                        
                        chat_history.append({"role": "assistant", "content": full_response_clean})
                        
                        # Print beautiful formatted bubble
                        if full_response_clean:
                            rendered_ai_response = render_markdown(full_response_clean, PALETTE)
                            print(format_chat_bubble(rendered_ai_response, "Atlas", palette=PALETTE))
                        
                        # Check for tools in the cleaned response
                        parse_and_execute_tool_from_text(full_response_clean, auto_save)

                    except Exception as e:
                        if not stop_event.is_set():
                            stop_event.set()
                        if loader_thread.is_alive():
                            loader_thread.join()
                        print(PALETTE["error"] + f"\n[ERROR] {e}" + PALETTE["reset"])
                        continue

        except KeyboardInterrupt:
            print("\n" + PALETTE["muted"] + "Session ended by user." + PALETTE["reset"])
            break
        except Exception as e:
            err_msg = str(e)
            # Simplify common network/api errors
            if "quota" in err_msg.lower():
                print(PALETTE["error"] + "\n[Quota Error] API quota exceeded. Please check your billing or usage limits." + PALETTE["reset"])
            elif "invalid" in err_msg.lower() and "key" in err_msg.lower():
                print(PALETTE["error"] + "\n[Auth Error] Invalid API key. Please check your ~/Atlas/.env file." + PALETTE["reset"])
            else:
                print(PALETTE["error"] + f"\n[Atlas Error] {err_msg}" + PALETTE["reset"])
            continue

def main():
    parser = argparse.ArgumentParser(description="Atlas: Command-line pentesting assistant.")
    parser.add_argument('--auto-save', action='store_true', help='Bypass confirmation prompts (USE WITH CAUTION)')
    parser.add_argument('--prompt', choices=['pentest', 'ctf', 'vuln-research'],
                       help='Select system prompt: pentest (default), ctf, vuln-research')
    parser.add_argument('--model', type=str, help='Specify AI model directly (e.g., gemini-2.5-flash, gpt-4, claude-3-sonnet, etc.)')


    args = parser.parse_args()


    ai_type, API_KEY, MODEL = initialize_ai(prompt_type=args.prompt, model_override=args.model)
    chat_loop(ai_type, API_KEY, MODEL, auto_save=args.auto_save, prompt_type=args.prompt)


if __name__ == "__main__":
    main()