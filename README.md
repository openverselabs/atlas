# Atlas v0.1.4

> [!IMPORTANT]
> **Migration Note**: This project was originally known as [Strix](https://github.com/strixproject/Strix). It has been migrated and renamed to **Atlas** due to naming/copyright considerations. The original repository is now deprecated in favor of this one.

Atlas is a command-line penetration testing assistant powered by AI. It integrates with various AI models to help cybersecurity professionals and enthusiasts with technical tasks, while maintaining strict security controls to prevent unintended actions.

## Features

- **Multi-AI Support**: Works with Google Gemini, OpenAI GPT-4, Anthropic Claude, Groq LLaMA 3, and Mistral (default).
- **Zero-Config Fallback**: Instantly get access to free open-source models like `deepseek-r1:latest` directly if you don't have API keys.
- **MCP Tool Connections**: Built-in dynamic integration for Model Context Protocol APIs (such as Burpsuite) using Server-Sent Events (SSE) and Stdio channels.
- **Slash Commands Autocomplete**: Quick execution via CLI dropdown routes (e.g. `/mcp`, `/help`)
- **Expanded Model Selection**: Access to multiple models from each provider (e.g., gemini-2.5-flash, gpt-4o, claude-3-opus, etc.)
- **Interactive Mode**: Real-time conversation interface with the AI assistant
- **Confirmation Prompts**: Asks for confirmation before executing dangerous commands

## What's New in v0.1.4

- **MCP Module Support & Python Wrapper Integration**: Control arbitrary endpoints such as Burpsuite entirely through `mcp_servers.json` configuration blocks natively.
- **Improved Slash Command Routings**: Execute tool lookups instantly while writing your payload in terminal.
- **Atlas Main Engine Path Fixes**: All backend references use explicit system directory targeting (improving stability).

## What's New in v0.1.3

- **New --model Command**: Direct model selection from command line
  - Specify exact models: `atlas --model gpt-4`, `atlas --model gemini-2.5-flash`, etc.
  - Use provider names: `atlas --model openai`, `atlas --model groq`, etc.
  - Combine with other options: `atlas --model gpt-4 --prompt ctf --auto-save`
- **Enhanced Dependency Management**: All AI provider packages now included in installation

## What's New in v0.1.2

- **Bug Fixes**: Resolved several stability issues and bugs from previous version
- **Performance Improvements**: Enhanced response times and overall application performance
- **UI Enhancements**: Minor user interface improvements for better user experience

## What's New in v0.1.1

- **Expanded Model Support**: Added support for multiple models from each AI provider
  - **Google Gemini**: gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-pro-exp, gemini-1.0-pro
  - **OpenAI**: gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo
  - **Anthropic**: claude-3-sonnet, claude-3-opus, claude-3-haiku, claude-2.1
  - **Groq**: llama3-70b-8192, llama-3.1-8b, llama-3.1-70b, mixtral-8x7b, gemma-7b
  - **Mistral**: mistral-small-latest, mistral-large, mistral-medium, mistral-nemo
- **Enhanced User Experience**: Improved input handling using prompt_toolkit with better formatting and interaction
- **Better Model Selection Menu**: Organized and expanded model selection interface

## Installation

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/atlasproject/Atlas/main/install.sh | bash
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/atlasproject/Atlas.git
cd Atlas

# Option 1: Install in virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .

# Option 2: Install globally/local (without virtual environment)
pip install -e .
```

# If the binary is in ~/.local/share/pipx/venvs/atlas/bin/atlas
sudo ln -sf ~/.local/share/pipx/venvs/atlas/bin/atlas /usr/local/bin/atlas

# Set up API keys
# Create ~/Atlas/.env with your API keys:
# GOOGLE_API_KEY=your_google_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# GROQ_API_KEY=your_groq_api_key_here
# MISTRAL_API_KEY=your_mistral_api_key_here
```

## Usage

```bash
# Start interactive mode
atlas

# Start with auto-save mode (bypass confirmation prompts)
atlas --auto-save

# Start with a specific system prompt
atlas --prompt ctf
atlas --prompt vuln-research

# Start with a specific AI model (new in v0.1.3)
atlas --model gpt-4
atlas --model gemini-2.5-flash
atlas --model claude-3-sonnet
atlas --model llama3-70b-8192
atlas --model mistral-large

# You can also specify provider names (uses default model for that provider)
atlas --model openai      # Uses gpt-4 by default
atlas --model gemini      # Uses gemini-2.5-flash by default
atlas --model anthropic   # Uses claude-3-sonnet by default
atlas --model groq        # Uses llama3-70b-8192 by default
atlas --model mistral     # Uses mistral-small-latest by default

# Combine with other options
atlas --model gpt-4 --prompt ctf --auto-save

# Show help
atlas --help
```

## System Prompts

Atlas comes with three built-in system prompts that can be selected using the `--prompt` option:

### Pentesting Assistant (Default)

```bash
atlas --prompt pentest
```

```
Rules:
1. NEVER save scan results to a file automatically.
2. ONLY save to a file if the user explicitly asks (e.g., "save to file.txt" or "write this to output.txt").
3. When scanning (subdomains, ports, web), show output in the terminal only.
4. If the user provides a list and says "save to X", use 'write_file' with that content.
5. Be precise, technical, and do not hallucinate actions.
6. Match the user's language.
7. Use markdown: **bold**, *italic*, * lists.
8. You can create any script according to user requests, and can save the script via the save file function.
```

### CTF Assistant

```bash
atlas --prompt ctf
```

```
Rules:
1. Help users solve CTF challenges ethically and educationally.
2. Break down complex problems into understandable steps.
3. Explain methodologies and reasoning clearly.
4. Suggest multiple approaches when applicable.
5. Point out common pitfalls and how to avoid them.
6. Encourage learning and understanding over quick solutions.
7. Respect challenge categories (crypto, forensics, web, etc.).
```

### Vulnerability Researcher

```bash
atlas --prompt vuln-research
```

```
Rules:
1. Assist with vulnerability analysis and research methodologies.
2. NEVER exploit vulnerabilities in real systems without authorization.
3. Explain vulnerability concepts with practical examples.
4. Guide users through secure coding practices.
5. Help with CVE analysis and PoC development in controlled environments.
6. Provide guidance on responsible disclosure procedures.
7. Detail attack vectors and mitigation strategies.
8. Emphasize ethical considerations in all recommendations.
```

## Supported AI Models

### Google Gemini

- gemini-2.5-flash (default)
- gemini-2.0-flash
- gemini-1.5-pro
- gemini-1.5-pro-exp
- gemini-1.0-pro

### OpenAI

- gpt-4
- gpt-4-turbo
- gpt-4o
- gpt-3.5-turbo

### Anthropic Claude

- claude-3-sonnet
- claude-3-opus
- claude-3-haiku
- claude-2.1

### Groq

- llama3-70b-8192
- llama-3.1-8b
- llama-3.1-70b
- mixtral-8x7b
- gemma-7b

### Mistral

- mistral-small-latest
- mistral-large
- mistral-medium
- mistral-nemo

### OllamaFreeAPI (Free, Zero-Config)

Powered by community distributed nodes, allowing users to use open-source LLMs out-of-the-box simply via `atlas --model ollama`.

- deepseek-r1:latest (Powerful reasoning capabilities)
- llama3.2:3b
- mistral:latest
- gpt-oss:20b

## Required Tools

For full functionality, install these security tools:

- subfinder
- nmap
- gobuster
  Or you can use your local tools that are already installed.

## License

MIT License - see LICENSE file for details.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
