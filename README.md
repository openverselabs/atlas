<p align="center">
  <a href="https://github.com/openverselabs/atlas">
    <img src="https://i.ibb.co.com/chvJ3Cy7/Project-Logo.png" alt="Atlas Logo" >
  </a>
</p>

<h1 align="center">Atlas v0.1.4</h1>

<p align="center">
  <strong>A professional AI-powered command-line assistant for penetration testing and vulnerability research.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/Version-0.1.4-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.9+-brightgreen.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey.svg" alt="Platform">
</p>

---

> [!IMPORTANT]
> **Migration Note**: This project was originally known as [Strix](https://github.com/strixproject/Strix). It has been migrated and renamed to **Atlas** due to naming and copyright considerations. The original repository is now deprecated in favor of this one.

## Table of Contents
- [Core Features](#core-features)
- [Release History](#release-history)
- [Installation](#installation)
- [Environment Configuration](#environment-configuration)
- [Usage and Commands](#usage-and-commands)
- [System Prompts and Personas](#system-prompts-and-personas)
- [Supported AI Models](#supported-ai-models)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)
- [License and Contributions](#license-and-contributions)

---

## Core Features

*   **Multi-AI Provider Support**: Native integration with Google Gemini, OpenAI, Anthropic Claude, Groq, and Mistral.
*   **Zero-Config Fallback**: Instant access to open-source models like `deepseek-r1:latest` via OllamaFreeAPI for users without personal API keys.
*   **Model Context Protocol (MCP)**: Built-in dynamic integration for MCP APIs (such as Burp Suite) using Server-Sent Events (SSE) and Stdio channels.
*   **Slash Command Interface**: Interactive CLI with autocomplete for quick tool execution and system navigation (e.g., `/mcp`, `/help`).
*   **Interactive Conversation**: A real-time terminal interface optimized for technical dialogue and code generation.
*   **Safety Controls**: Mandatory confirmation prompts before the execution of potentially hazardous system commands.

---

## Release History

### v0.1.4
*   **MCP Module Support**: Full control of arbitrary endpoints like Burp Suite via `mcp_servers.json` configuration.
*   **Python Wrapper Integration**: Enhanced stability for executing modular Python scripts.
*   **Path Optimization**: Backend references now utilize explicit system directory targeting to prevent execution errors.

### v0.1.3
*   **Direct Model Selection**: Introduced the `--model` flag for granular control.
*   **Provider Aliases**: Support for calling providers directly (e.g., `atlas --model groq`).
*   **Dependency Management**: Inclusion of all AI provider SDKs within the base installation.

---

## Installation

### Automated Installation (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/openverselabs/atlas/main/install.sh | bash

```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openverselabs/Atlas.git
cd Atlas

# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install package in editable mode
pip install -e .

# Optional: Link binary for global access
sudo ln -sf ~/.local/share/pipx/venvs/atlas/bin/atlas /usr/local/bin/atlas

```

---

## Environment Configuration

Create a `.env` file in the application directory to store your API keys:

```env
GOOGLE_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
GROQ_API_KEY=your_key
MISTRAL_API_KEY=your_key

```

---

## Usage and Commands

| Flag | Description |
| --- | --- |
| `atlas` | Launch the interactive assistant |
| `--auto-save` | Bypass confirmation prompts for file operations |
| `--prompt [type]` | Select a system persona: `pentest`, `ctf`, or `vuln-research` |
| `--model [name]` | Specify a model (e.g., `gpt-4o`, `gemini-2.0-flash`) |
| `--help` | Display all available command-line options |

### Example Execution

```bash
atlas --model gpt-4o --prompt ctf --auto-save

```

---

## System Prompts and Personas

### Pentesting Assistant (Default)

**Focus**: Efficiency and Technical Accuracy.

* Never saves results to files unless explicitly instructed.
* Displays scanning output directly in the terminal.
* Utilizes the `write_file` function only upon direct user request.

### CTF Assistant

**Focus**: Education and Methodology.

* Breaks down complex challenges into logical steps.
* Explains underlying reasoning and methodologies.
* Suggests multiple attack vectors to encourage learning.

### Vulnerability Researcher

**Focus**: Analysis and Responsible Disclosure.

* Assists in CVE analysis and Proof of Concept (PoC) development.
* Guides users through secure coding practices and mitigation strategies.

---

## Supported AI Models

* **Google Gemini**: gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro
* **OpenAI**: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
* **Anthropic**: claude-3-opus, claude-3-sonnet, claude-3-haiku
* **Groq / Mistral**: llama-3.1-70b, mixtral-8x7b, mistral-large
* **Ollama (Local)**: deepseek-r1:latest, llama3.2:3b

---

## Roadmap

* [ ] **Metasploit Integration**: Direct RPC connection to MSF sessions.
* [ ] **Report Generation**: Exporting terminal sessions into structured PDF/Markdown reports.
* [ ] **Local RAG**: Ability to "read" local security documentation or PDF notes for context.
* [ ] **Web UI**: Optional lightweight local dashboard for visual scan management.

---

## Disclaimer

> [!CAUTION]
> This tool is intended for **educational purposes** and **authorized security testing** only. The author is not responsible for any misuse or damage caused by this application. Users are strictly responsible for complying with all local, state, and federal laws regarding cybersecurity and privacy. Unauthorized access to systems is illegal.

---

## Star History

---

## License and Contributions

* **License**: Distributed under the MIT License.
* **Contributing**: Pull requests are welcome. For major changes, please open an issue first to discuss the proposed updates.

---
