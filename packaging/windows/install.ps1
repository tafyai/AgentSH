# AgentSH Windows Installer
#
# Usage (PowerShell):
#   irm https://get.agentsh.dev/windows | iex
#
# Or:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
#   iex ((New-Object System.Net.WebClient).DownloadString('https://get.agentsh.dev/windows'))

param(
    [string]$Version = "latest",
    [string]$InstallDir = "",
    [switch]$NoPath,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Configuration
$GITHUB_REPO = "agentsh/agentsh"
$PYPI_PACKAGE = "agentsh"
$MIN_PYTHON_VERSION = [Version]"3.10"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    $input | ForEach-Object { Write-Output $_ }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Info($msg) {
    Write-Host "==> " -ForegroundColor Blue -NoNewline
    Write-Host $msg -ForegroundColor White
}

function Success($msg) {
    Write-Host "==> " -ForegroundColor Green -NoNewline
    Write-Host $msg -ForegroundColor White
}

function Warn($msg) {
    Write-Host "Warning: " -ForegroundColor Yellow -NoNewline
    Write-Host $msg -ForegroundColor White
}

function Error($msg) {
    Write-Host "Error: " -ForegroundColor Red -NoNewline
    Write-Host $msg -ForegroundColor White
}

# Check if running as Administrator
function Test-Admin {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Find Python installation
function Find-Python {
    $pythonCommands = @("python3", "python", "py")

    foreach ($cmd in $pythonCommands) {
        try {
            $version = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($version) {
                $ver = [Version]$version
                if ($ver -ge $MIN_PYTHON_VERSION) {
                    return $cmd
                }
            }
        } catch {
            # Command not found, continue
        }
    }

    # Try py launcher with version
    try {
        $version = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($version) {
            $ver = [Version]$version
            if ($ver -ge $MIN_PYTHON_VERSION) {
                return "py -3"
            }
        }
    } catch {}

    return $null
}

# Install Python via winget
function Install-Python {
    Info "Installing Python..."

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements
        return $true
    }

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install python311 -y
        return $true
    }

    if (Get-Command scoop -ErrorAction SilentlyContinue) {
        scoop install python
        return $true
    }

    Error "Cannot install Python automatically. Please install Python 3.10+ manually from https://python.org"
    return $false
}

# Install AgentSH via pip
function Install-AgentSH {
    param([string]$PythonCmd)

    Info "Installing AgentSH..."

    $pkgSpec = $PYPI_PACKAGE
    if ($Version -ne "latest") {
        $pkgSpec = "${PYPI_PACKAGE}==$Version"
    }

    # Try pipx first
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        Info "Installing via pipx..."
        pipx install $pkgSpec --force
        return $true
    }

    # Try uv
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Info "Installing via uv..."
        uv tool install $pkgSpec --force
        return $true
    }

    # Fall back to pip
    Info "Installing via pip..."
    if ($PythonCmd -eq "py -3") {
        & py -3 -m pip install --upgrade $pkgSpec
    } else {
        & $PythonCmd -m pip install --upgrade $pkgSpec
    }

    return $LASTEXITCODE -eq 0
}

# Add to PATH
function Add-ToPath {
    param([string]$Dir)

    if ($NoPath) {
        return
    }

    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$Dir*") {
        Info "Adding $Dir to PATH..."
        [Environment]::SetEnvironmentVariable("Path", "$Dir;$currentPath", "User")
        $env:Path = "$Dir;$env:Path"
        Success "Added to PATH. Restart your terminal to apply."
    }
}

# Verify installation
function Test-Installation {
    try {
        $version = & agentsh --version 2>$null
        if ($version) {
            Success "AgentSH installed successfully!"
            Write-Host ""
            Write-Host "  Version:  $version" -ForegroundColor Cyan
            Write-Host "  Location: $(Get-Command agentsh | Select-Object -ExpandProperty Source)" -ForegroundColor Cyan
            Write-Host ""
            return $true
        }
    } catch {}

    # Check common locations
    $locations = @(
        "$env:USERPROFILE\.local\bin\agentsh.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\Scripts\agentsh.exe",
        "$env:USERPROFILE\AppData\Roaming\Python\Python311\Scripts\agentsh.exe"
    )

    foreach ($loc in $locations) {
        if (Test-Path $loc) {
            $dir = Split-Path $loc -Parent
            Add-ToPath $dir
            Success "AgentSH installed to $loc"
            Warn "Restart your terminal and run 'agentsh' to start."
            return $true
        }
    }

    return $false
}

# Print banner
function Print-Banner {
    Write-Host @"

    ___                    __  _____ __ __
   /   | ____ ____  ____  / /_/ ___// // /
  / /| |/ __ `/ _ \/ __ \/ __/\__ \/ // /_
 / ___ / /_/ /  __/ / / / /_ ___/ /__  __/
/_/  |_\__, /\___/_/ /_/\__//____/  /_/
      /____/

"@ -ForegroundColor Magenta
    Write-Host "AI-Enhanced Terminal Shell" -ForegroundColor White
    Write-Host ""
}

# Main function
function Main {
    Print-Banner

    # Check for WSL recommendation
    Info "Detected: Windows"
    Warn "For the best experience, consider using Windows Subsystem for Linux (WSL2)."
    Write-Host ""

    # Find or install Python
    $pythonCmd = Find-Python
    if (-not $pythonCmd) {
        Warn "Python $MIN_PYTHON_VERSION+ not found."

        $response = Read-Host "Install Python automatically? [Y/n]"
        if ($response -ne "n" -and $response -ne "N") {
            if (-not (Install-Python)) {
                exit 1
            }
            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            $pythonCmd = Find-Python
            if (-not $pythonCmd) {
                Error "Failed to install Python. Please install manually."
                exit 1
            }
        } else {
            Error "Python $MIN_PYTHON_VERSION+ is required."
            exit 1
        }
    }

    $pyVersion = if ($pythonCmd -eq "py -3") {
        & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    } else {
        & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    }
    Info "Using Python: $pythonCmd ($pyVersion)"

    # Install AgentSH
    if (-not (Install-AgentSH -PythonCmd $pythonCmd)) {
        Error "Installation failed."
        exit 1
    }

    # Verify installation
    if (-not (Test-Installation)) {
        Error "Installation verification failed."
        exit 1
    }

    # Print next steps
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Start AgentSH:     agentsh" -ForegroundColor Gray
    Write-Host "  2. Configure:         agentsh config init" -ForegroundColor Gray
    Write-Host "  3. Check status:      agentsh status" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Documentation: https://github.com/$GITHUB_REPO" -ForegroundColor Cyan
    Write-Host ""
}

# Run
Main
