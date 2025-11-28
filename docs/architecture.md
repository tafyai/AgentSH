# Architecture

This document describes the system architecture and internal components of agentsh.

## High-Level Process Model

```
User TTY
   │
   ▼
[ agentsh ]
   │ \
   │  \ (AI backend over HTTP/HTTPS)
   │
   ▼
[ PTY + real shell ]
   │
   ▼
  OS
```

### Login Flow

1. `sshd` (or local `login`) invokes `agentsh` as the login shell
2. `agentsh`:
   - Parses configuration
   - Sets up a PTY pair
   - Spawns the execution shell (user-configurable, defaults to `$SHELL` or `/bin/bash`)
3. agentsh runs an event loop:
   - For most input: pass bytes between user TTY and PTY unchanged
   - When an AI entrypoint is detected: intercept and invoke AI orchestration

## Core Modules

### 1. PTY Module (`pty.rs`)

Manages pseudo-terminal creation and shell spawning.

**Responsibilities:**
- Create and manage PTY pair
- Spawn underlying shell as child process
- Bidirectional I/O between stdin/stdout and PTY master
- Window-size handling (SIGWINCH)

**Key Types:**

```rust
struct PtyShell {
    child_pid: Pid,
    master_fd: RawFd,
}

impl PtyShell {
    fn spawn(shell_path: &str, args: &[&str]) -> Result<PtyShell>;
    fn resize(&self, cols: u16, rows: u16);
    fn read(&self) -> Result<Vec<u8>>;
    fn write(&self, data: &[u8]) -> Result<usize>;
}
```

### 2. Input Router Module (`input_router.rs`)

Routes user input between shell and AI.

**Responsibilities:**
- Detect when to use passthrough vs line-editor mode
- Recognize `ai` commands and special forms
- Maintain command history

**Operating Modes:**

| Mode | Use Case | Behavior |
|------|----------|----------|
| Passthrough | Full-screen apps (vim, top) | Bytes relayed unchanged |
| Line-editor | Normal commands | readline-style editing with history |

**Detection Logic:**
- Lines starting with `ai` / `@ai` → route to AI
- Special keybinding (Alt-A) → send current line to AI
- All other input → forward to PTY

### 3. AI Orchestrator Module (`ai_orchestrator.rs`)

Manages communication with the LLM backend.

**Responsibilities:**
- Maintain per-session conversation context
- Build prompts with system instructions and context
- Call LLM API and parse JSON responses
- Handle malformed responses gracefully

**Key Types:**

```rust
enum ActionKind {
    AnswerOnly,
    CommandSequence,
    PlanAndCommands,
}

struct Step {
    id: String,
    description: String,
    shell_command: String,
    needs_confirmation: bool,
    is_destructive: bool,
    requires_sudo: bool,
    working_directory: Option<PathBuf>,
}

struct AiAction {
    kind: ActionKind,
    summary: Option<String>,
    steps: Vec<Step>,
}
```

**Response Handling:**
1. Try to parse entire response as JSON
2. If fails, look for first `{`…`}` block and parse
3. If still fails, treat as `AnswerOnly` and print text

### 4. Execution Engine Module (`execution_engine.rs`)

Executes AI-proposed commands with user confirmation.

**Responsibilities:**
- Present plans to user
- Handle user confirmation (y/e/n)
- Execute commands via PTY
- Enforce safety policies
- Capture output for AI and user

**Execution Flow:**

```
┌─────────────────┐
│ Receive AiAction│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Render Plan    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌──────────┐
│ User Confirms?  │───▶│  Cancel  │
└────────┬────────┘ n  └──────────┘
         │ y/e
         ▼
┌─────────────────┐
│ For Each Step   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐
│ Safety Check    │───▶│ Extra Confirm    │
└────────┬────────┘    └────────┬─────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────┐
│            Execute via PTY              │
└─────────────────────────────────────────┘
```

### 5. Context Collector Module (`context.rs`)

Provides environmental context to the AI.

**Responsibilities:**
- Gather OS and system information
- Track current working directory
- Read relevant files (bounded size)
- Provide recent command history

**Built-in Tools:**

| Tool | Description |
|------|-------------|
| `sysinfo` | OS, CPU, RAM, disk usage |
| `services` | Running services (systemd/init) |
| `packages` | Installed package versions |
| `fs.read_file` | Size-limited file reading |

### 6. Config Module (`config.rs`)

Manages layered configuration.

**Configuration Sources (in order):**
1. Compiled-in defaults
2. `/etc/aishell/config.toml` (system)
3. `~/.aishell/config.toml` (user)
4. `.aishellrc` (per-project, reloaded on cd)

**Key Types:**

```rust
struct AiConfig {
    provider: String,
    model: String,
    endpoint: String,
    api_key_env: String,
    max_tokens: u32,
}

struct SafetyConfig {
    require_confirmation_for_destructive: bool,
    require_confirmation_for_sudo: bool,
    allow_ai_to_execute_sudo: bool,
    log_ai_generated_commands: bool,
    log_path: PathBuf,
}

struct UiConfig {
    show_plan_before_execution: bool,
    show_step_numbers: bool,
}

struct Config {
    ai: AiConfig,
    safety: SafetyConfig,
    ui: UiConfig,
}
```

### 7. Safety Module (`safety.rs`)

Analyzes commands for dangerous operations.

**Responsibilities:**
- Static analysis of proposed commands
- Pattern matching for destructive operations
- Return safety flags for Execution Engine

**Detection Categories:**

| Category | Examples |
|----------|----------|
| Destructive FS | `rm -rf`, `mkfs`, critical path ops |
| Block Device | `dd if=/dev/... of=/dev/...` |
| Network | `iptables`, `ufw` |
| Services | `systemctl restart sshd` |
| Packages | apt/yum/dnf/pacman install/remove |
| Privilege | Any command with `sudo` |

**API:**

```rust
struct SafetyFlags {
    is_destructive: bool,
    requires_sudo: bool,
    affects_critical_service: bool,
    modifies_packages: bool,
}

fn analyze_command(cmd: &str) -> SafetyFlags;
```

### 8. Logging Module (`logging.rs`)

Provides audit logging for AI-generated commands.

**Responsibilities:**
- Append commands and context to log file
- Include session ID and timestamp
- Best-effort secret redaction

**Log Format (JSON Lines):**

```json
{
  "session_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "request": "find and kill port 8080",
  "ai_action": { ... },
  "executed_commands": ["lsof -i :8080", "kill 1234"]
}
```

## Data Flow

### Normal Shell Command

```
User Input → Input Router → PTY → Shell → OS
                              ↓
                          Output → User
```

### AI-Assisted Command

```
User Input ("ai ...") → Input Router
                              ↓
                    AI Orchestrator
                              ↓
                      LLM Backend
                              ↓
                    Parse AiAction
                              ↓
                   Execution Engine
                              ↓
                    Present to User
                              ↓
                      Confirm (y/e/n)
                              ↓
                    Safety Analysis
                              ↓
                     Execute via PTY
                              ↓
                    Capture Output
                              ↓
                     Display + Log
```

## Concurrency Model

agentsh uses async I/O (tokio) for:
- PTY read/write loops
- HTTP calls to LLM backend
- Signal handling

```
┌─────────────────────────────────────────────────────┐
│                    Main Event Loop                   │
├─────────────┬─────────────┬─────────────────────────┤
│ PTY Reader  │ PTY Writer  │ Signal Handler          │
│ (async)     │ (async)     │ (SIGINT/TERM/WINCH)     │
├─────────────┴─────────────┴─────────────────────────┤
│                   HTTP Client                        │
│              (LLM API calls, async)                  │
└─────────────────────────────────────────────────────┘
```

## Plugin Architecture (v2)

Plugins extend agentsh with new tools for AI.

**Protocol:** JSON over stdin/stdout

**Request:**
```json
{
  "tool": "pkg.manage",
  "action": "install",
  "args": { "packages": ["nginx"], "assume_yes": true }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "...",
  "stderr": "",
  "meta": { "duration_ms": 2300 }
}
```

**Built-in Tools:**
- `cmd.run` - Execute shell commands
- `fs.read_file`, `fs.write_file` - File operations
- `pkg.manage` - Package manager abstraction
- `svc.manage` - Service management

## Error Handling

| Component | Error Handling Strategy |
|-----------|------------------------|
| PTY | Propagate to user, offer shell restart |
| AI Backend | Degrade gracefully, continue as normal shell |
| Config | Use defaults, log warning |
| Execution | Pause on failure, offer retry/skip/fix |
| Safety | Fail-safe (require confirmation when uncertain) |
