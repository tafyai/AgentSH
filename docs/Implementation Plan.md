Here’s a concrete implementation plan for **agentsh** based on the design spec. 

I’ll assume a **reference implementation in Rust**, but the architecture is language-agnostic. Where it matters I’ll call out specific crates or equivalents.

---

## 1. Foundational decisions

### 1.1 Tech stack (reference)

* **Language:** Rust (safety, good PTY + async ecosystem).
* **Key crates (or equivalents):**

  * PTY / process: `nix` + `libc` or `portable-pty`.
  * Async runtime: `tokio`.
  * Line editing: `rustyline` or `reedline`.
  * Config: `serde`, `toml`.
  * HTTP/LLM: `reqwest`.
  * JSON schema enforcement: `serde` with custom validation.
  * Logging: `tracing` + `tracing-subscriber` (file + stderr).

You could port this to Go (using `creack/pty`) or another compiled language later without changing the high-level plan.

### 1.2 High-level process model

At login:

1. `sshd` (or local `login`) invokes `agentsh` as the **login shell**.
2. `agentsh`:

   * Parses config.
   * Sets up a **PTY pair**.
   * Spawns the **execution shell** (user-configurable, default `$SHELL` or `/bin/bash`) attached to the PTY.
3. agentsh runs an **event loop**:

   * For **most input**: pass bytes between user TTY and PTY unchanged.
   * When an **AI entrypoint** is detected (e.g., line starts with `ai` and user hits Enter in line-editor mode), intercept the line and invoke the AI orchestration instead of sending it to the child shell.

We want **transparent passthrough** in the default case, so that agentsh “feels like a normal shell” when AI is idle.

---

## 2. Core modules & responsibilities

Map directly to the spec’s components.

### 2.1 `pty` module

**Responsibilities:**

* Create and manage PTY pair.
* Spawn the underlying shell as a child process.
* Bidirectional I/O:

  * `stdin` → PTY master.
  * PTY master → `stdout`/`stderr`.
* Window-size handling (SIGWINCH).

**Key types:**

```rust
struct PtyShell {
    child_pid: Pid,
    master_fd: RawFd,
}
```

**Tasks:**

* Implement `PtyShell::spawn(shell_path: &str, args: &[&str]) -> Result<PtyShell>`.
* Implement `resize(&self, cols: u16, rows: u16)`.
* Implement blocking/non-blocking read/write wrappers for the PTY master.

### 2.2 `input_router` module

**Responsibilities:**

* Decide when to:

  * Run in **raw passthrough** (interactive programs).
  * Use a **line editor** (for normal commands & AI prefixes).
* Detect `ai` commands and special forms (`ai run`, `ai explain`, `ai do`, `ai fix`, `ai sysinfo`, etc.).
* Maintain command history (integ with underlying shell where possible).

**Design:**

* Two modes:

  1. **Passthrough mode:** bytes are relayed between TTY and PTY; used when:

     * The shell is running full-screen apps (`vim`, `top`), or
     * We’re not at a “clean prompt” (we detect this heuristically via PTY output or a special prompt marker).
  2. **Line-editor mode:**

     * Use `rustyline` to read a line, with history + keybindings.
     * When user presses Enter:

       * If line starts with `ai` / `@ai` or matches configured prefix → route to AI.
       * Else → write the line to PTY with newline.

* Consider marking the prompt with an escape sequence like `\[\e]133;A\a\]` or a custom marker to detect when the shell is ready for a new command.

### 2.3 `ai_orchestrator` module

**Responsibilities:**

* Maintain per-session AI conversation context.
* Build prompts with:

  * System prompt.
  * Last N user/assistant messages.
  * Environment context (OS, cwd, etc.).
* Call LLM API and parse JSON action schema.
* Handle malformed responses robustly.

**Key types:**

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

**Main flows:**

* **`ai` / `ai run` / `ai do`:** expect `CommandSequence` or `PlanAndCommands`.
* **`ai explain`:** prefer `AnswerOnly`.
* **`ai fix`:** send last command + stderr as context.
* Fallback:

  * If JSON parsing fails:

    * Try to extract JSON segment heuristically.
    * If still failing, treat response as `AnswerOnly` and print text.

### 2.4 `execution_engine` module

**Responsibilities:**

* Take `AiAction` → present to user → execute steps via PTY.
* Enforce safety policies:

  * Confirm destructive / sudo commands.
  * Honor “no auto-sudo execution” config.
* Capture output for both:

  * User (real-time streaming).
  * AI (summaries or last N lines).

**Key behaviours:**

1. **Rendering plan:**

   * Show `summary` (if any).
   * Show numbered `steps`:

     * `[DESTRUCTIVE]` / `[SUDO]` labels.
2. **User controls:**

   * `y` / `Enter`: accept and run as-is.
   * `e`: open an inline editor prompt for per-step editing.
   * `n`: cancel.
3. **Running:**

   * For each step:

     * If `needs_confirmation` or flagged by safety rules → ask before running.
     * Change directory if `working_directory` is set (`cd` via PTY or chdir in parent).
     * Write `shell_command` plus newline to PTY.
     * Stream output until prompt detection or timeout.
   * Allow user to interrupt with Ctrl-C.

### 2.5 `context_collector` module

**Responsibilities:**

* Provide “context tools” to AI (either implicitly or via `ai sysinfo`, `ai services`, etc.).
* Implement read-only system inspection commands:

  * `sysinfo`: `uname -a`, CPU, RAM, disk usage, OS version.
  * `services`: list of services (systemd or alternative).
  * `packages`: key installed packages (for known stacks).

**Design:**

* Tools implemented as local Rust functions calling `cmd.run` on the PTY or via direct `std::process::Command`.
* Provide a **size-limited file inspection** helper:

  * Read at most N KB of each file.
  * Respect include/exclude patterns from `.aishellrc`.

### 2.6 `config` module

**Responsibilities:**

* Merge config from:

  * `/etc/aishell/config.toml` (system).
  * `~/.aishell/config.toml` (user).
  * `.aishellrc` (per-project; scanned on `cd`).
* Provide a single read-only `Config` object for other modules.

**Key types:**

```rust
struct AiConfig { /* provider, model, endpoint, key env, max_tokens */ }
struct SafetyConfig { /* require_confirmation_for_destructive, ... */ }
struct UiConfig { /* show_plan_before_execution, ... */ }

struct Config {
    ai: AiConfig,
    safety: SafetyConfig,
    ui: UiConfig,
    // ...
}
```

**Implementation:**

* Use `dirs` crate to locate home/config dirs.
* Implement a layered merge:

  1. Defaults (compiled in).
  2. Global config (if present).
  3. User config.
  4. Project config (`.aishellrc`), reloaded on directory change.

### 2.7 `safety` module

**Responsibilities:**

* Static analysis of proposed commands to detect:

  * Destructive operations: `rm -rf`, `mkfs`, `dd` to block devices, `iptables`, critical service restarts.
  * Package management changes: apt/yum/dnf/pacman install/remove.
  * `sudo` usage.
* Return flags that the Execution Engine uses to enforce extra confirmation.

**Approach:**

* Use simple pattern matching + tokenization:

  * Split by shell-like rules (basic).
  * Maintain list of patterns to match (`rm -rf`, `systemctl restart sshd`, etc.).
* Expose function:

```rust
fn analyze_command(cmd: &str) -> SafetyFlags
```

### 2.8 `logging` module

**Responsibilities:**

* Append AI-generated commands and context to a log file if enabled.
* Support:

  * Per-session ID and timestamp.
  * Redaction of secrets (best effort: detect tokens/password-like patterns).

**Format:**

* JSON lines or structured text:

  * `session_id`, `timestamp`, `request`, `ai_action`, `executed_commands`.

---

## 3. Phase-by-phase implementation plan

We’ll expand spec section 10 into more concrete tasks. 

### Phase 0 – Repo setup & scaffolding

**Goals:**

* Project skeleton, CI, basic dev ergonomics.

**Tasks:**

1. Create repo structure:

   ```text
   agentsh/
     src/
       main.rs
       pty.rs
       input_router.rs
       ai_orchestrator.rs
       execution_engine.rs
       context.rs
       config.rs
       safety.rs
       logging.rs
       cli.rs
     tests/
     contrib/
   ```

2. Add basic `main.rs`:

   * Parse CLI args: `--shell`, `--config`, `--debug`.
   * Initialize logging.

3. Configure CI:

   * `cargo fmt`, `cargo clippy`, `cargo test` on push.

4. Add basic docs:

   * README with “what is agentsh”.
   * `docs/architecture.md` summarizing the process and PTY model.

---

### Phase 1 – Minimal viable shell (MVP)

**Goals:**

* agentsh behaves like a transparent login shell.
* Basic config reading.
* Very simple `ai` command that returns **answer-only** (no execution yet).

#### 1.1 PTY shim & shell spawning

**Tasks:**

* Implement `PtyShell`:

  * `spawn` with:

    * Login environment (e.g., set `TERM`, `USER`, `HOME`).
    * Shell path from `$SHELL` or config, fallback `/bin/bash`.
  * Read loop:

    * Non-blocking read from PTY master → write to stdout.
  * Write loop:

    * Read from stdin → write to PTY master.

* Implement basic signal handling:

  * Forward SIGINT, SIGTERM, SIGWINCH to child.

**Acceptance criteria:**

* Running `agentsh` manually launches your normal shell.
* All typical commands (`ls`, `vim`, `ssh`) behave as expected.

#### 1.2 Configuration loading

**Tasks:**

* Implement `Config::load()`:

  * Load defaults.
  * Merge `/etc/aishell/config.toml` (if exists).
  * Merge `~/.aishell/config.toml`.
* Respect `ai` provider and endpoint, but not used heavily yet.

**Acceptance criteria:**

* Changing config values affects runtime behavior (e.g., logging level, default mode).

#### 1.3 Simple `ai` prefix (answer-only)

**Tasks:**

* Implement minimal **command detection**:

  * Only in line-editor mode (for now, we can cheat: run a simple read-line loop when we detect a clean prompt marker, or start with a simpler model where we intercept entire lines when in “command mode”).

* When user types:

  ```sh
  ai <free text>
  ```

  * Strip `ai` prefix.
  * Build prompt: system prompt + user text + minimal context (cwd, OS, etc.).
  * Call LLM with a **text-only instruction**: “Answer in natural language, no JSON, no commands to execute.”
  * Print response and return to shell prompt.

* Implement network error handling:

  * If AI unreachable → print clear message and do nothing else.
  * Ensure spec’s “degradability”: if AI is down, shell still works.

**Acceptance criteria:**

* `agentsh` works like a normal shell.
* `ai what is this machine?` prints a helpful, text-only response.
* No auto-execution of commands.

---

### Phase 2 – Command proposal & execution

**Goals:**

* Implement AI → JSON action schema.
* Add `ai run` and `ai explain`.
* Build Execution Engine for **single-shot** command sequences.

#### 2.1 JSON action schema support

**Tasks:**

* Implement `AiAction`, `Step` types and `serde` (de)serialization.
* Build **system prompt** that instructs the model to **always return valid JSON**, following the schema (with allowed `kind` values).
* Error handling:

  * Try to parse entire response as JSON.
  * If fails, look for first `{`…`}` block and parse.
  * If still fails:

    * Log parsing error.
    * Treat entire response as `AnswerOnly` and print it.

**Acceptance criteria:**

* For test prompts, AI returns usable JSON that parses into `AiAction`.

#### 2.2 Execution Engine (single sequence)

**Tasks:**

* Implement rendering of plan:

  ```text
  Plan:
    1. <step description>
    2. ...

  Proposed commands:
    #1: <cmd>  [DESTRUCTIVE][SUDO]
    #2: <cmd>
  ```

* Implement user confirmation:

  * Prompt: `Run these? [y/e/n]`
  * `y` / Enter: execute all steps (per-step confirmation if flagged).
  * `e`: interactive editing:

    * For now, show numbered steps and allow editing each `shell_command` line by line.
  * `n`: abort.

* Execution:

  * For each step:

    * Analyze with `safety::analyze_command`.
    * If `is_destructive` or `requires_sudo` and config says so → extra confirmation.
    * Write to PTY and stream output until prompt.

* Logging:

  * If `log_ai_generated_commands` is true → append to log.

**Acceptance criteria:**

* `ai run "list all docker containers"` proposes something like `docker ps`.
* User can accept and see results executed in the same shell session.
* Destructive commands require extra confirmation.

#### 2.3 `ai explain`

**Tasks:**

* `ai explain 'some command'`:

  * Build prompt focusing on explanation:

    * Force `kind = "answer_only"`.
  * AI returns explanation text.
  * Print explanation, no commands executed.

**Acceptance criteria:**

* `ai explain 'rsync -avz --delete src/ dst/'` prints a human-readable explanation and returns to prompt.

---

### Phase 3 – Autonomous workflows (`ai do`, `ai fix`, context tools, per-project config)

**Goals:**

* Implement multi-step `ai do`.
* Implement `ai fix` flow.
* Add context tools and `.aishellrc` support.

#### 3.1 Multi-step `ai do`

**Tasks:**

* New subcommand: `ai do "..."`.

* Prompt engineering:

  * Ask AI to produce `kind = "plan_and_commands"` with a clear, multi-step plan.

* UX flow:

  1. Show plan and full command sequence.
  2. Ask user to confirm.
  3. Execution Engine runs steps **sequentially**.
  4. After each step:

     * Optionally feed summarized output back to AI for “observe → think → next action” loop (in v1 this can be disabled; we can treat plan as static).

* Implement per-step pause/as-necessary:

  * On failure (non-zero exit code):

    * Stop and show error.
    * Offer: `Retry / Skip / Ask AI to fix (ai fix)`.

**Acceptance criteria:**

* `ai do "set up a dockerized postgres with persistent volume"` yields a multi-step plan and commands.
* User can step through plan and see incremental progress.

#### 3.2 `ai fix` (using last error)

**Tasks:**

* In `Execution Engine`, keep track of:

  * Last command string.
  * Last N lines of stderr.

* `ai fix`:

  * Build prompt with:

    * Last command.
    * Last error output.
    * Optional relevant files (e.g., Makefile snippet).
  * Ask AI to:

    * Explain the failure.
    * Propose one or more commands or edits to fix it.

* Execution:

  * Same as `ai run` flow: show plan, confirm, execute.

**Acceptance criteria:**

* After a failed `make deploy`, `ai fix` produces a plausible explanation and suggested fix commands.

#### 3.3 Context tools (`ai sysinfo`, `ai services`, `ai packages`)

**Tasks:**

* Implement built-in AI-visible tools:

  * `ai sysinfo`: run OS info commands, print to user.
  * `ai services`: list services via systemd or fallback.
  * `ai packages`: list installed versions for common stacks (e.g., nginx, postgres, docker).

* Integrate into AI prompts:

  * System prompt informs AI that these tools exist and are preferred over guessing.

**Acceptance criteria:**

* `ai sysinfo` provides a useful summary.
* AI uses these tools in its reasoning (validated with test prompts).

#### 3.4 Per-project config (`.aishellrc`)

**Tasks:**

* On directory change (detected via:

  * Observing PTY output or instrumenting a shell wrapper function), reload `.aishellrc` if present.
* Merge `context` and `ai` settings:

  * `include_files`, `exclude_patterns`, `domain_hint`.

**Acceptance criteria:**

* In a project dir with `.aishellrc`, AI sees extra file context and domain hint, reflected in responses.

---

### Phase 4 – Safety, plugins, polish

**Goals:**

* Harden destructive/sudo behaviour.
* Logging and privacy controls.
* Plugin/tool API (pkg/svc helpers).
* Better prompt/completion and interactive UX.

#### 4.1 Safety hardening

**Tasks:**

* Extend `safety::analyze_command` to cover:

  * Filesystem ops: `rm`, `mv`, `cp` on critical paths.
  * Device/block ops: `dd if=/dev/... of=/dev/...`.
  * Network/firewall: `iptables`, `ufw`.
  * Service restarts (`sshd`, databases).
  * Package installs/removes.

* Config options:

  * `require_confirmation_for_destructive`.
  * `require_confirmation_for_sudo`.
  * `allow_ai_to_execute_sudo` (default false).

* Enforce:

  * If `allow_ai_to_execute_sudo = false`:

    * Do not execute `sudo` commands directly.
    * Instead, print them (with copy/paste hint) or prompt user to confirm and run manually.

**Acceptance criteria:**

* `ai run "wipe this disk"` triggers strong warnings and requires explicit confirmations.
* Sudo commands are never run silently.

#### 4.2 Logging & privacy

**Tasks:**

* Implement structured logs:

  * Log per session:

    * Session ID.
    * AI requests/responses (optional).
    * Commands executed.
  * Respect `log_ai_generated_commands` and `log_path`.

* Add privacy options:

  * Disable logging entirely.
  * Redact obvious secrets (tokens, passwords).

**Acceptance criteria:**

* Logs are written when enabled and can be disabled via config.
* Log format is stable and documented.

#### 4.3 Plugin / tool API

**Tasks:**

* Define plugin protocol (JSON over stdin/stdout):

  * Input:

    ```json
    { "tool": "pkg.manage", "action": "install", "args": { "packages": ["nginx"], "assume_yes": true } }
    ```

  * Output:

    ```json
    { "ok": true, "stdout": "...", "stderr": "", "meta": { "duration_ms": 2300 } }
    ```

* Implement core tools:

  * `cmd.run` (default).
  * `fs.read_file`, `fs.write_file` (with path/size restrictions).
  * `pkg.manage`: wrappers around apt/yum/dnf/pacman.
  * `svc.manage`: wrappers around `systemctl` or service equivalents.

* Integrate with AI:

  * System prompt describes available tools and encourages using them instead of raw commands where appropriate.

**Acceptance criteria:**

* A simple external plugin (e.g. `agentsh-tool-example`) can be installed and called from AI.
* pkg/svc helpers work end-to-end.

#### 4.4 UX polish (prompts, completions, keybindings)

**Tasks:**

* Prompt customization:

  * `user@host:~/dir [ai:assist]$` format.
  * Configurable AI status indicator (off/assist/auto).
* Completion:

  * Reuse underlying shell completions where possible, or:

    * Use a fallback built-in completion (filenames, commands).
* Keybinding for AI:

  * e.g. `Alt-A` to send current line to AI instead of executing.

**Acceptance criteria:**

* Prompt clearly indicates AI mode.
* Basic completions (filenames, commands) work.
* Keybinding triggers AI flow smoothly.

---

## 4. AI prompt & contract details

### 4.1 System prompt (core content)

When calling the LLM, always prepend a system prompt along these lines:

* You are a **shell operations assistant**.
* You **never** run commands yourself; you only propose actions in **JSON**.
* Prefer minimal, safe, auditable commands.
* Mark destructive or sudo commands explicitly.
* Use tools (`sysinfo`, `services`, `packages`, `fs.read_file`, etc.) instead of guessing.
* For `ai explain`, respond with natural language only (`kind = "answer_only"`).

### 4.2 Per-command prompts

* `ai run`: “Propose one or more commands to accomplish this task. Use `command_sequence`.”
* `ai do`: “Create a multi-step plan (`plan_and_commands`) with descriptions and commands.”
* `ai fix`: “Explain the error and propose commands or edits to fix it.”

---

## 5. Testing & QA strategy

### 5.1 Unit tests

* `config` module: merging, defaults, overrides.
* `safety` module: destructive command detection.
* `ai_orchestrator`: parsing JSON into `AiAction`, malformed JSON handling.
* `logging`: correct log output and redaction.

### 5.2 Integration tests

* Spawn `agentsh` with a test shell (e.g. `/bin/sh`) under PTY and:

  * Run simple commands and ensure output matches expectations.
  * Simulate AI responses by mocking the LLM HTTP client:

    * Provide canned JSON.
    * Verify Execution Engine behavior.

### 5.3 Manual / exploratory tests

* Interactive use in:

  * Local terminal.
  * Over SSH.
* Edge cases:

  * Long-running commands, CTRL-C.
  * Full-screen TUI apps (`vim`, `top`).
  * AI backend unavailable (network off).

---

## 6. Deployment & integration plan

**Steps:**

1. **Build & install binary**:

   * Install to `/usr/local/bin/agentsh` (or similar).

2. **User-level opt-in:**

   * Instruct users to set shell:

     ```sh
     chsh -s /usr/local/bin/agentsh
     ```

   * Alternatively, use as wrapper:

     ```sh
     agentsh /bin/bash
     ```

3. **SSH integration:**

   * For servers, set login shell of specific users to `agentsh`.
   * Confirm that `ssh user@host` lands in agentsh with expected prompt.

4. **Rollback mechanism:**

   * Document how to change shell back if anything goes wrong.

---

If you’d like, I can next break this down into **GitHub issues / epics** with concrete task lists and dependencies, or propose **specific Rust crates and code sketches** for the tricky parts (PTY handling, line editor integration, and AI client).
