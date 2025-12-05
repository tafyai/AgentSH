#compdef agentsh

# Zsh completion for AgentSH
# Install: cp agentsh.zsh /usr/share/zsh/site-functions/_agentsh
# Or: fpath+=(/path/to/dir) before compinit

_agentsh() {
    local context state state_descr line
    typeset -A opt_args

    local -a commands
    commands=(
        'config:Manage configuration'
        'status:Show status'
        'version:Show version'
        'help:Show help'
    )

    local -a config_commands
    config_commands=(
        'init:Initialize configuration'
        'show:Show current configuration'
        'edit:Edit configuration file'
        'reset:Reset to defaults'
        'import:Import configuration'
        'export:Export configuration'
    )

    local -a global_opts
    global_opts=(
        '--help[Show help message]'
        '--version[Show version]'
        '--debug[Enable debug mode]'
        '--quiet[Suppress output]'
        '--no-color[Disable color output]'
        '--config[Configuration file]:file:_files -g "*.yaml"'
        '--model[Model to use]:model:(claude-3-5-sonnet-latest claude-sonnet-4-20250514 gpt-4o gpt-4-turbo llama3.2 mistral)'
        '--provider[LLM provider]:provider:(anthropic openai ollama openrouter litellm)'
    )

    _arguments -C \
        "${global_opts[@]}" \
        '1: :->command' \
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
                    else
                        case $words[2] in
                            import|export)
                                _files
                                ;;
                        esac
                    fi
                    ;;
                *)
                    _files
                    ;;
            esac
            ;;
    esac
}

_agentsh "$@"
