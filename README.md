# agentsh

An AI-powered login shell that combines traditional shell capabilities with an intelligent operations agent.

## Overview

agentsh is a login shell that:
- **Feels like ZSH/Fish** - Full support for history, completion, prompts, and scripting interoperability
- **Adds an AI ops agent** - Take natural language tasks and turn them into shell commands/scripts
- **Works over plain SSH** - No custom client or GUI required; manages hosts over standard SSH connections

### Mental Model

```
sshd → agentsh → [real shell + AI orchestrator] → OS
```

agentsh acts as a shim + agent around a normal shell, not a full replacement of POSIX semantics.

## Features

### Shell Modes

| Mode | Description |
|------|-------------|
| **Normal** | Standard shell behavior; AI is idle unless invoked |
| **Assisted** | AI triggered via `ai` prefix or keybinding |
| **Autonomous** | Multi-step task execution with `ai do` |

### AI Commands

```bash
# Single command assistance
ai find and kill the process using port 8080

# Explicit run mode
ai run "set up nginx with TLS"

# Explain a command
ai explain 'rsync -avz --delete src/ dst/'

# Fix the last error
ai fix

# Multi-step autonomous task
ai do "Set up a Dockerized Postgres with volume persistence and daily dumps"
```

### System Inspection Tools

```bash
ai sysinfo    # OS, CPU, RAM, disk usage
ai services   # Running services
ai packages   # Installed package versions
```

## Installation

### Prerequisites

- Linux or macOS (Windows via WSL supported)
- Rust toolchain (for building from source)
- An LLM API key (OpenAI, Anthropic, or compatible)

### Build from Source

```bash
git clone https://github.com/yourusername/agentsh.git
cd agentsh
cargo build --release
sudo cp target/release/agentsh /usr/local/bin/
```

### Set as Login Shell

```bash
# Add to /etc/shells if needed
echo /usr/local/bin/agentsh | sudo tee -a /etc/shells

# Change your shell
chsh -s /usr/local/bin/agentsh
```

### Use as Wrapper

```bash
agentsh /bin/bash
```

## Configuration

agentsh reads configuration from (in order of precedence):
1. `/etc/aishell/config.toml` - System-wide
2. `~/.aishell/config.toml` - User-specific
3. `.aishellrc` - Per-project (loaded on directory change)

### Example Configuration

```toml
[ai]
provider = "openai"
model = "gpt-4"
endpoint = "https://api.openai.com/v1/chat/completions"
api_key_env = "OPENAI_API_KEY"
max_tokens = 2048

[mode]
default = "assist"  # "off" | "assist" | "auto"

[safety]
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
allow_ai_to_execute_sudo = false
log_ai_generated_commands = true
log_path = "~/.aishell/logs/commands.log"

[ui]
show_plan_before_execution = true
show_step_numbers = true
```

## Safety

agentsh prioritizes safety with:

- **No automatic privilege escalation** - sudo commands require explicit confirmation
- **Destructive operation detection** - Commands like `rm -rf`, `mkfs`, `dd` are flagged
- **Audit logging** - All AI-generated commands logged (configurable)
- **Graceful degradation** - If AI is unreachable, shell continues to work normally

## Documentation

- [Architecture](docs/architecture.md) - System design and component overview
- [API Reference](docs/api.md) - JSON schema and tool contracts
- [Configuration](docs/configuration.md) - Complete configuration reference
- [Development](docs/development.md) - Contributing and development setup
- [Security](docs/security.md) - Security model and best practices
- [User Guide](docs/user-guide.md) - Complete usage instructions

## Project Structure

```
agentsh/
├── src/
│   ├── main.rs           # Entry point and CLI
│   ├── pty.rs            # PTY management
│   ├── input_router.rs   # Input routing and line editing
│   ├── ai_orchestrator.rs # LLM communication
│   ├── execution_engine.rs # Command execution
│   ├── context.rs        # System context collection
│   ├── config.rs         # Configuration management
│   ├── safety.rs         # Destructive command detection
│   └── logging.rs        # Audit logging
├── tests/                # Integration tests
├── docs/                 # Documentation
└── contrib/              # Plugins and extensions
```

## License

[License to be determined]

## Contributing

See [Development Guide](docs/development.md) for contribution guidelines.
