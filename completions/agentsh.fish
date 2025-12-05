# Fish completion for AgentSH
# Install: cp agentsh.fish ~/.config/fish/completions/
# Or: cp agentsh.fish /usr/share/fish/vendor_completions.d/

# Disable file completions by default
complete -c agentsh -f

# Global options
complete -c agentsh -s h -l help -d 'Show help message'
complete -c agentsh -l version -d 'Show version'
complete -c agentsh -l debug -d 'Enable debug mode'
complete -c agentsh -s q -l quiet -d 'Suppress output'
complete -c agentsh -l no-color -d 'Disable color output'
complete -c agentsh -s c -l config -d 'Configuration file' -r -F
complete -c agentsh -s m -l model -d 'Model to use' -xa 'claude-3-5-sonnet-latest claude-sonnet-4-20250514 gpt-4o gpt-4-turbo llama3.2 mistral'
complete -c agentsh -s p -l provider -d 'LLM provider' -xa 'anthropic openai ollama openrouter litellm'

# Commands
complete -c agentsh -n __fish_use_subcommand -a config -d 'Manage configuration'
complete -c agentsh -n __fish_use_subcommand -a status -d 'Show status'
complete -c agentsh -n __fish_use_subcommand -a version -d 'Show version'
complete -c agentsh -n __fish_use_subcommand -a help -d 'Show help'

# Config subcommands
complete -c agentsh -n '__fish_seen_subcommand_from config' -a init -d 'Initialize configuration'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a show -d 'Show current configuration'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a edit -d 'Edit configuration file'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a reset -d 'Reset to defaults'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a import -d 'Import configuration'
complete -c agentsh -n '__fish_seen_subcommand_from config' -a export -d 'Export configuration'

# Enable file completion for import/export
complete -c agentsh -n '__fish_seen_subcommand_from import export' -F
