# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

agentsh is an AI-powered login shell written in Rust that wraps a traditional shell (bash/zsh) with AI capabilities. It acts as a PTY shim + agent, intercepting commands starting with `ai` and routing them to an LLM while passing through normal shell commands unchanged.

**Key Concept**: agentsh is NOT a full shell implementation. It spawns a real shell in a PTY and acts as an intelligent proxy layer.

## Essential Commands

### Build & Run
```bash
# Debug build
cargo build

# Release build
cargo build --release

# Run debug version
cargo run

# Run with specific shell
cargo run -- /bin/bash

# Run with debug logging
RUST_LOG=debug cargo run
```

### Testing
```bash
# Run all tests
cargo test

# Run specific test
cargo test test_name

# Run with output visible
cargo test -- --nocapture

# Run integration tests
cargo test --test integration
```

### Code Quality
```bash
# Format code
cargo fmt

# Check formatting
cargo fmt -- --check

# Run linter
cargo clippy

# Strict linting
cargo clippy -- -D warnings
```

## Architecture Overview

### Core Data Flow

**Normal Command**:
```
User Input → Input Router → PTY → Shell → OS
```

**AI Command** (`ai find port 8080`):
```
User Input → Input Router → AI Orchestrator → LLM API
                                ↓
                         Execution Engine
                                ↓
                         Safety Analysis
                                ↓
                    User Confirmation (y/e/n)
                                ↓
                         Execute via PTY
```

### Module Responsibilities

| Module | File | Purpose |
|--------|------|---------|
| **Shell Runner** | `shell.rs` | Main event loop, manages PTY I/O, coordinates AI and shell |
| **PTY** | `pty.rs` | Creates and manages pseudo-terminal pair, spawns underlying shell |
| **Input Router** | `input_router.rs` | Detects `ai` commands, routes to AI vs shell |
| **AI Orchestrator** | `ai_orchestrator.rs` | LLM API communication, conversation context |
| **Execution Engine** | `execution_engine.rs` | Executes AI-proposed commands, handles confirmation |
| **Safety** | `safety.rs` | Analyzes commands for destructive operations (rm -rf, sudo, etc.) |
| **Context** | `context.rs` | Gathers system info (OS, services, packages) for AI |
| **Config** | `config.rs` | Layered TOML configuration loading |
| **Logging** | `logging.rs` | Audit logging of AI-generated commands |

### Key Types

**AI Action Response** (`ai_orchestrator.rs`):
```rust
enum ActionKind {
    AnswerOnly,           // Just text, no commands
    CommandSequence,      // One or more commands to execute
    PlanAndCommands,      // Plan + commands
}

struct Step {
    id: String,
    description: String,
    shell_command: String,
    needs_confirmation: bool,
    is_destructive: bool,
    requires_sudo: bool,
}
```

**Safety Analysis** (`safety.rs`):
```rust
struct SafetyFlags {
    is_destructive: bool,      // rm -rf, mkfs, dd
    requires_sudo: bool,
    affects_critical_service: bool,  // sshd, etc.
    modifies_packages: bool,
}
```

## Configuration System

Configuration is layered (later overrides earlier):
1. Compiled defaults
2. `/etc/aishell/config.toml` (system-wide)
3. `~/.aishell/config.toml` (user)
4. `.aishellrc` (per-project, reloaded on cd)

See [examples/config.toml](examples/config.toml) for complete example.

## Important Implementation Details

### PTY Management
- Uses `portable-pty` crate for cross-platform PTY support
- Spawns underlying shell with user's environment
- Must handle SIGWINCH for terminal resize
- Raw mode enabled during shell operation, disabled for AI interaction

### AI Command Detection
Commands are routed to AI if they start with:
- `ai ` (e.g., `ai find port 8080`)
- `@ai ` (alternative prefix)

See `input_router::is_ai_command()` for detection logic.

### Safety System
The safety module (`safety.rs`) performs static analysis on proposed commands:
- **Destructive operations**: `rm -rf`, `mkfs`, `dd` to block devices
- **Sudo commands**: All commands using `sudo`
- **Critical services**: Operations affecting `sshd`, networking
- **Protected paths**: `/etc/passwd`, `/etc/shadow`, etc.

Extra confirmation required when safety flags are raised.

### Execution Confirmation Flow
1. AI generates plan with steps
2. If `ui.show_plan_before_execution = true`, display plan
3. User confirms: `y` (yes), `e` (edit in $EDITOR), `n` (no)
4. For each step:
   - Run safety analysis
   - If flagged, require additional confirmation
   - Execute via PTY
   - Capture output

### Async Architecture
- Uses `tokio` async runtime
- PTY read/write in separate threads/tasks
- HTTP calls to LLM are async
- Signal handling for SIGINT/SIGTERM/SIGWINCH

## Testing Considerations

### PTY Tests
PTY tests may fail in CI without proper TTY support. Tests should:
- Use `tests/fixtures/` for mock data
- Mock LLM responses using `mockito` crate
- Set `TERM=xterm-256color` in CI environments

### Integration Tests
Place in `tests/integration/` directory. Key areas to test:
- PTY spawn and I/O
- AI command routing
- Safety analysis patterns
- Configuration loading and merging

## Common Development Tasks

### Adding a New AI Command Mode
1. Update `AiMode` in `ai_orchestrator.rs`
2. Add routing logic in `input_router.rs`
3. Update `ShellRunner::handle_ai_command()` in `shell.rs`
4. Add tests in `tests/integration/ai_tests.rs`

### Adding Safety Patterns
1. Add pattern to `safety.rs::analyze_command()`
2. Return appropriate `SafetyFlags`
3. Add test cases for the pattern
4. Document in `docs/security.md`

### Supporting a New LLM Provider
1. Add provider variant to `AiConfig` in `config.rs`
2. Implement request/response formatting in `ai_orchestrator.rs`
3. Add example config in `docs/configuration.md`
4. Test with mock server

### Extending Context Collection
1. Add tool definition to `context.rs`
2. Implement data collection function
3. Include in `AiContext` struct
4. Update prompts in `ai_orchestrator.rs` to use the new context

## Error Handling Philosophy

| Component | Strategy |
|-----------|----------|
| **PTY** | Propagate to user, offer shell restart |
| **AI Backend** | Degrade gracefully, continue as normal shell |
| **Config** | Use defaults, log warning |
| **Execution** | Pause on failure, offer retry/skip/abort |
| **Safety** | Fail-safe (require confirmation when uncertain) |

## Environment Variables

The shell sets these for the child process:
- `AGENTSH=1` - Indicates running under agentsh
- `AGENTSH_VERSION` - Version number
- Standard shell vars: `HOME`, `USER`, `PATH`, `TERM`, etc.
- API keys: Variables ending in `_API_KEY` or `_TOKEN`

## Important Dependencies

- `portable-pty` - Cross-platform PTY operations
- `tokio` - Async runtime
- `rustyline` - Line editing (future integration)
- `reqwest` - HTTP client for LLM APIs
- `nix` - POSIX/Unix system calls
- `tracing` - Structured logging
- `serde` + `toml` - Configuration parsing

## Conventions

### Commit Messages
Follow Conventional Commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation only
- `refactor:` - Code restructuring
- `test:` - Test additions

### Code Style
- Use `Result<T>` for fallible operations
- Prefer `?` operator over explicit matching
- Document public APIs with rustdoc (`///`)
- Keep functions focused and small
- Place unit tests in `#[cfg(test)]` modules alongside code

## Security Considerations

This is a **defensive security tool** - never add features that:
- Auto-execute commands without confirmation
- Bypass safety checks by default
- Expose credentials or secrets
- Perform bulk credential harvesting

All AI-generated commands must:
- Be visible to the user before execution
- Respect safety configuration
- Be logged (when enabled)
- Allow user cancellation
