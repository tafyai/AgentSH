# AgentSH Windows Installation

AgentSH supports Windows through Python installation. For the best experience, we recommend using WSL2 (Windows Subsystem for Linux).

## Quick Install (PowerShell)

```powershell
irm https://get.agentsh.dev/windows | iex
```

Or with execution policy bypass:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://get.agentsh.dev/windows'))
```

## Manual Installation

### Prerequisites

1. **Python 3.10+**
   ```powershell
   # Via winget (Windows 10/11)
   winget install Python.Python.3.11

   # Via Chocolatey
   choco install python311

   # Via Scoop
   scoop install python
   ```

2. **pip** (included with Python)

### Install AgentSH

```powershell
# Via pip
pip install agentsh

# Via pipx (recommended for isolation)
pip install pipx
pipx install agentsh

# Via uv (fastest)
pip install uv
uv tool install agentsh
```

## WSL2 (Recommended)

For the best experience with full PTY support and Unix-style shell features:

1. **Install WSL2**
   ```powershell
   wsl --install
   ```

2. **Install AgentSH in WSL**
   ```bash
   curl -fsSL https://get.agentsh.dev | bash
   ```

## Windows Terminal

For best results, use [Windows Terminal](https://github.com/microsoft/terminal) which provides:
- Full color support
- Better PTY handling
- Multiple shell tabs
- Customizable appearance

Install via:
```powershell
winget install Microsoft.WindowsTerminal
```

## Configuration

AgentSH stores configuration in:
- `%USERPROFILE%\.config\agentsh\config.yaml`
- `%APPDATA%\agentsh\config.yaml`

Set your API key:
```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
# Or configure permanently:
agentsh config init
```

## Known Limitations on Windows

1. **No login shell support** - Windows doesn't use `/etc/shells` or `chsh`
2. **Limited PTY support** - Some interactive features may not work as expected
3. **Path handling** - Paths use backslashes, though AgentSH handles both

## Troubleshooting

### "agentsh is not recognized"

Add Python Scripts to PATH:
```powershell
$env:Path += ";$env:USERPROFILE\AppData\Local\Programs\Python\Python311\Scripts"
```

### Permission Denied

Run PowerShell as Administrator, or use `--user` flag:
```powershell
pip install --user agentsh
```

### SSL Certificate Errors

Update certificates:
```powershell
pip install --upgrade certifi
```
