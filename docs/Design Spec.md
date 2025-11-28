I’ll call it **agentsh** in the spec, but treat that as a placeholder.

---

## 0. High-level concept

**Goal:** A login shell that:

- Feels like ZSH/FISH (history, completion, prompts, scripting interop).
    
- Adds an **AI “ops agent”** that can:
    
    - Take natural language tasks and turn them into shell commands/scripts.
        
    - Execute them safely, step-by-step, with review.
        
    - Manage the host over plain SSH (no extra GUI or protocol).
        

**Mental model:**  
`sshd → agentsh → [real shell + AI orchestrator] → OS`

agentsh is a **shim + agent** around a normal shell, not a full replacement of POSIX semantics.

---

## 1. Functional requirements

### 1.1 Shell behaviour

agentsh MUST:

1. Act as a valid login shell (usable in `/etc/passwd`).
    
2. Work over **plain SSH** (no custom client required).
    
3. Support:
    
    - Running arbitrary commands/binaries.
        
    - Pipes, redirections, environment vars.
        
    - Interactive programs (vim, top, etc.).
        
    - Command history (shared with underlying shell if desired).
        
4. Start in a reasonable default prompt:
    
    - e.g. `user@host:~/dir [ai:assist]$`
        

It MAY:

- Delegate actual command execution to an underlying shell (bash/zsh/fish) via PTY.
    
- Provide its own completion and prompt logic on top.
    

---

### 1.2 AI-assisted usage modes

#### 1.2.1 Normal shell mode

- User types shell commands as usual.
    
- agentsh just forwards them to the underlying shell.
    
- AI is idle unless explicitly invoked.
    

#### 1.2.2 Assisted mode (inline AI)

AI is triggered by one of:

- Prefixes: `ai ...` / `@ai ...`  
    Example:  
    `ai find and kill the process using port 8080`
    
- Special keybinding (e.g. `Alt-A`) that sends the current line to AI instead of executing it.
    
- Command forms:
    
    - `ai run "set up nginx with TLS"`
        
    - `ai explain 'rsync -avz --delete src/ dst/'`
        
    - `ai fix` (while last command failed)
        

AI responds with **proposed shell actions**:

- Show a “plan” (in natural language).
    
- Show proposed commands.
    
- Mark destructive/privileged commands as needing confirmation.
    

User can:

- `y` / `enter` — accept and execute.
    
- `e` — edit commands before run.
    
- `n` — cancel.
    

#### 1.2.3 Autonomous task mode

Command:  
`ai do "short description of a multi-step task"`

Example:

```sh
ai do "Set up a basic Dockerized Postgres instance with volume persistence and a daily dump"
```

Expected behaviour:

1. AI creates a **multi-step plan**:
    
    - Check OS and Docker install.
        
    - Create docker-compose.yml.
        
    - Start service.
        
    - Add cron job for dump.
        
2. User confirms the plan.
    
3. agentsh orchestrator:
    
    - Runs commands step-by-step.
        
    - Streams output.
        
    - Gives progress updates.
        
    - May loop with AI for “observe → think → next action” using tool calls.
        

---

## 2. Non-functional requirements

- **Compatibility:** Linux (primary), macOS; Windows via WSL is “nice to have”.
    
- **Degradability:** If AI backend is unreachable:
    
    - agentsh behaves like a regular shell.
        
    - `ai` commands show a clear error, but don’t break anything.
        
- **Latency:** Regular shell usage must not be slower than normal shell.
    
- **Security:**
    
    - No automatic `sudo` or privilege escalation.
        
    - Strong safeguards around file deletion, package management, and networking.
        
- **Auditability:**
    
    - Log all AI-generated commands to a log file (configurable; can be disabled).
        
    - Optional “dry-run” mode.
        

---

## 3. High-level architecture

### 3.1 Processes and PTY layout

- `sshd` spawns `agentsh` as login shell.
    
- `agentsh` sets up a **pseudo-terminal (PTY)** and spawns an **execution shell** (bash/zsh/fish).
    
- agentsh:
    
    - Sits between user TTY and the execution shell PTY.
        
    - Intercepts input line-by-line only when necessary:
        
        - For `ai` invocations.
            
        - For features like a custom prompt/completion.
            
    - For normal commands it behaves as a transparent pass-through.
        

Visually:

```text
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

### 3.2 Internal components

1. **Input Router**
    
    - Reads user input.
        
    - Decides: forward to shell or send to AI.
        
    - Maintains a readline-style line editor (or uses existing libraries).
        
2. **AI Orchestrator**
    
    - Maintains conversation state (per session).
        
    - Calls LLM with:
        
        - System prompt.
            
        - Last N interactions.
            
        - Context (OS info, pwd, etc.)
            
    - Validates and parses AI output (JSON schema).
        
    - Returns actions to Execution Engine.
        
3. **Execution Engine**
    
    - Receives a list of steps from AI:
        
        - Shell commands.
            
        - File read/write actions.
            
        - “Ask user” / “display summary” actions.
            
    - Presents them to user for approval (if needed).
        
    - Executes via PTY (for commands) or direct filesystem calls.
        
    - Captures output for AI and user.
        
4. **Context Collector**
    
    - Provides context to AI:
        
        - OS and distribution.
            
        - Current working directory.
            
        - List of relevant files (bounded).
            
        - Recent command history.
            
    - Runs lightweight commands: `uname`, `ls`, `df -h`, etc. if AI requests.
        
5. **Config + Profile Manager**
    
    - Reads config from:
        
        - Global: `/etc/aishell/config.toml`
            
        - User: `~/.aishell/config.toml`
            
        - Project/local: `.aishellrc` in the current directory.
            
    - Merges config layers.
        
6. **Plugin System (optional v2)**
    
    - Plugins add new “tools” for AI:
        
        - Package manager abstraction.
            
        - Docker / Kubernetes helpers.
            
        - Cloud platform commands.
            
    - Likely implemented as:
        
        - Local executables following a small JSON-over-stdin/stdout protocol, or
            
        - Python/rust plugins loaded dynamically.
            

---

## 4. AI contract / JSON schema

### 4.1 System prompt (conceptual)

The system prompt should define:

- You are a **shell operations assistant**.
    
- You never run commands directly; you only propose actions in JSON.
    
- You aim for minimal, safe, auditable commands.
    
- You must explicitly label steps that are destructive or require sudo.
    
- You can request context via tools instead of guessing.
    

### 4.2 AI → agentsh action schema

Example JSON schema (concept-level):

```json
{
  "type": "object",
  "properties": {
    "kind": { "enum": ["answer_only", "command_sequence", "plan_and_commands"] },
    "summary": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "description": { "type": "string" },
          "shell_command": { "type": "string" },
          "needs_confirmation": { "type": "boolean" },
          "is_destructive": { "type": "boolean" },
          "requires_sudo": { "type": "boolean" },
          "working_directory": { "type": "string" }
        },
        "required": ["id", "description", "shell_command"]
      }
    }
  },
  "required": ["kind"]
}
```

agentsh:

- Validates this JSON.
    
- If invalid, asks AI to reformat or falls back to answer-only mode.
    
- Marks steps with `is_destructive` or `requires_sudo` for extra prompts.
    

---

## 5. UX flows

### 5.1 Basic “help me craft a command”

User:

```sh
$ ai find and kill whatever is listening on port 8080
```

AI response (rendered by agentsh):

```text
Plan:
 1. Find the PID using port 8080.
 2. Kill that process.

Proposed commands:
  #1: lsof -i :8080
  #2: kill -9 <PID_FROM_ABOVE>   [DESTRUCTIVE]

Run these? [y/e/n] y
```

Execution:

- agentsh runs command #1, shows output.
    
- Pauses and asks:
    
    - “Which PID should I kill? (or 'skip')”
        
- Substitutes PID, runs `kill`.
    
- Shows results.
    

### 5.2 “Explain that command”

User:

```sh
$ ai explain 'rsync -avz --delete src/ dst/'
```

AI responds:

- Pure text answer, no commands to run.
    
- agentsh prints explanation and returns to prompt.
    

### 5.3 “Fix the last error”

User:

```sh
$ make deploy
# ... fails with cryptic error ...
$ ai fix
```

agentsh sends to AI:

- The last command: `make deploy`.
    
- The error output (truncated).
    
- Relevant files if requested (e.g. Makefile snippet).
    

AI responds with:

- Explanation of the error.
    
- Proposed command(s) or file edits to fix it.
    

---

## 6. Configuration spec

### 6.1 Global + user config

**File:** `~/.aishell/config.toml` (example)

```toml
[ai]
provider = "openai"
model = "gpt-5.1-pro"
endpoint = "https://api.openai.com/v1/chat/completions"
api_key_env = "OPENAI_API_KEY"
max_tokens = 2048

[mode]
default = "assist"       # "off" | "assist" | "auto"

[safety]
require_confirmation_for_destructive = true
require_confirmation_for_sudo = true
log_ai_generated_commands = true
log_path = "~/.aishell/logs/commands.log"

[ui]
show_plan_before_execution = true
show_step_numbers = true
```

### 6.2 Per-project config

**File:** `.aishellrc` in a project directory.

Example:

```toml
[context]
include_files = ["docker-compose.yml", "Makefile", "README.md"]
exclude_patterns = ["*.log", "node_modules"]

[ai]
domain_hint = "web-app"
```

agentsh:

- When you `cd` into a directory, it looks up `.aishellrc`.
    
- Merges it into the current session config.
    

---

## 7. Device management specifics (over SSH)

### 7.1 Core idea

Once installed as a login shell on the device, you can:

```sh
ssh myserver
# lands you into agentsh
```

Then you can ask:

```sh
ai harden sshd config and restart the service
```

Expected AI plan:

1. Check OS and init system.
    
2. Locate `sshd_config`.
    
3. Propose changes (disable password auth, root login, etc.).
    
4. Write backup file.
    
5. Apply changes.
    
6. Restart `sshd` safely.
    

**Execution safeguards:**

- Always create backups for config files by default:
    
    - e.g. `/etc/ssh/sshd_config.aishell-YYYYMMDDHHMMSS.bak`
        
- Confirm diff before writing:
    
    - Show `diff -u old new` (or a snippet) and ask user to approve.
        

### 7.2 System inspection commands (read-only tools)

Built-in helper commands (for AI and user):

- `ai sysinfo`:
    
    - Gathers: `uname -a`, CPU, RAM, disk usage, OS version.
        
- `ai services`:
    
    - Lists running services (via systemd/service detection).
        
- `ai packages`:
    
    - Lists key packages and versions (for known stacks: nginx, postgres, docker, etc.).
        

AI can call these internally as “tools” to avoid guessing.

---

## 8. Security & safety model

### 8.1 Principles

- **Least surprise:** AI doesn’t silently run commands.
    
- **Least privilege:** AI never bypasses normal auth.
    
- **Auditability:** Commands are visible and loggable.
    

### 8.2 Destructive operations

Detect:

- `rm -rf`, `mkfs`, `dd` to block devices, `iptables` rules, etc.
    
- Package installs/removals (apt/yum/dnf/pacman, etc.).
    
- Service restarts/reloads on critical services (sshd, database).
    

Policy:

- Always require explicit confirmation.
    
- Optionally require a manual edit step.
    

### 8.3 Sudo and privileged actions

- agentsh never stores or handles sudo passwords directly.
    
- It may propose `sudo` commands, but:
    
    - User will see them and run them manually, OR
        
    - agentsh executes them, but sudo prompts user in the normal way.
        

Config option:

```toml
[safety]
allow_ai_to_execute_sudo = false  # default
```

If `false`, then:

- agentsh shows commands with `sudo` but doesn’t run them automatically, even after confirmation.
    
- Instead it prints them and suggests user copy/paste.
    

---

## 9. Plugin / tool API (outline)

To extend agentsh with structured “tools”:

### 9.1 Tool types

- `cmd.run`: run arbitrary shell commands (default tool).
    
- `fs.read_file`, `fs.write_file`: safe file ops with max size and path restrictions.
    
- `pkg.manage`: high-level package manager actions (install, remove, update).
    
- `svc.manage`: system service actions (start/stop/restart/status).
    

### 9.2 Example tool contract

Plugins implement a simple protocol over stdin/stdout:

- Input JSON:
    

```json
{
  "tool": "pkg.manage",
  "action": "install",
  "args": { "packages": ["nginx"], "assume_yes": true }
}
```

- Output JSON:
    

```json
{
  "ok": true,
  "stdout": "...",
  "stderr": "",
  "meta": { "duration_ms": 2300 }
}
```

The AI is instructed to call tools instead of raw commands when available; agentsh maps tool outputs back into the conversation.

---

## 10. Implementation roadmap (suggested phases)

### Phase 1 – Minimal viable shell

- PTY shim:
    
    - agentsh that spawns a real shell and passes everything through.
        
- Basic config reading.
    
- `ai` prefix command that:
    
    - Sends the user text + limited context to AI.
        
    - Returns answer-only (no execution).
        

### Phase 2 – Command proposal & execution

- Introduce JSON action schema.
    
- Implement Execution Engine:
    
    - Show plan + commands.
        
    - Confirm + execute commands via PTY.
        
- Add `ai run` and `ai explain`.
    

### Phase 3 – Autonomous workflows

- `ai do` with multi-step plan.
    
- Tool-calling for context gathering (OS detection, file inspection).
    
- Per-project `.aishellrc`.
    

### Phase 4 – Safety, plugins, polish

- Destructive command detection and policies.
    
- Logging and configurable privacy.
    
- Plugin API for package managers, services, etc.
    
- Better prompts, completions, and interactive UI tweaks.
    

---

If you’d like, next step I can:

- Turn this into a **concrete RFC-style document** (with numbered requirements), and/or
    
- Sketch actual **CLI UX** & **config file examples**, or
    
- Propose a specific implementation stack (e.g. Rust + tokio PTY + clap) and repo layout.