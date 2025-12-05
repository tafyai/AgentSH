# AgentSH Packaging & Distribution

This directory contains packaging configurations for distributing AgentSH across various platforms and package managers.

## Quick Install

### Universal (curl/wget)

```bash
# curl
curl -fsSL https://get.agentsh.dev | bash

# wget
wget -qO- https://get.agentsh.dev | bash

# With options
curl -fsSL https://get.agentsh.dev | AGENTSH_VERSION=0.1.0 bash
curl -fsSL https://get.agentsh.dev | AGENTSH_SET_DEFAULT_SHELL=1 bash
```

### macOS (Homebrew)

```bash
brew tap agentsh/tap
brew install agentsh
```

### Debian/Ubuntu (APT)

```bash
curl -fsSL https://pkg.agentsh.dev/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/agentsh-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/agentsh-archive-keyring.gpg] https://pkg.agentsh.dev/apt stable main" | sudo tee /etc/apt/sources.list.d/agentsh.list
sudo apt update
sudo apt install agentsh
```

### Fedora/RHEL (DNF)

```bash
sudo curl -fsSL https://pkg.agentsh.dev/rpm/agentsh.repo -o /etc/yum.repos.d/agentsh.repo
sudo dnf install agentsh
```

### Arch Linux (AUR)

```bash
# Via yay
yay -S agentsh

# Via paru
paru -S agentsh

# Manual
git clone https://aur.archlinux.org/agentsh.git
cd agentsh
makepkg -si
```

### Alpine Linux

```bash
# Add repository
echo "https://pkg.agentsh.dev/alpine/edge/main" >> /etc/apk/repositories
apk update
apk add agentsh
```

### Python (pip/pipx/uv)

```bash
# pip (system)
pip install agentsh

# pipx (isolated)
pipx install agentsh

# uv (fastest)
uv tool install agentsh
```

### Docker

```bash
# Standard image
docker run -it --rm -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY ghcr.io/agentsh/agentsh

# Alpine (minimal)
docker run -it --rm -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY ghcr.io/agentsh/agentsh:alpine

# With Ollama (local LLM)
docker-compose up -d ollama agentsh-local
```

### Windows (PowerShell)

```powershell
irm https://get.agentsh.dev/windows | iex
```

## Package Contents

### `homebrew/`
- `agentsh.rb` - Homebrew formula for macOS

### `debian/`
- `control` - Package metadata
- `rules` - Build rules
- `changelog` - Version history
- `copyright` - License information
- `postinst` - Post-installation script (adds to /etc/shells)
- `postrm` - Post-removal script (removes from /etc/shells)

### `rpm/`
- `agentsh.spec` - RPM spec file for Fedora/RHEL/CentOS

### `arch/`
- `PKGBUILD` - Arch Linux build script
- `agentsh.install` - Install hooks

### `alpine/`
- `APKBUILD` - Alpine Linux build script

### `docker/`
- `Dockerfile` - Standard Debian-based image
- `Dockerfile.alpine` - Minimal Alpine image
- `Dockerfile.dev` - Development image
- `docker-compose.yml` - Multi-container setup with Ollama
- `docker-entrypoint.sh` - Container entrypoint

### `windows/`
- `install.ps1` - PowerShell installer
- `README.md` - Windows-specific instructions

## Building Packages

### Debian Package

```bash
# Install build dependencies
sudo apt install debhelper dh-python python3-all python3-setuptools

# Build
dpkg-buildpackage -us -uc -b
```

### RPM Package

```bash
# Install build dependencies
sudo dnf install rpm-build python3-devel python3-setuptools

# Build
rpmbuild -ba packaging/rpm/agentsh.spec
```

### Arch Package

```bash
cd packaging/arch
makepkg -s
```

### Docker Images

```bash
cd packaging/docker
docker build -t agentsh:latest -f Dockerfile ../..
docker build -t agentsh:alpine -f Dockerfile.alpine ../..
```

## Shell Completions

Shell completion scripts are installed automatically by package managers. For manual installation:

```bash
# Bash
cp completions/agentsh.bash /usr/share/bash-completion/completions/agentsh

# Zsh
cp completions/agentsh.zsh /usr/share/zsh/site-functions/_agentsh

# Fish
cp completions/agentsh.fish ~/.config/fish/completions/agentsh.fish
```

## Setting as Default Shell

After installation, AgentSH can be set as your default login shell:

```bash
# Add to /etc/shells (done automatically by packages)
echo "$(which agentsh)" | sudo tee -a /etc/shells

# Set as default
chsh -s $(which agentsh)
```

## Release Process

1. Update version in `pyproject.toml`
2. Update `packaging/debian/changelog`
3. Update `packaging/rpm/agentsh.spec` version
4. Update `packaging/arch/PKGBUILD` version
5. Update `packaging/alpine/APKBUILD` version
6. Build and test packages
7. Push to PyPI: `python -m build && twine upload dist/*`
8. Create GitHub release
9. Push to package repositories

## Infrastructure

For production deployment, set up:

1. **Package hosting** (pkg.agentsh.dev)
   - APT repository with GPG signing
   - RPM repository
   - Alpine repository

2. **Installer hosting** (get.agentsh.dev)
   - Redirect to `scripts/install.sh`
   - `/windows` redirect to `packaging/windows/install.ps1`

3. **Docker registry** (ghcr.io/agentsh/agentsh)
   - Multi-arch builds (amd64, arm64)
   - Tags: latest, alpine, dev, version numbers

4. **Homebrew tap** (github.com/agentsh/homebrew-tap)
   - Formula auto-updated on release
