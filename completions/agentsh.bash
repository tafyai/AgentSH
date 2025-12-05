# Bash completion for AgentSH
# Install: cp agentsh.bash /usr/share/bash-completion/completions/agentsh
# Or: source agentsh.bash

_agentsh_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="config status version help"
    local config_commands="init show edit reset import export"
    local global_opts="--help --version --debug --quiet --no-color"

    case "${prev}" in
        agentsh)
            COMPREPLY=($(compgen -W "${commands} ${global_opts}" -- "${cur}"))
            return
            ;;
        config)
            COMPREPLY=($(compgen -W "${config_commands}" -- "${cur}"))
            return
            ;;
        --config|-c)
            _filedir yaml
            return
            ;;
        --model|-m)
            local models="claude-3-5-sonnet-latest claude-sonnet-4-20250514 gpt-4o gpt-4-turbo llama3.2 mistral"
            COMPREPLY=($(compgen -W "${models}" -- "${cur}"))
            return
            ;;
        --provider|-p)
            local providers="anthropic openai ollama openrouter litellm"
            COMPREPLY=($(compgen -W "${providers}" -- "${cur}"))
            return
            ;;
        import|export)
            _filedir
            return
            ;;
    esac

    case "${cur}" in
        -*)
            COMPREPLY=($(compgen -W "${global_opts}" -- "${cur}"))
            return
            ;;
    esac

    # Default to file completion
    _filedir
}

complete -F _agentsh_completions agentsh
