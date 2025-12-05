#!/usr/bin/env bash
#
# AgentSH Login Shell Installer
#
# This script configures AgentSH as a valid login shell:
# 1. Adds AgentSH to /etc/shells
# 2. Optionally sets it as the default shell for the current user
# 3. Creates initial ~/.agentshrc configuration
#
# Usage:
#   ./install-login-shell.sh              # Just add to /etc/shells
#   ./install-login-shell.sh --set-default # Also set as default shell
#   ./install-login-shell.sh --uninstall   # Remove from /etc/shells
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info() {
    echo -e "${BLUE}==>${NC} ${BOLD}$1${NC}"
}

success() {
    echo -e "${GREEN}==>${NC} ${BOLD}$1${NC}"
}

warn() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

error() {
    echo -e "${RED}Error:${NC} $1" >&2
}

die() {
    error "$1"
    exit 1
}

# Find AgentSH binary
find_agentsh() {
    local agentsh_path=""

    # Check common locations
    if command -v agentsh >/dev/null 2>&1; then
        agentsh_path=$(command -v agentsh)
    elif [[ -x "$HOME/.local/bin/agentsh" ]]; then
        agentsh_path="$HOME/.local/bin/agentsh"
    elif [[ -x "/usr/local/bin/agentsh" ]]; then
        agentsh_path="/usr/local/bin/agentsh"
    elif [[ -x "/usr/bin/agentsh" ]]; then
        agentsh_path="/usr/bin/agentsh"
    fi

    # Resolve symlinks to get absolute path
    if [[ -n "$agentsh_path" ]]; then
        # Use readlink if available, otherwise realpath
        if command -v readlink >/dev/null 2>&1; then
            agentsh_path=$(readlink -f "$agentsh_path" 2>/dev/null || echo "$agentsh_path")
        elif command -v realpath >/dev/null 2>&1; then
            agentsh_path=$(realpath "$agentsh_path" 2>/dev/null || echo "$agentsh_path")
        fi
    fi

    echo "$agentsh_path"
}

# Check if AgentSH is in /etc/shells
is_in_shells() {
    local agentsh_path="$1"
    grep -q "^${agentsh_path}$" /etc/shells 2>/dev/null
}

# Add AgentSH to /etc/shells
add_to_shells() {
    local agentsh_path="$1"

    if is_in_shells "$agentsh_path"; then
        info "AgentSH already in /etc/shells"
        return 0
    fi

    info "Adding AgentSH to /etc/shells..."
    echo "$agentsh_path" | sudo tee -a /etc/shells >/dev/null
    success "Added to /etc/shells"
}

# Remove AgentSH from /etc/shells
remove_from_shells() {
    local agentsh_path="$1"

    if ! is_in_shells "$agentsh_path"; then
        info "AgentSH not in /etc/shells"
        return 0
    fi

    info "Removing AgentSH from /etc/shells..."
    sudo sed -i.bak "\|^${agentsh_path}$|d" /etc/shells
    success "Removed from /etc/shells"
}

# Set AgentSH as default shell
set_default_shell() {
    local agentsh_path="$1"

    if ! is_in_shells "$agentsh_path"; then
        die "AgentSH must be in /etc/shells before setting as default"
    fi

    info "Setting AgentSH as default shell..."
    chsh -s "$agentsh_path"
    success "Default shell changed to AgentSH"
}

# Restore original shell
restore_shell() {
    local original_shell="${SHELL:-/bin/bash}"

    # Common shells to try
    local shells=("$original_shell" "/bin/bash" "/bin/zsh" "/bin/sh")

    for shell in "${shells[@]}"; do
        if [[ -x "$shell" ]] && grep -q "^${shell}$" /etc/shells 2>/dev/null; then
            info "Restoring shell to $shell..."
            chsh -s "$shell"
            success "Shell restored to $shell"
            return 0
        fi
    done

    warn "Could not restore shell. Please run: chsh -s /bin/bash"
}

# Create default ~/.agentshrc
create_agentshrc() {
    local rc_file="$HOME/.agentshrc"

    if [[ -f "$rc_file" ]]; then
        info "~/.agentshrc already exists"
        return 0
    fi

    info "Creating ~/.agentshrc..."
    cat > "$rc_file" << 'EOF'
# AgentSH Configuration File
# This file is sourced when AgentSH starts in interactive mode.

# Aliases
# alias ll='ls -la'
# alias gs='git status'

# Environment variables for AgentSH
# export AGENTSH_LOG_LEVEL=INFO

# Custom prompt (optional)
# export AGENTSH_PROMPT_PREFIX="my-shell"

# Tool registration (advanced)
# :tool register my-tool "Description" "command"

# Welcome message (optional)
# echo "Welcome to AgentSH!"
EOF
    success "Created ~/.agentshrc"
}

# Check system requirements
check_requirements() {
    # Check /etc/shells exists
    if [[ ! -f /etc/shells ]]; then
        die "/etc/shells not found. This system may not support login shells."
    fi

    # Check if we can use sudo
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo not available. You may need to run this as root."
    fi

    # Check chsh
    if ! command -v chsh >/dev/null 2>&1; then
        warn "chsh not found. You won't be able to set AgentSH as default shell."
    fi
}

# Print usage
usage() {
    cat << EOF
AgentSH Login Shell Installer

Usage:
    $0 [options]

Options:
    --set-default    Set AgentSH as default shell
    --uninstall      Remove AgentSH from /etc/shells
    --restore        Restore original shell
    --help           Show this help message

Examples:
    $0                    # Add to /etc/shells only
    $0 --set-default      # Add and set as default
    $0 --uninstall        # Remove from /etc/shells
EOF
}

# Main
main() {
    local set_default=false
    local uninstall=false
    local restore=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --set-default)
                set_default=true
                shift
                ;;
            --uninstall)
                uninstall=true
                shift
                ;;
            --restore)
                restore=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    echo ""
    echo -e "${BOLD}AgentSH Login Shell Installer${NC}"
    echo ""

    check_requirements

    # Find AgentSH
    local agentsh_path
    agentsh_path=$(find_agentsh)

    if [[ -z "$agentsh_path" ]]; then
        die "AgentSH not found. Please install it first: pip install agentsh"
    fi

    info "Found AgentSH: $agentsh_path"

    # Verify it works
    if ! "$agentsh_path" --version >/dev/null 2>&1; then
        die "AgentSH binary not working properly"
    fi

    local version
    version=$("$agentsh_path" --version 2>/dev/null || echo "unknown")
    info "Version: $version"
    echo ""

    # Handle uninstall
    if $uninstall; then
        remove_from_shells "$agentsh_path"
        echo ""
        success "AgentSH removed from login shells"
        echo ""
        echo "Note: If AgentSH was your default shell, run:"
        echo "  chsh -s /bin/bash"
        exit 0
    fi

    # Handle restore
    if $restore; then
        restore_shell
        exit 0
    fi

    # Install
    add_to_shells "$agentsh_path"
    create_agentshrc

    # Set as default if requested
    if $set_default; then
        echo ""
        set_default_shell "$agentsh_path"
    fi

    echo ""
    success "Installation complete!"
    echo ""
    echo "AgentSH is now a valid login shell."
    echo ""
    echo "Next steps:"
    if ! $set_default; then
        echo "  - Set as default shell: chsh -s $agentsh_path"
    fi
    echo "  - Customize: vim ~/.agentshrc"
    echo "  - Start now: agentsh"
    echo ""

    # PAM notes
    echo -e "${BOLD}PAM Integration Notes:${NC}"
    echo "  - AgentSH uses standard exit codes for PAM compatibility"
    echo "  - Environment from /etc/environment and pam_env is loaded"
    echo "  - Resource limits from /etc/security/limits.conf are respected"
    echo ""

    # Sudo notes
    echo -e "${BOLD}Sudo Notes:${NC}"
    echo "  - 'sudo -s' will spawn AgentSH"
    echo "  - 'sudo -i' will run AgentSH as login shell"
    echo "  - Add AGENTSH env vars to /etc/sudoers Defaults env_keep if needed"
    echo ""
}

main "$@"
