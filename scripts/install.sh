#!/usr/bin/env bash
#
# AgentSH Universal Installer
#
# Usage:
#   curl -fsSL https://get.agentsh.dev | bash
#   wget -qO- https://get.agentsh.dev | bash
#
# Options (via environment variables):
#   AGENTSH_VERSION     - Specific version to install (default: latest)
#   AGENTSH_INSTALL_DIR - Installation directory (default: ~/.local/bin or /usr/local/bin)
#   AGENTSH_NO_MODIFY_PATH - Don't modify PATH in shell rc files
#   AGENTSH_SET_DEFAULT_SHELL - Set as default shell after install
#
# Examples:
#   curl -fsSL https://get.agentsh.dev | bash
#   curl -fsSL https://get.agentsh.dev | AGENTSH_VERSION=0.2.0 bash
#   curl -fsSL https://get.agentsh.dev | AGENTSH_SET_DEFAULT_SHELL=1 bash
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="agentsh/agentsh"
PYPI_PACKAGE="agentsh"
MIN_PYTHON_VERSION="3.10"

# Detect options from environment
VERSION="${AGENTSH_VERSION:-latest}"
INSTALL_DIR="${AGENTSH_INSTALL_DIR:-}"
NO_MODIFY_PATH="${AGENTSH_NO_MODIFY_PATH:-0}"
SET_DEFAULT_SHELL="${AGENTSH_SET_DEFAULT_SHELL:-0}"

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# -----------------------------------------------------------------------------
# System Detection
# -----------------------------------------------------------------------------

detect_os() {
    local os=""
    case "$(uname -s)" in
        Linux*)     os="linux";;
        Darwin*)    os="macos";;
        CYGWIN*|MINGW*|MSYS*) os="windows";;
        FreeBSD*)   os="freebsd";;
        *)          os="unknown";;
    esac
    echo "$os"
}

detect_arch() {
    local arch=""
    case "$(uname -m)" in
        x86_64|amd64)   arch="x86_64";;
        aarch64|arm64)  arch="aarch64";;
        armv7l)         arch="armv7";;
        i386|i686)      arch="i686";;
        *)              arch="unknown";;
    esac
    echo "$arch"
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "${ID:-unknown}"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "rhel"
    elif command_exists sw_vers; then
        echo "macos"
    else
        echo "unknown"
    fi
}

detect_package_manager() {
    if command_exists brew; then
        echo "brew"
    elif command_exists apt-get; then
        echo "apt"
    elif command_exists dnf; then
        echo "dnf"
    elif command_exists yum; then
        echo "yum"
    elif command_exists pacman; then
        echo "pacman"
    elif command_exists apk; then
        echo "apk"
    elif command_exists zypper; then
        echo "zypper"
    elif command_exists pkg; then
        echo "pkg"
    else
        echo "none"
    fi
}

detect_shell() {
    basename "${SHELL:-/bin/sh}"
}

# -----------------------------------------------------------------------------
# Python Detection and Installation
# -----------------------------------------------------------------------------

get_python_version() {
    local python_cmd="$1"
    "$python_cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0"
}

version_ge() {
    # Returns 0 if $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

find_python() {
    local candidates=("python3" "python" "python3.12" "python3.11" "python3.10")

    for cmd in "${candidates[@]}"; do
        if command_exists "$cmd"; then
            local version
            version=$(get_python_version "$cmd")
            if version_ge "$version" "$MIN_PYTHON_VERSION"; then
                echo "$cmd"
                return 0
            fi
        fi
    done

    return 1
}

install_python() {
    local pkg_manager="$1"

    info "Installing Python..."

    case "$pkg_manager" in
        brew)
            brew install python@3.11
            ;;
        apt)
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
            ;;
        dnf|yum)
            sudo "$pkg_manager" install -y python3 python3-pip
            ;;
        pacman)
            sudo pacman -Sy --noconfirm python python-pip
            ;;
        apk)
            sudo apk add --no-cache python3 py3-pip
            ;;
        zypper)
            sudo zypper install -y python3 python3-pip
            ;;
        *)
            die "Cannot install Python automatically. Please install Python $MIN_PYTHON_VERSION+ manually."
            ;;
    esac
}

# -----------------------------------------------------------------------------
# Installation Methods
# -----------------------------------------------------------------------------

install_via_brew() {
    info "Installing via Homebrew..."

    # Check if our tap exists
    if brew tap | grep -q "agentsh/tap"; then
        brew update
    else
        brew tap agentsh/tap || true
    fi

    if brew install agentsh 2>/dev/null; then
        return 0
    fi

    # Fallback to pip if homebrew formula not available
    warn "Homebrew formula not found, falling back to pip installation"
    return 1
}

install_via_apt() {
    info "Installing via APT..."

    # Add repository if available
    if curl -fsSL "https://pkg.agentsh.dev/gpg.key" 2>/dev/null | sudo gpg --dearmor -o /usr/share/keyrings/agentsh-archive-keyring.gpg 2>/dev/null; then
        echo "deb [signed-by=/usr/share/keyrings/agentsh-archive-keyring.gpg] https://pkg.agentsh.dev/apt stable main" | \
            sudo tee /etc/apt/sources.list.d/agentsh.list > /dev/null
        sudo apt-get update
        if sudo apt-get install -y agentsh; then
            return 0
        fi
    fi

    warn "APT repository not available, falling back to pip installation"
    return 1
}

install_via_dnf() {
    info "Installing via DNF..."

    # Add repository if available
    if sudo curl -fsSL "https://pkg.agentsh.dev/rpm/agentsh.repo" -o /etc/yum.repos.d/agentsh.repo 2>/dev/null; then
        if sudo dnf install -y agentsh; then
            return 0
        fi
    fi

    warn "DNF repository not available, falling back to pip installation"
    return 1
}

install_via_pacman() {
    info "Installing via pacman..."

    # Check AUR helpers
    if command_exists yay; then
        if yay -S --noconfirm agentsh 2>/dev/null; then
            return 0
        fi
    elif command_exists paru; then
        if paru -S --noconfirm agentsh 2>/dev/null; then
            return 0
        fi
    fi

    warn "AUR package not available, falling back to pip installation"
    return 1
}

install_via_pip() {
    local python_cmd="$1"

    info "Installing via pip..."

    # Determine install location
    local pip_args=("--upgrade")

    if [[ -z "$INSTALL_DIR" ]]; then
        # Check if we can install to user site-packages
        if [[ -w "$("$python_cmd" -m site --user-base 2>/dev/null)/bin" ]] || [[ ! -d "$("$python_cmd" -m site --user-base 2>/dev/null)/bin" ]]; then
            pip_args+=("--user")
            INSTALL_DIR="$("$python_cmd" -m site --user-base)/bin"
        else
            # Try system install
            INSTALL_DIR="/usr/local/bin"
        fi
    fi

    # Install package
    local pkg_spec="$PYPI_PACKAGE"
    if [[ "$VERSION" != "latest" ]]; then
        pkg_spec="${PYPI_PACKAGE}==${VERSION}"
    fi

    if [[ " ${pip_args[*]} " =~ " --user " ]]; then
        "$python_cmd" -m pip install "${pip_args[@]}" "$pkg_spec"
    else
        sudo "$python_cmd" -m pip install "${pip_args[@]}" "$pkg_spec"
    fi

    return 0
}

install_via_pipx() {
    info "Installing via pipx..."

    local pkg_spec="$PYPI_PACKAGE"
    if [[ "$VERSION" != "latest" ]]; then
        pkg_spec="${PYPI_PACKAGE}==${VERSION}"
    fi

    pipx install "$pkg_spec" --force
    INSTALL_DIR="$HOME/.local/bin"

    return 0
}

install_via_uv() {
    info "Installing via uv..."

    local pkg_spec="$PYPI_PACKAGE"
    if [[ "$VERSION" != "latest" ]]; then
        pkg_spec="${PYPI_PACKAGE}==${VERSION}"
    fi

    uv tool install "$pkg_spec" --force
    INSTALL_DIR="$HOME/.local/bin"

    return 0
}

# -----------------------------------------------------------------------------
# Post-Installation
# -----------------------------------------------------------------------------

get_shell_rc_file() {
    local shell="$1"
    case "$shell" in
        bash)
            if [[ -f "$HOME/.bash_profile" ]]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        zsh)
            echo "$HOME/.zshrc"
            ;;
        fish)
            echo "$HOME/.config/fish/config.fish"
            ;;
        *)
            echo "$HOME/.profile"
            ;;
    esac
}

add_to_path() {
    local install_dir="$1"
    local shell
    shell=$(detect_shell)
    local rc_file
    rc_file=$(get_shell_rc_file "$shell")

    # Check if already in PATH
    if [[ ":$PATH:" == *":$install_dir:"* ]]; then
        return 0
    fi

    # Check if rc file already has the path
    if [[ -f "$rc_file" ]] && grep -q "$install_dir" "$rc_file" 2>/dev/null; then
        return 0
    fi

    info "Adding $install_dir to PATH in $rc_file"

    local path_line=""
    case "$shell" in
        fish)
            path_line="set -gx PATH \"$install_dir\" \$PATH"
            ;;
        *)
            path_line="export PATH=\"$install_dir:\$PATH\""
            ;;
    esac

    # Create rc file directory if needed (for fish)
    mkdir -p "$(dirname "$rc_file")"

    # Add to rc file
    echo "" >> "$rc_file"
    echo "# Added by AgentSH installer" >> "$rc_file"
    echo "$path_line" >> "$rc_file"

    success "Added to PATH. Run 'source $rc_file' or start a new terminal."
}

add_to_shells() {
    local agentsh_path="$1"

    if [[ ! -f /etc/shells ]]; then
        warn "/etc/shells not found, skipping shell registration"
        return 1
    fi

    if grep -q "^${agentsh_path}$" /etc/shells 2>/dev/null; then
        info "AgentSH already in /etc/shells"
        return 0
    fi

    info "Adding AgentSH to /etc/shells (requires sudo)..."
    echo "$agentsh_path" | sudo tee -a /etc/shells > /dev/null
    success "Added to /etc/shells"
}

set_default_shell() {
    local agentsh_path="$1"

    if ! grep -q "^${agentsh_path}$" /etc/shells 2>/dev/null; then
        error "AgentSH not in /etc/shells, cannot set as default"
        return 1
    fi

    info "Setting AgentSH as default shell..."
    chsh -s "$agentsh_path"
    success "Default shell changed to AgentSH"
}

verify_installation() {
    local agentsh_path="$1"

    if [[ ! -x "$agentsh_path" ]]; then
        # Try to find it
        agentsh_path=$(command -v agentsh 2>/dev/null || echo "")
    fi

    if [[ -z "$agentsh_path" ]] || [[ ! -x "$agentsh_path" ]]; then
        error "Installation verification failed: agentsh not found"
        return 1
    fi

    local version
    version=$("$agentsh_path" --version 2>/dev/null || echo "unknown")

    success "AgentSH installed successfully!"
    echo ""
    echo -e "  ${CYAN}Version:${NC}  $version"
    echo -e "  ${CYAN}Location:${NC} $agentsh_path"
    echo ""

    return 0
}

# -----------------------------------------------------------------------------
# Main Installation Logic
# -----------------------------------------------------------------------------

print_banner() {
    echo -e "${MAGENTA}"
    cat << 'EOF'
    ___                    __  _____ __ __
   /   | ____ ____  ____  / /_/ ___// // /
  / /| |/ __ `/ _ \/ __ \/ __/\__ \/ // /_
 / ___ / /_/ /  __/ / / / /_ ___/ /__  __/
/_/  |_\__, /\___/_/ /_/\__//____/  /_/
      /____/
EOF
    echo -e "${NC}"
    echo -e "${BOLD}AI-Enhanced Terminal Shell${NC}"
    echo ""
}

main() {
    print_banner

    # Detect system
    local os arch distro pkg_manager
    os=$(detect_os)
    arch=$(detect_arch)
    distro=$(detect_distro)
    pkg_manager=$(detect_package_manager)

    info "Detected: $os ($arch) - $distro - package manager: $pkg_manager"

    # Check for unsupported platforms
    if [[ "$os" == "windows" ]]; then
        die "Windows is not fully supported. Please use WSL2 or see docs for Windows installation."
    fi

    if [[ "$os" == "unknown" ]]; then
        die "Unknown operating system. Please install manually."
    fi

    # Find or install Python
    local python_cmd
    python_cmd=$(find_python) || true

    if [[ -z "$python_cmd" ]]; then
        warn "Python $MIN_PYTHON_VERSION+ not found"

        if [[ "$pkg_manager" != "none" ]]; then
            read -p "Install Python automatically? [Y/n] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                install_python "$pkg_manager"
                python_cmd=$(find_python) || die "Failed to install Python"
            else
                die "Python $MIN_PYTHON_VERSION+ is required"
            fi
        else
            die "Python $MIN_PYTHON_VERSION+ is required. Please install it manually."
        fi
    fi

    info "Using Python: $python_cmd ($(get_python_version "$python_cmd"))"

    # Try installation methods in order of preference
    local installed=false

    # 1. Try native package manager first
    case "$pkg_manager" in
        brew)
            install_via_brew && installed=true
            ;;
        apt)
            install_via_apt && installed=true
            ;;
        dnf|yum)
            install_via_dnf && installed=true
            ;;
        pacman)
            install_via_pacman && installed=true
            ;;
    esac

    # 2. Try modern Python installers
    if [[ "$installed" != "true" ]]; then
        if command_exists uv; then
            install_via_uv && installed=true
        elif command_exists pipx; then
            install_via_pipx && installed=true
        fi
    fi

    # 3. Fall back to pip
    if [[ "$installed" != "true" ]]; then
        install_via_pip "$python_cmd" && installed=true
    fi

    if [[ "$installed" != "true" ]]; then
        die "All installation methods failed"
    fi

    # Find the installed binary
    local agentsh_path=""
    if [[ -n "$INSTALL_DIR" ]] && [[ -x "$INSTALL_DIR/agentsh" ]]; then
        agentsh_path="$INSTALL_DIR/agentsh"
    else
        agentsh_path=$(command -v agentsh 2>/dev/null || echo "")
    fi

    # Add to PATH if needed
    if [[ "$NO_MODIFY_PATH" != "1" ]] && [[ -n "$INSTALL_DIR" ]]; then
        add_to_path "$INSTALL_DIR"
    fi

    # Verify installation
    # Add install dir to current PATH for verification
    if [[ -n "$INSTALL_DIR" ]]; then
        export PATH="$INSTALL_DIR:$PATH"
    fi

    verify_installation "$agentsh_path" || die "Installation verification failed"

    # Add to /etc/shells
    if [[ -n "$agentsh_path" ]]; then
        agentsh_path=$(command -v agentsh)  # Get absolute path
        add_to_shells "$agentsh_path" || true

        # Set as default shell if requested
        if [[ "$SET_DEFAULT_SHELL" == "1" ]]; then
            set_default_shell "$agentsh_path"
        fi
    fi

    # Print next steps
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Start AgentSH:     agentsh"
    echo "  2. Configure:         agentsh config init"
    echo "  3. Check status:      agentsh status"
    echo ""
    echo -e "  Set as default shell: ${CYAN}chsh -s $(command -v agentsh)${NC}"
    echo ""
    echo -e "Documentation: ${CYAN}https://github.com/$GITHUB_REPO${NC}"
    echo ""
}

# Run main function
main "$@"
