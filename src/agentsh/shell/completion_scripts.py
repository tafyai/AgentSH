"""Shell completion script generation for AgentSH.

Generates completion scripts for bash, zsh, and fish that can be
installed for use when AgentSH is invoked as a command (not as a shell).
"""

import os
from pathlib import Path
from typing import Tuple

from agentsh import __version__


def get_bash_completion() -> str:
    """Generate bash completion script.

    Returns:
        Bash completion script content
    """
    return f'''# Bash completion for AgentSH v{__version__}
# Install: agentsh completions bash > /etc/bash_completion.d/agentsh
# Or: agentsh completions bash >> ~/.bashrc

_agentsh_completions() {{
    local cur prev words cword
    _init_completion || return

    local commands="config status completions devices help"
    local config_commands="init show edit reset"
    local devices_commands="list add remove status"
    local completions_shells="bash zsh fish"
    local global_opts="--help --version --config --log-level --login --norc --noprofile --rcfile --mcp-server --profile-startup"

    case "${{prev}}" in
        agentsh)
            COMPREPLY=($(compgen -W "${{commands}} ${{global_opts}}" -- "${{cur}}"))
            return
            ;;
        config)
            COMPREPLY=($(compgen -W "${{config_commands}}" -- "${{cur}}"))
            return
            ;;
        completions)
            COMPREPLY=($(compgen -W "${{completions_shells}}" -- "${{cur}}"))
            return
            ;;
        devices)
            COMPREPLY=($(compgen -W "${{devices_commands}}" -- "${{cur}}"))
            return
            ;;
        --config|--rcfile)
            _filedir
            return
            ;;
        --log-level)
            COMPREPLY=($(compgen -W "DEBUG INFO WARNING ERROR" -- "${{cur}}"))
            return
            ;;
        bash|zsh|fish)
            COMPREPLY=($(compgen -W "--install" -- "${{cur}}"))
            return
            ;;
    esac

    case "${{cur}}" in
        -*)
            COMPREPLY=($(compgen -W "${{global_opts}}" -- "${{cur}}"))
            return
            ;;
    esac

    # Default to file completion
    _filedir
}}

complete -F _agentsh_completions agentsh
'''


def get_zsh_completion() -> str:
    """Generate zsh completion script.

    Returns:
        Zsh completion script content
    """
    return f'''#compdef agentsh

# Zsh completion for AgentSH v{__version__}
# Install: agentsh completions zsh > /usr/share/zsh/site-functions/_agentsh
# Or: Place in a directory in your $fpath

_agentsh() {{
    local context state state_descr line
    typeset -A opt_args

    local -a commands
    commands=(
        'config:Manage configuration'
        'status:Show status'
        'completions:Generate shell completions'
        'devices:Device management'
        'help:Show help'
    )

    local -a config_commands
    config_commands=(
        'init:Initialize configuration'
        'show:Show current configuration'
        'edit:Edit configuration file'
        'reset:Reset to defaults'
    )

    local -a devices_commands
    devices_commands=(
        'list:List all devices'
        'add:Add a device'
        'remove:Remove a device'
        'status:Check device status'
    )

    local -a global_opts
    global_opts=(
        '--help[Show help message]'
        '--version[Show version]'
        '--config[Configuration file]:file:_files -g "*.yaml"'
        '--log-level[Log level]:level:(DEBUG INFO WARNING ERROR)'
        '(-l --login)'{{'{{-l,--login}}'}}'[Run as login shell]'
        '--norc[Skip rc files]'
        '--noprofile[Skip profile files]'
        '--rcfile[Custom RC file]:file:_files'
        '--mcp-server[Run as MCP server]'
        '--profile-startup[Profile startup time]'
    )

    _arguments -C \\
        "${{global_opts[@]}}" \\
        '1: :->command' \\
        '*:: :->args'

    case $state in
        command)
            _describe -t commands 'agentsh command' commands
            ;;
        args)
            case $words[1] in
                config)
                    if (( CURRENT == 2 )); then
                        _describe -t commands 'config command' config_commands
                    fi
                    ;;
                completions)
                    if (( CURRENT == 2 )); then
                        _values 'shell' bash zsh fish
                    elif (( CURRENT == 3 )); then
                        _values 'options' '--install[Install to system]'
                    fi
                    ;;
                devices)
                    if (( CURRENT == 2 )); then
                        _describe -t commands 'devices command' devices_commands
                    elif [[ $words[2] == "add" ]]; then
                        _hosts
                    fi
                    ;;
            esac
            ;;
    esac
}}

_agentsh "$@"
'''


def get_fish_completion() -> str:
    """Generate fish completion script.

    Returns:
        Fish completion script content
    """
    return f'''# Fish completion for AgentSH v{__version__}
# Install: agentsh completions fish > ~/.config/fish/completions/agentsh.fish

# Disable file completions by default
complete -c agentsh -f

# Global options
complete -c agentsh -s h -l help -d 'Show help message'
complete -c agentsh -l version -d 'Show version'
complete -c agentsh -l config -d 'Configuration file' -r -F
complete -c agentsh -l log-level -d 'Log level' -xa 'DEBUG INFO WARNING ERROR'
complete -c agentsh -s l -l login -d 'Run as login shell'
complete -c agentsh -l norc -d 'Skip rc files'
complete -c agentsh -l noprofile -d 'Skip profile files'
complete -c agentsh -l rcfile -d 'Custom RC file' -r -F
complete -c agentsh -l mcp-server -d 'Run as MCP server'
complete -c agentsh -l profile-startup -d 'Profile startup time'

# Commands
complete -c agentsh -n __fish_use_subcommand -a config -d 'Manage configuration'
complete -c agentsh -n __fish_use_subcommand -a status -d 'Show status'
complete -c agentsh -n __fish_use_subcommand -a completions -d 'Generate shell completions'
complete -c agentsh -n __fish_use_subcommand -a devices -d 'Device management'
complete -c agentsh -n __fish_use_subcommand -a help -d 'Show help'

# Config subcommands
complete -c agentsh -n '__fish_seen_subcommand_from config' -a init -d 'Initialize configuration'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a show -d 'Show current configuration'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a edit -d 'Edit configuration file'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a reset -d 'Reset to defaults'

# Completions subcommands
complete -c agentsh -n '__fish_seen_subcommand_from completions' -a bash -d 'Generate bash completions'
complete -c agentsh -n '__fish_seen_subcommand_from completions' -a zsh -d 'Generate zsh completions'
complete -c agentsh -n '__fish_seen_subcommand_from completions' -a fish -d 'Generate fish completions'
complete -c agentsh -n '__fish_seen_subcommand_from completions; and __fish_seen_subcommand_from bash zsh fish' -l install -d 'Install completions'

# Devices subcommands
complete -c agentsh -n '__fish_seen_subcommand_from devices' -a list -d 'List all devices'
complete -c agentsh -n '__fish_seen_subcommand_from devices' -a add -d 'Add a device'
complete -c agentsh -n '__fish_seen_subcommand_from devices' -a remove -d 'Remove a device'
complete -c agentsh -n '__fish_seen_subcommand_from devices' -a status -d 'Check device status'
'''


def install_completion(shell: str, script: str) -> Tuple[bool, str]:
    """Install completion script to appropriate location.

    Args:
        shell: Shell type (bash, zsh, fish)
        script: Completion script content

    Returns:
        Tuple of (success, path_or_error)
    """
    home = Path.home()

    # Determine installation path
    if shell == "bash":
        # Try system-wide first, then user
        paths = [
            Path("/etc/bash_completion.d/agentsh"),
            Path("/usr/share/bash-completion/completions/agentsh"),
            home / ".local" / "share" / "bash-completion" / "completions" / "agentsh",
        ]
    elif shell == "zsh":
        paths = [
            Path("/usr/share/zsh/site-functions/_agentsh"),
            Path("/usr/local/share/zsh/site-functions/_agentsh"),
            home / ".zsh" / "completions" / "_agentsh",
        ]
    elif shell == "fish":
        paths = [
            Path("/usr/share/fish/vendor_completions.d/agentsh.fish"),
            home / ".config" / "fish" / "completions" / "agentsh.fish",
        ]
    else:
        return False, f"Unknown shell: {shell}"

    # Try each path
    for path in paths:
        try:
            # Try to create parent directory
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write the script
            path.write_text(script)
            return True, str(path)
        except PermissionError:
            continue
        except Exception as e:
            continue

    # All paths failed
    return False, f"Could not write to any of: {', '.join(str(p) for p in paths)}"


def get_completion_script(shell: str) -> str:
    """Get completion script for specified shell.

    Args:
        shell: Shell type (bash, zsh, fish)

    Returns:
        Completion script content

    Raises:
        ValueError: If shell is not supported
    """
    if shell == "bash":
        return get_bash_completion()
    elif shell == "zsh":
        return get_zsh_completion()
    elif shell == "fish":
        return get_fish_completion()
    else:
        raise ValueError(f"Unsupported shell: {shell}")
