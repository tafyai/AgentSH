#!/bin/bash
# AgentSH Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/tafyai/AgentSH/main/scripts/install.sh | bash

set -e

REPO="tafyai/AgentSH"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
CONFIG_DIR="$HOME/.aishell"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Detect OS and architecture
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    case "$OS" in
        linux)
            case "$ARCH" in
                x86_64) PLATFORM="linux-x86_64" ;;
                aarch64|arm64) PLATFORM="linux-aarch64" ;;
                *) error "Unsupported architecture: $ARCH" ;;
            esac
            ;;
        darwin)
            case "$ARCH" in
                x86_64) PLATFORM="macos-x86_64" ;;
                arm64) PLATFORM="macos-aarch64" ;;
                *) error "Unsupported architecture: $ARCH" ;;
            esac
            ;;
        *)
            error "Unsupported OS: $OS"
            ;;
    esac
    
    info "Detected platform: $PLATFORM"
}

# Check for required tools
check_requirements() {
    for cmd in curl tar; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd is required but not installed"
        fi
    done
}

# Get latest release version
get_latest_version() {
    VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$VERSION" ]; then
        warn "Could not fetch latest version, using 'main'"
        VERSION="main"
    fi
    info "Latest version: $VERSION"
}

# Download and install
install_binary() {
    info "Installing to $INSTALL_DIR..."
    
    # Create install directory if needed
    mkdir -p "$INSTALL_DIR"
    
    # For now, build from source since we don't have releases yet
    if command -v cargo &> /dev/null; then
        info "Building from source..."
        TEMP_DIR=$(mktemp -d)
        cd "$TEMP_DIR"
        git clone --depth 1 "https://github.com/$REPO.git" agentsh
        cd agentsh
        cargo build --release
        cp target/release/agentsh "$INSTALL_DIR/"
        cd /
        rm -rf "$TEMP_DIR"
    else
        error "Rust/Cargo is required. Install from https://rustup.rs"
    fi
    
    chmod +x "$INSTALL_DIR/agentsh"
    info "Installed agentsh to $INSTALL_DIR/agentsh"
}

# Create default config
setup_config() {
    if [ ! -d "$CONFIG_DIR" ]; then
        info "Creating config directory..."
        mkdir -p "$CONFIG_DIR"
        mkdir -p "$CONFIG_DIR/logs"
        mkdir -p "$CONFIG_DIR/plugins"
        
        # Create default config
        cat > "$CONFIG_DIR/config.toml" << 'CONFIGEOF'
# AgentSH Configuration
# See https://github.com/tafyai/AgentSH for documentation

[ai]
provider = "openai"
model = "gpt-4"
# Set your API key via environment variable:
# export OPENAI_API_KEY=your-key-here

[mode]
default = "assist"

[safety]
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
log_ai_generated_commands = true
CONFIGEOF
        
        info "Created default config at $CONFIG_DIR/config.toml"
    else
        info "Config directory already exists"
    fi
}

# Add to PATH if needed
setup_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        warn "Add $INSTALL_DIR to your PATH:"
        echo ""
        echo "  # Add to ~/.bashrc or ~/.zshrc:"
        echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
        echo ""
    fi
}

# Main installation
main() {
    echo ""
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║     AgentSH Installation Script       ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo ""
    
    check_requirements
    detect_platform
    get_latest_version
    install_binary
    setup_config
    setup_path
    
    echo ""
    info "Installation complete!"
    echo ""
    echo "  To get started:"
    echo "    1. Set your API key: export OPENAI_API_KEY=your-key"
    echo "    2. Run: agentsh"
    echo "    3. Try: ai help"
    echo ""
}

main "$@"
