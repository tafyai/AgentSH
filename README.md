# AgentSH

[![CI](https://github.com/tafyai/AgentSH/actions/workflows/ci.yml/badge.svg)](https://github.com/tafyai/AgentSH/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An AI-powered login shell that combines traditional shell capabilities with an intelligent operations agent.

## Overview

AgentSH is a login shell that:
- **Feels like ZSH/Fish** - Full support for history, completion, prompts, and scripting interoperability
- **Adds an AI ops agent** - Take natural language tasks and turn them into shell commands/scripts
- **Works over plain SSH** - No custom client or GUI required; manages hosts over standard SSH connections

### Mental Model

```
sshd → agentsh → [real shell + AI orchestrator] → OS
```

AgentSH acts as a shim + agent around a normal shell, not a full replacement of POSIX semantics.

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

### Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/tafyai/AgentSH/main/scripts/install.sh | bash
```

### Prerequisites

- Linux or macOS (Windows via WSL supported)
- Rust toolchain (for building from source)
- An LLM API key (OpenAI, Anthropic, or compatible)

### Build from Source

```bash
git clone https://github.com/tafyai/AgentSH.git
cd AgentSH
cargo build --release
cp target/release/agentsh ~/.local/bin/
```

### Set as Login Shell

```bash
# Add to /etc/shells if needed
echo ~/.local/bin/agentsh | sudo tee -a /etc/shells

# Change your shell
chsh -s ~/.local/bin/agentsh
```

### Use as Wrapper

```bash
agentsh /bin/bash
```

## Configuration

AgentSH reads configuration from (in order of precedence):
1. `/etc/aishell/config.toml` - System-wide
2. `~/.aishell/config.toml` - User-specific
3. `.aishellrc` - Per-project (loaded on directory change)

### Example Configuration

```toml
[ai]
provider = "openai"          # openai, anthropic, or custom
model = "gpt-4"
endpoint = "https://api.openai.com/v1/chat/completions"
api_key_env = "OPENAI_API_KEY"
max_tokens = 2048
temperature = 0.7
timeout_secs = 30

[mode]
default = "assist"           # "off" | "assist" | "auto"

[safety]
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
allow_ai_to_execute_sudo = false
log_ai_generated_commands = true
log_path = "~/.aishell/logs/commands.log"
protected_paths = ["/etc", "/boot", "~/.ssh"]
blocked_patterns = ["rm -rf /", ":(){ :|:& };:"]

[ui]
show_plan_before_execution = true
show_step_numbers = true
spinner_style = "braille"    # braille, dots, simple

[logging]
level = "info"               # trace, debug, info, warn, error
format = "pretty"            # pretty, json, compact
log_dir = "~/.aishell/logs"
max_log_size_mb = 10
max_log_files = 5
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `AISHELL_CONFIG` | Custom config file path |
| `AISHELL_LOG_LEVEL` | Override log level |

## Safety

AgentSH prioritizes safety with:

- **No automatic privilege escalation** - sudo commands require explicit confirmation
- **Destructive operation detection** - Commands like `rm -rf`, `mkfs`, `dd` are flagged
- **Database protection** - DROP, TRUNCATE, FLUSHALL operations require confirmation
- **Network/firewall guards** - iptables flush, interface down operations are flagged
- **Critical service protection** - SSH, init operations require confirmation
- **Protected paths** - Configurable paths that trigger warnings
- **Blocked patterns** - Commands matching patterns are rejected entirely
- **Audit logging** - All AI-generated commands logged with timestamps
- **Graceful degradation** - If AI is unreachable, shell continues to work normally

### Safety Flags

When a potentially dangerous command is detected, AgentSH displays warnings:

```
⚠️  DESTRUCTIVE: Command may delete or modify files
⚠️  SUDO: Command requires elevated privileges
⚠️  DATABASE: Command may destroy database data
⚠️  NETWORK: Command modifies network/firewall configuration
```

## Plugin System

AgentSH supports plugins for extending functionality:

```bash
~/.aishell/plugins/
├── my-plugin/
│   ├── manifest.toml
│   └── plugin.sh
```

### Plugin Manifest

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
description = "My custom plugin"
entry_point = "plugin.sh"

[[tools]]
name = "my_tool"
description = "Does something useful"
```

## Project Structure

```
agentsh/
├── src/
│   ├── main.rs              # Entry point and CLI
│   ├── cli.rs               # Command-line argument parsing
│   ├── shell.rs             # Shell session management
│   ├── pty.rs               # PTY management
│   ├── input_router.rs      # Input routing and line editing
│   ├── ai_orchestrator.rs   # LLM communication
│   ├── execution_engine.rs  # Command execution
│   ├── context.rs           # System context collection
│   ├── config.rs            # Configuration management
│   ├── safety.rs            # Destructive command detection
│   ├── logging.rs           # Structured audit logging
│   ├── spinner.rs           # Progress indicators
│   ├── error.rs             # Error types and handling
│   └── plugins/             # Plugin system
│       ├── mod.rs
│       ├── manager.rs
│       ├── loader.rs
│       └── protocol.rs
├── scripts/
│   └── install.sh           # Installation script
├── tests/                   # Integration tests
├── docs/                    # Documentation
└── .github/
    └── workflows/
        └── ci.yml           # CI/CD pipeline
```

## Development

### Building

```bash
cargo build           # Debug build
cargo build --release # Release build
cargo test            # Run tests (108+ tests)
cargo clippy          # Lint
cargo fmt             # Format
```

### Running Tests

```bash
# All tests
cargo test

# Specific module
cargo test safety::
cargo test config::
cargo test logging::

# With output
cargo test -- --nocapture
```

### Security Audit

```bash
cargo audit
```

## Troubleshooting

### Common Issues

**API Key Not Found**
```
Error: Missing API key
Tip: Set OPENAI_API_KEY or configure api_key_env in config
```

**Rate Limited**
```
Error: AI API error (429)
Tip: Rate limit exceeded. Wait a moment and try again.
```

**Connection Timeout**
```
Error: Request timed out
Tip: Check your network connection or increase timeout_secs
```

### Debug Mode

```bash
AISHELL_LOG_LEVEL=debug agentsh
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Run `cargo fmt` before committing
- Ensure `cargo clippy` passes
- Add tests for new functionality
- Update documentation as needed

## Acknowledgments

- Built with Rust and Tokio
- Uses portable-pty for cross-platform PTY support
- Inspired by the vision of AI-augmented developer workflows
