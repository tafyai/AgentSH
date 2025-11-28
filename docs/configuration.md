# Configuration Reference

agentsh uses a layered configuration system with TOML files.

## Configuration Locations

Configuration is loaded and merged in this order (later overrides earlier):

| Priority | Location | Scope |
|----------|----------|-------|
| 1 | Compiled defaults | Built-in |
| 2 | `/etc/aishell/config.toml` | System-wide |
| 3 | `~/.aishell/config.toml` | User-specific |
| 4 | `.aishellrc` | Per-project |

## Complete Configuration Reference

### AI Settings

```toml
[ai]
# LLM provider: "openai", "anthropic", "azure", "local"
provider = "openai"

# Model identifier
model = "gpt-4"

# API endpoint URL
endpoint = "https://api.openai.com/v1/chat/completions"

# Environment variable containing API key
api_key_env = "OPENAI_API_KEY"

# Maximum tokens for response
max_tokens = 2048

# Request timeout in seconds
timeout = 30

# Temperature for generation (0.0-2.0)
temperature = 0.7

# Maximum context window size
max_context = 8192
```

### Provider-Specific Examples

#### OpenAI

```toml
[ai]
provider = "openai"
model = "gpt-4"
endpoint = "https://api.openai.com/v1/chat/completions"
api_key_env = "OPENAI_API_KEY"
```

#### Anthropic

```toml
[ai]
provider = "anthropic"
model = "claude-3-opus-20240229"
endpoint = "https://api.anthropic.com/v1/messages"
api_key_env = "ANTHROPIC_API_KEY"
```

#### Azure OpenAI

```toml
[ai]
provider = "azure"
model = "gpt-4"
endpoint = "https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT/chat/completions?api-version=2024-02-15-preview"
api_key_env = "AZURE_OPENAI_API_KEY"
```

#### Local (Ollama)

```toml
[ai]
provider = "local"
model = "llama2"
endpoint = "http://localhost:11434/api/chat"
api_key_env = ""  # No key needed
```

### Mode Settings

```toml
[mode]
# Default AI mode: "off", "assist", "auto"
# - off: AI disabled, pure shell
# - assist: AI available via `ai` prefix (default)
# - auto: AI proactively suggests (experimental)
default = "assist"

# Underlying shell to spawn
shell = "/bin/bash"
# Alternative: use $SHELL environment variable
# shell = "$SHELL"

# Shell arguments
shell_args = ["-l"]
```

### Safety Settings

```toml
[safety]
# Require confirmation for destructive commands
# (rm -rf, mkfs, dd to devices, etc.)
require_confirmation_for_destructive = true

# Require confirmation for sudo commands
require_confirmation_for_sudo = true

# Allow AI to execute sudo commands after confirmation
# If false, sudo commands are only displayed, not executed
allow_ai_to_execute_sudo = false

# Log all AI-generated commands
log_ai_generated_commands = true

# Log file location
log_path = "~/.aishell/logs/commands.log"

# Maximum log file size before rotation (bytes)
max_log_size = 10485760  # 10MB

# Number of rotated logs to keep
log_retention = 5

# Redact potential secrets from logs
redact_secrets = true

# Commands that are always blocked (regex patterns)
blocked_patterns = [
    "rm -rf /",
    "dd.*of=/dev/sd[a-z]$",
    "mkfs.* /dev/sd[a-z]$"
]

# Paths that require extra confirmation for modification
protected_paths = [
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers",
    "~/.ssh/authorized_keys"
]
```

### UI Settings

```toml
[ui]
# Show plan before execution
show_plan_before_execution = true

# Show step numbers in output
show_step_numbers = true

# Prompt format (supports variables)
# Variables: {user}, {host}, {cwd}, {mode}
prompt = "{user}@{host}:{cwd} [{mode}]$ "

# AI status indicator in prompt
mode_indicators = { off = "shell", assist = "ai:assist", auto = "ai:auto" }

# Color output
color = true

# Color scheme
[ui.colors]
prompt_user = "green"
prompt_host = "blue"
prompt_cwd = "cyan"
ai_plan = "yellow"
ai_command = "white"
ai_warning = "red"
ai_success = "green"

# Show timestamps in output
show_timestamps = false

# Spinner style during AI calls
spinner = "dots"  # dots, line, arrow, star
```

### Context Settings

```toml
[context]
# Files to always include in AI context (relative to project root)
include_files = [
    "README.md",
    "Makefile",
    "docker-compose.yml",
    "package.json",
    "Cargo.toml"
]

# Patterns to exclude from context
exclude_patterns = [
    "*.log",
    "node_modules/*",
    "target/*",
    ".git/*",
    "*.pyc",
    "__pycache__/*"
]

# Maximum file size to include in context (bytes)
max_file_size = 102400  # 100KB

# Maximum total context size (bytes)
max_context_size = 524288  # 512KB

# Number of recent commands to include
history_lines = 20

# Domain hint for AI (helps with specialized tasks)
domain_hint = ""  # e.g., "web-app", "kubernetes", "database"
```

### History Settings

```toml
[history]
# Enable command history
enabled = true

# History file location
file = "~/.aishell/history"

# Maximum history entries
max_entries = 10000

# Share history with underlying shell
share_with_shell = true

# Ignore commands starting with space
ignore_space = true

# Commands to exclude from history (patterns)
ignore_patterns = [
    "^ai .*password.*",
    "^export.*API_KEY.*"
]
```

### Keybindings

```toml
[keys]
# Send current line to AI
ai_mode = "Alt-a"

# Toggle AI assist mode
toggle_assist = "Alt-m"

# Show AI help
ai_help = "Alt-h"

# Cancel AI operation
cancel = "Ctrl-c"

# Accept AI suggestion
accept = "Enter"

# Edit AI suggestion
edit = "e"

# Reject AI suggestion
reject = "n"
```

### Plugin Settings

```toml
[plugins]
# Enable plugin system
enabled = true

# Plugin directory
directory = "~/.aishell/plugins"

# Auto-load plugins
auto_load = true

# Specific plugins to load (if auto_load = false)
load = [
    "pkg-manager",
    "docker-helper"
]

# Plugin timeout (seconds)
timeout = 30
```

## Per-Project Configuration (.aishellrc)

Place `.aishellrc` in your project root for project-specific settings.

### Example Web Project

```toml
[context]
include_files = [
    "package.json",
    "tsconfig.json",
    "src/index.ts",
    "docker-compose.yml"
]
exclude_patterns = [
    "node_modules/*",
    "dist/*",
    ".next/*"
]
domain_hint = "nodejs-web-app"

[ai]
# Use a faster model for this project
model = "gpt-3.5-turbo"
```

### Example DevOps Project

```toml
[context]
include_files = [
    "terraform/*.tf",
    "ansible/*.yml",
    "kubernetes/*.yaml",
    "Makefile"
]
domain_hint = "infrastructure-devops"

[safety]
# Extra caution for infrastructure
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
allow_ai_to_execute_sudo = false
```

### Example Database Project

```toml
[context]
include_files = [
    "migrations/*.sql",
    "schema.sql",
    "docker-compose.yml"
]
domain_hint = "postgresql-database"

[safety]
# Block dangerous SQL patterns
blocked_patterns = [
    "DROP DATABASE",
    "TRUNCATE.*CASCADE"
]
```

## Environment Variables

These environment variables override config file settings:

| Variable | Description |
|----------|-------------|
| `AISHELL_CONFIG` | Path to config file |
| `AISHELL_MODE` | Default mode (off/assist/auto) |
| `AISHELL_SHELL` | Shell to spawn |
| `AISHELL_LOG` | Log file path |
| `AISHELL_DEBUG` | Enable debug logging (true/false) |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

## CLI Flags

Command-line flags take highest precedence:

```bash
agentsh [OPTIONS] [SHELL]

Options:
  -c, --config <FILE>     Config file path
  -m, --mode <MODE>       AI mode (off/assist/auto)
  -s, --shell <SHELL>     Shell to spawn
  -d, --debug             Enable debug output
  -v, --version           Print version
  -h, --help              Print help

Examples:
  agentsh                        # Use default config and shell
  agentsh /bin/zsh               # Use zsh as underlying shell
  agentsh -m off                 # Start with AI disabled
  agentsh -c ~/custom.toml       # Use custom config
```

## Validation

agentsh validates configuration on startup. Invalid configurations produce clear error messages:

```
Error: Invalid configuration
  → ai.model: required field missing
  → safety.log_path: directory does not exist: /var/log/aishell
  → ui.colors.prompt_user: invalid color: "chartreuse"

Fix these issues in ~/.aishell/config.toml and restart.
```

## Defaults

If no configuration file exists, agentsh uses these defaults:

```toml
[ai]
provider = "openai"
model = "gpt-4"
max_tokens = 2048

[mode]
default = "assist"

[safety]
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
allow_ai_to_execute_sudo = false
log_ai_generated_commands = true

[ui]
show_plan_before_execution = true
color = true
```
