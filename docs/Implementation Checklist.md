# Implementation Checklist

A comprehensive checklist for building agentsh from scratch. Tasks are organized by phase and module, with dependencies noted.

---

## Phase 0: Project Setup & Scaffolding

### Repository Setup
- [x] Initialize git repository
- [x] Create `.gitignore` (Rust, IDE files, logs)
- [x] Initialize Cargo workspace: `cargo init`
- [x] Configure `Cargo.toml` with metadata and dependencies
- [x] Create directory structure:
  ```
  src/
  tests/
  docs/
  contrib/plugins/
  examples/
  scripts/
  ```

### Core Dependencies
- [x] Add `nix` or `portable-pty` for PTY operations
- [x] Add `tokio` with `full` features for async runtime
- [x] Add `rustyline` or `reedline` for line editing
- [x] Add `serde` and `serde_json` for serialization
- [x] Add `toml` for configuration parsing
- [x] Add `reqwest` with `json` feature for HTTP
- [x] Add `tracing` and `tracing-subscriber` for logging
- [x] Add `clap` for CLI argument parsing
- [x] Add `dirs` for locating config directories
- [x] Add `regex` for pattern matching

### CI/CD Setup
- [ ] Create `.github/workflows/ci.yml`
- [ ] Configure `cargo fmt` check
- [ ] Configure `cargo clippy` check
- [ ] Configure `cargo test` run
- [ ] Add code coverage (optional: `tarpaulin` or `llvm-cov`)

### Initial Documentation
- [x] Create README.md with project description
- [ ] Add LICENSE file
- [ ] Create CONTRIBUTING.md
- [ ] Create CHANGELOG.md

---

## Phase 1: Minimal Viable Shell (MVP)

### 1.1 CLI Entry Point (`src/main.rs`, `src/cli.rs`)

- [x] Define CLI arguments with clap:
  - [x] `--shell <PATH>` - Shell to spawn
  - [x] `--config <PATH>` - Config file path
  - [x] `--debug` - Enable debug logging
  - [x] `--version` - Print version
  - [x] `--help` - Print help
- [x] Parse CLI arguments
- [x] Initialize tracing subscriber
- [x] Load configuration
- [x] Start main event loop

### 1.2 Configuration Module (`src/config.rs`)

- [x] Define `Config` struct with all sections:
  - [x] `AiConfig` (provider, model, endpoint, api_key_env, max_tokens)
  - [x] `ModeConfig` (default mode, shell path, shell args)
  - [x] `SafetyConfig` (confirmation flags, logging, blocked patterns)
  - [x] `UiConfig` (prompt format, colors, display options)
  - [x] `ContextConfig` (include files, exclude patterns, limits)
- [x] Implement `Default` for all config structs
- [x] Implement config file loading:
  - [x] Load from `/etc/aishell/config.toml`
  - [x] Merge with `~/.aishell/config.toml`
  - [x] Support environment variable overrides
- [x] Implement config validation
- [x] Add error handling for missing/invalid config
- [x] Write unit tests for config merging

### 1.3 PTY Module (`src/pty.rs`)

- [x] Define `PtyShell` struct:
  - [x] `child_pid: Pid`
  - [x] `master_fd: RawFd`
  - [x] `reader: AsyncReader`
  - [x] `writer: AsyncWriter`
- [x] Implement `PtyShell::spawn()`:
  - [x] Create PTY pair (openpty)
  - [x] Fork process
  - [x] In child: setup as session leader, set controlling terminal
  - [x] In child: exec shell with login environment
  - [x] In parent: store master fd
- [x] Implement `PtyShell::resize()`:
  - [x] Handle SIGWINCH
  - [x] Set window size via ioctl
- [x] Implement async read from PTY master
- [x] Implement async write to PTY master
- [x] Implement `PtyShell::wait()` for child termination
- [x] Handle signals (SIGINT, SIGTERM, SIGWINCH)
- [ ] Write unit tests for PTY spawn
- [ ] Write integration test: spawn shell, run `echo hello`, verify output

### 1.4 Basic Event Loop (`src/main.rs`)

- [x] Set terminal to raw mode
- [x] Create PTY shell instance
- [x] Spawn async tasks:
  - [x] Task 1: Read stdin → write to PTY
  - [x] Task 2: Read PTY → write to stdout
  - [x] Task 3: Signal handler
- [x] Handle graceful shutdown
- [x] Restore terminal on exit
- [ ] Test: verify interactive programs work (vim, top, htop)

### 1.5 Simple AI Query (Answer-Only)

- [x] Create `src/ai_orchestrator.rs` stub
- [x] Implement basic LLM client:
  - [x] Build HTTP request with headers
  - [x] Send to configured endpoint
  - [x] Parse response
- [x] Implement simple `ai <query>` detection:
  - [x] Read line from PTY output
  - [x] Check if starts with `ai ` prefix
  - [x] Extract query text
- [x] Build minimal prompt:
  - [x] System prompt: "Answer in natural language only"
  - [x] User query
  - [x] Basic context (OS, cwd)
- [x] Display AI response to user
- [x] Handle network errors gracefully
- [ ] Test: `ai what time is it` returns text response

### Phase 1 Acceptance Criteria
- [x] `agentsh` spawns underlying shell
- [ ] All normal commands work (ls, cd, vim, ssh)
- [ ] Window resize works
- [ ] Ctrl-C, Ctrl-D work correctly
- [ ] `ai <question>` returns text answer
- [ ] Network failure doesn't break shell

---

## Phase 2: Command Proposal & Execution

### 2.1 JSON Action Schema (`src/ai_orchestrator.rs`)

- [x] Define `ActionKind` enum:
  - [x] `AnswerOnly`
  - [x] `CommandSequence`
  - [x] `PlanAndCommands`
- [x] Define `Step` struct:
  - [x] `id: String`
  - [x] `description: String`
  - [x] `shell_command: String`
  - [x] `needs_confirmation: bool`
  - [x] `is_destructive: bool`
  - [x] `requires_sudo: bool`
  - [x] `working_directory: Option<PathBuf>`
- [x] Define `AiAction` struct:
  - [x] `kind: ActionKind`
  - [x] `summary: Option<String>`
  - [x] `steps: Vec<Step>`
- [x] Implement serde deserialization
- [x] Implement JSON validation
- [x] Handle malformed JSON:
  - [x] Try parsing whole response
  - [x] Extract JSON from markdown code blocks
  - [x] Fall back to AnswerOnly
- [x] Write unit tests for JSON parsing
- [ ] Test edge cases (missing fields, extra fields, invalid types)

### 2.2 System Prompt Engineering

- [x] Create system prompt template
- [x] Define AI behavior rules:
  - [x] Never execute directly
  - [x] Always return JSON
  - [x] Mark destructive commands
  - [x] Mark sudo commands
- [x] Include schema definition in prompt
- [ ] Add example responses
- [ ] Test with various LLM providers

### 2.3 Input Router (`src/input_router.rs`)

- [x] Define routing modes:
  - [x] `Passthrough` - raw bytes to PTY
  - [x] `LineEditor` - readline-style input
- [ ] Implement mode detection:
  - [ ] Detect clean prompt (regex or marker)
  - [ ] Detect full-screen apps (alternate screen)
- [ ] Implement line editor integration:
  - [ ] Initialize rustyline/reedline
  - [ ] Configure history file
  - [ ] Configure completions (basic)
- [x] Implement AI prefix detection:
  - [x] `ai `, `@ai `, `ai run`, `ai explain`, `ai do`, `ai fix`
- [x] Route to appropriate handler
- [x] Write tests for routing logic

### 2.4 Execution Engine (`src/execution_engine.rs`)

- [x] Define execution state machine
- [x] Implement plan rendering:
  - [x] Display summary
  - [x] Display numbered steps
  - [x] Show `[DESTRUCTIVE]` / `[SUDO]` labels
- [x] Implement user prompt:
  - [x] `[y/e/n]` prompt
  - [x] Handle `y` - accept
  - [x] Handle `e` - edit mode
  - [x] Handle `n` - cancel
- [x] Implement edit mode:
  - [x] Show each command
  - [x] Allow editing
  - [x] Allow skipping steps
- [x] Implement command execution:
  - [x] Write command to PTY
  - [x] Stream output to user
  - [x] Detect command completion
  - [x] Capture exit code
- [x] Implement step-by-step execution:
  - [x] Execute steps sequentially
  - [x] Pause on failure
  - [x] Offer retry/skip/abort
- [ ] Write integration tests

### 2.5 Safety Module (`src/safety.rs`)

- [x] Define `SafetyFlags` struct:
  - [x] `is_destructive: bool`
  - [x] `requires_sudo: bool`
  - [x] `affects_critical_service: bool`
  - [x] `modifies_packages: bool`
- [x] Implement `analyze_command()`:
  - [x] Tokenize command
  - [x] Check destructive patterns (rm -rf, mkfs, dd)
  - [x] Check sudo usage
  - [x] Check service commands (systemctl, service)
  - [x] Check package commands (apt, yum, dnf, pacman)
- [x] Define pattern lists:
  - [x] Destructive filesystem patterns
  - [x] Block device patterns
  - [x] Network/firewall patterns
  - [x] Critical service patterns
- [x] Implement blocked command detection
- [x] Write comprehensive unit tests
- [ ] Test edge cases and false positives

### 2.6 `ai run` Command

- [x] Parse `ai run "task description"`
- [x] Build prompt for command generation
- [x] Send to AI orchestrator
- [x] Parse response as `CommandSequence`
- [x] Pass to execution engine
- [ ] Test end-to-end flow

### 2.7 `ai explain` Command

- [x] Parse `ai explain 'command'`
- [x] Build explanation-focused prompt
- [x] Force `AnswerOnly` response
- [x] Display explanation to user
- [ ] Test with various commands

### Phase 2 Acceptance Criteria
- [ ] `ai run "task"` proposes commands
- [ ] User can accept/edit/reject
- [ ] Commands execute in shell
- [ ] Destructive commands show warning
- [ ] Sudo commands are flagged
- [ ] `ai explain` returns explanations
- [ ] Malformed AI responses handled gracefully

---

## Phase 3: Autonomous Workflows

### 3.1 Multi-Step `ai do` (`src/ai_orchestrator.rs`, `src/execution_engine.rs`)

- [x] Parse `ai do "complex task"`
- [x] Build multi-step prompt:
  - [x] Request `PlanAndCommands` response
  - [x] Include detailed instructions
- [x] Implement plan confirmation:
  - [x] Show full plan overview
  - [x] Allow plan-level accept/reject
- [x] Implement sequential execution:
  - [x] Execute steps in order
  - [x] Show progress indicator
  - [x] Handle failures gracefully
- [x] Implement error recovery:
  - [x] On step failure, offer options
  - [x] Retry / Skip / Ask AI to fix / Abort
- [ ] Capture output for AI context (optional)
- [ ] Write integration tests

### 3.2 `ai fix` Command

- [x] Track last command executed
- [x] Track last stderr output
- [x] Parse `ai fix`
- [x] Build fix-focused prompt:
  - [x] Include failed command
  - [x] Include error output
  - [x] Request diagnosis and fix
- [x] Pass response to execution engine
- [ ] Test with various error scenarios

### 3.3 Context Collector (`src/context.rs`)

- [x] Implement system info collection:
  - [x] OS and version (`uname -a`)
  - [x] Distribution (parse `/etc/os-release`)
  - [x] CPU info
  - [x] Memory info
  - [x] Disk usage
- [x] Implement `ai sysinfo` command
- [x] Implement service listing:
  - [x] Detect init system (systemd, init, launchd)
  - [x] List running services
- [x] Implement `ai services` command
- [x] Implement package listing:
  - [x] Detect package manager
  - [x] List key packages
- [x] Implement `ai packages` command
- [x] Implement file reader:
  - [x] Size-limited reading
  - [x] Respect include/exclude patterns
- [x] Inject context into AI prompts
- [ ] Write unit tests

### 3.4 Per-Project Config (`.aishellrc`)

- [x] Detect directory changes:
  - [x] Monitor PWD changes
  - [x] Or hook into cd command
- [x] Load `.aishellrc` when entering directory
- [x] Merge project config with base config
- [x] Unload when leaving directory
- [ ] Test config inheritance

### Phase 3 Acceptance Criteria
- [x] `ai do` executes multi-step plans
- [x] Progress shown during execution
- [x] Failures handled with recovery options
- [x] `ai fix` diagnoses and proposes fixes
- [x] `ai sysinfo/services/packages` work
- [x] Per-project config loads on cd

---

## Phase 4: Safety, Plugins, Polish

### 4.1 Safety Hardening

- [x] Expand destructive patterns:
  - [x] Add more filesystem patterns (truncate, rsync --delete, :>)
  - [x] Add network patterns (ip route del, interface down, iptables -D/-X)
  - [x] Add database patterns (DROP, TRUNCATE, FLUSHALL, FLUSHDB)
- [x] Implement protected paths:
  - [x] `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`
  - [x] SSH keys (~/.ssh/id_rsa, id_ed25519, config)
  - [x] System configs (/etc/fstab, /etc/hosts, /boot, cron)
- [x] Add SafetyFlags for database and network operations
- [x] Implement blocked command rejection
- [ ] Add configurable safety levels
- [ ] Test with fuzzing/edge cases

### 4.2 Logging Module (`src/logging.rs`)

- [x] Define log entry structure:
  - [x] Session ID
  - [x] Timestamp
  - [x] Request
  - [x] AI response
  - [x] Commands executed
  - [x] Exit codes
- [x] Implement log writer:
  - [x] JSON lines format
  - [x] File rotation
  - [x] Configurable path
- [x] Implement secret redaction:
  - [x] API key patterns
  - [x] Password patterns
  - [x] Token patterns
- [x] Implement log configuration:
  - [x] Enable/disable
  - [x] Max size
  - [x] Retention count
- [x] Write unit tests (18 tests covering serialization, redaction, file ops)

### 4.3 Plugin System (`src/plugins/`)

- [x] Define plugin protocol:
  - [x] JSON request format (PluginRequest with id, tool, params, context)
  - [x] JSON response format (PluginResponse with success, result, error, output)
- [x] Implement plugin loader:
  - [x] Scan plugin directory
  - [x] Validate plugin executables
  - [x] Load manifest.json for tool definitions
  - [x] Register available tools
- [x] Implement plugin executor:
  - [x] Spawn plugin process
  - [x] Send request via stdin
  - [x] Read response from stdout
  - [x] Handle timeouts
- [x] Implement built-in tools:
  - [x] `cmd.run` - Run shell commands
  - [x] `fs.read_file` - Read file contents
  - [x] `fs.write_file` - Write/append to files
  - [x] `fs.list_dir` - List directory contents
- [ ] Update AI prompt with available tools
- [ ] Write plugin examples
- [ ] Document plugin API

### 4.4 UX Polish

- [ ] Implement prompt customization:
  - [ ] Variable substitution
  - [ ] Color support
  - [ ] Mode indicator
- [ ] Implement better completions:
  - [ ] File completion
  - [ ] Command completion
  - [ ] AI command completion
- [ ] Implement keybindings:
  - [ ] Alt-A for AI mode
  - [ ] Alt-M for mode toggle
  - [ ] Configurable bindings
- [ ] Add progress spinners for AI calls
- [ ] Improve error messages
- [ ] Add `--help` for AI commands

### 4.5 Testing & Quality

- [ ] Achieve 80%+ unit test coverage
- [ ] Write integration test suite:
  - [ ] PTY operations
  - [ ] AI interactions (mocked)
  - [ ] Config loading
  - [ ] Safety module
- [ ] Write end-to-end tests:
  - [ ] Full user flows
  - [ ] Error scenarios
  - [ ] Edge cases
- [ ] Performance benchmarks:
  - [ ] Command latency
  - [ ] Memory usage
  - [ ] PTY throughput
- [ ] Security audit:
  - [ ] Code review
  - [ ] Dependency audit (`cargo audit`)
  - [ ] Fuzzing (optional)

### Phase 4 Acceptance Criteria
- [ ] Extended safety patterns work
- [ ] Logging is complete and configurable
- [ ] Plugin system loads external tools
- [ ] Built-in tools work end-to-end
- [ ] Prompt and UI are polished
- [ ] Test coverage is adequate
- [ ] No critical security issues

---

## Phase 5: Release Preparation

### Documentation
- [ ] Complete all doc files
- [ ] Add inline rustdoc comments
- [ ] Generate API documentation
- [ ] Create installation guide
- [ ] Write troubleshooting guide

### Packaging
- [ ] Create release build script
- [ ] Build Linux x86_64 binary
- [ ] Build Linux ARM64 binary
- [ ] Build macOS x86_64 binary
- [ ] Build macOS ARM64 binary
- [ ] Create installation script
- [ ] Set up package repositories (optional):
  - [ ] Homebrew formula
  - [ ] AUR package
  - [ ] Debian package

### Release Process
- [ ] Define versioning scheme (semver)
- [ ] Create release checklist
- [ ] Set up GitHub releases
- [ ] Write release notes template
- [ ] Tag v0.1.0

### Launch
- [ ] Final testing on fresh systems
- [ ] Update README with final instructions
- [ ] Announce release
- [ ] Monitor for issues

---

## Dependency Matrix

| Module | Depends On |
|--------|------------|
| cli | config |
| pty | - |
| config | - |
| input_router | pty, config |
| ai_orchestrator | config, context |
| execution_engine | pty, safety, logging |
| context | pty |
| safety | config |
| logging | config |
| plugins | config |

## Build Order

1. `config` - No dependencies
2. `pty` - No dependencies
3. `safety` - Depends on config
4. `logging` - Depends on config
5. `context` - Depends on pty
6. `ai_orchestrator` - Depends on config, context
7. `input_router` - Depends on pty, config
8. `execution_engine` - Depends on pty, safety, logging
9. `plugins` - Depends on config
10. `cli/main` - Integrates everything

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| PTY complexity on different platforms | Use `portable-pty` crate, test on Linux + macOS early |
| AI response unreliability | Robust JSON parsing, graceful fallbacks |
| Security vulnerabilities | Regular audits, conservative defaults, extensive testing |
| Performance issues | Profile early, benchmark critical paths |
| User confusion | Clear documentation, helpful error messages |

---

## Success Metrics

### Phase 1
- Shell passes bash/zsh compatibility tests
- AI queries return responses in <3s

### Phase 2
- 95% of AI responses parse successfully
- Command execution matches manual execution

### Phase 3
- Multi-step tasks complete successfully 80%+ of the time
- Error recovery works smoothly

### Phase 4
- Zero critical security issues
- <100ms overhead for normal shell commands
- 80%+ test coverage

### Release
- Successful installs on Linux + macOS
- Positive user feedback
- <5 critical bugs in first week
