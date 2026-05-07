#!/bin/bash

# =================================================================
# Atlas AI Penetration Testing Assistant - Installation Script
# =================================================================
# Usage: curl -sSL https://github.com/atlasproject/Atlas/install.sh | bash
# =================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}        Atlas v0.1.4 Installation Script        ${NC}"

# Check for required tools
echo -e "${YELLOW}[*] Checking system requirements...${NC}"

check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}[!] Error: $1 is not installed.${NC}"
        return 1
    fi
    return 0
}

MISSING_DEPS=0
check_cmd git || MISSING_DEPS=1
check_cmd python3 || MISSING_DEPS=1

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${RED}[!] Please install the missing dependencies and run the script again.${NC}"
    exit 1
fi

# Check for python3-venv (common issue on Debian/Ubuntu)
if ! python3 -m venv --help &> /dev/null; then
    echo -e "${RED}[!] Error: python3-venv is not installed.${NC}"
    echo -e "${YELLOW}[*] Try: sudo apt install python3-venv${NC}"
    exit 1
fi

# Determine installation directory
# If we are already inside a git repo named Atlas, use current directory.
if [ -d ".git" ] && git remote -v 2>/dev/null | grep -q "Atlas"; then
    INSTALL_DIR="$(pwd)"
    echo -e "${YELLOW}[*] Detected Atlas repository in current directory.${NC}"
else
    INSTALL_DIR="$HOME/Atlas"
fi

if [ -d "$INSTALL_DIR" ]; then
    # If we are NOT in the directory already, ask to update
    if [ "$INSTALL_DIR" != "$(pwd)" ]; then
        echo -e "${YELLOW}[!] Directory $INSTALL_DIR already exists.${NC}"
        printf "${CYAN}[?] Do you want to update the existing installation? (y/n): ${NC}"
        read -r choice
        if [[ "$choice" =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}[*] Updating Atlas in $INSTALL_DIR...${NC}"
            cd "$INSTALL_DIR"
            if [ -d ".git" ]; then
                git pull
            else
                echo -e "${RED}[!] Error: $INSTALL_DIR exists but is not a git repository.${NC}"
                echo -e "${YELLOW}[*] Please remove or rename $INSTALL_DIR to continue installation.${NC}"
                exit 1
            fi
        else
            echo -e "${RED}[!] Installation aborted.${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}[*] Cloning Atlas repository to $INSTALL_DIR...${NC}"
    git clone https://github.com/atlasproject/Atlas.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Set up virtual environment
echo -e "${YELLOW}[*] Creating virtual environment...${NC}"
python3 -m venv venv

# Install dependencies
echo -e "${YELLOW}[*] Installing dependencies...${NC}"
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -e .

# Create symlink for global access
echo -e "${YELLOW}[*] Configuring global 'atlas' command...${NC}"
ATLAS_BIN="$INSTALL_DIR/venv/bin/atlas"
DEST_BIN="/usr/local/bin/atlas"

# Check if a command named atlas already exists in PATH
EXISTING_ATLAS=$(which atlas 2>/dev/null || true)

if [ -w "/usr/local/bin" ]; then
    ln -sf "$ATLAS_BIN" "$DEST_BIN"
    echo -e "${GREEN}[+] Symlink created at $DEST_BIN${NC}"
else
    if [ -n "$EXISTING_ATLAS" ] && [ "$EXISTING_ATLAS" != "$ATLAS_BIN" ]; then
        echo -e "${YELLOW}[!] Conflict: 'atlas' already exists at $EXISTING_ATLAS${NC}"
        if [ -L "$EXISTING_ATLAS" ]; then
             echo -e "${YELLOW}[!] It points to: $(readlink -f "$EXISTING_ATLAS")${NC}"
        fi
    fi

    echo -e "${YELLOW}[!] /usr/local/bin is not writable without sudo.${NC}"
    printf "${CYAN}[?] Do you want to use sudo to create/fix the symlink? (y/n): ${NC}"
    read -r sudo_choice
    if [[ "$sudo_choice" =~ ^[Yy]$ ]]; then
        sudo ln -sf "$ATLAS_BIN" "$DEST_BIN"
        echo -e "${GREEN}[+] Symlink created/updated at $DEST_BIN${NC}"
    else
        echo -e "${YELLOW}[!] Skipping symlink creation.${NC}"
        echo -e "${YELLOW}[*] To run atlas, use: $ATLAS_BIN${NC}"
        echo -e "${YELLOW}[*] Or manually run: sudo ln -sf $ATLAS_BIN $DEST_BIN${NC}"
    fi
fi

# Set up .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[*] Setting up configuration...${NC}"
    cat <<EOF > .env
# Atlas AI Configuration File
# Add your API keys below

GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
TELEGRAM_BOT_TOKEN=
EOF
    echo -e "${GREEN}[+] Created .env file template at $INSTALL_DIR/.env${NC}"
fi

# Optional: Ask for API key immediately
if [ -f ".env" ] && grep -q "GOOGLE_API_KEY=$" .env; then
    printf "${CYAN}[?] Would you like to enter a Google API Key now? (y/n): ${NC}"
    read -r key_choice
    if [[ "$key_choice" =~ ^[Yy]$ ]]; then
        printf "${CYAN}[>] Enter your Google API Key: ${NC}"
        read -r api_key
        if [ -n "$api_key" ]; then
            sed -i "s/GOOGLE_API_KEY=/GOOGLE_API_KEY=$api_key/" .env
            echo -e "${GREEN}[+] API Key saved.${NC}"
        fi
    fi
fi

echo -e "${GREEN}"
echo "       Atlas has been installed successfully!       "
echo -e "${NC}"
echo -e "Usage:"
echo -e "  - Type ${CYAN}'atlas'${NC} from anywhere to start."
echo -e "  - Configuration: ${CYAN}$INSTALL_DIR/.env${NC}"
echo ""
echo -e "${YELLOW}Happy Hacking!${NC}"
