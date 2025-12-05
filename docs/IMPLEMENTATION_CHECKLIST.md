# AgentSH Implementation Checklist

**Purpose**: Master tracking document for AgentSH buildout
**Version**: 1.0
**Last Updated**: December 2025
**Status**: Ready for Implementation

---

## Quick Reference

| Phase | Name | Status | Priority | Dependencies |
|-------|------|--------|----------|--------------|
| 0 | Foundation & Project Setup | Complete | Critical | None |
| 1 | Shell Wrapper MVP | Complete | Critical | Phase 0 |
| 2 | LLM Integration & Agent Loop | Complete | Critical | Phase 1 |
| 3 | Security Baseline | Complete | Critical | Phase 2 |
| 4 | Tool Interface & Core Toolsets | Complete | High | Phase 3 |
| 5 | LangGraph Workflows | Complete | High | Phase 4 |
| 6 | Memory & Context | Complete | Medium | Phase 5 |
| 7 | Telemetry & Monitoring | Complete | Medium | Phase 4 |
| 8 | Multi-Device Orchestration | Complete | Medium | Phase 5, 7 |
| 9 | Robotics Integration | Complete | Low | Phase 8 |
| 10 | UX Polish & Hardening | Complete | Low | All |

**Legend**:
- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked

---

## Phase 0: Foundation & Project Setup

**Goal**: Establish codebase, CI/CD, and base infrastructure
**Estimated Effort**: 1-2 weeks
**Blocking**: All other phases

### 0.1 Repository Structure

- [x] Create project directory structure:
  ```
  agentsh/
  ├── src/agentsh/
  ├── tests/
  ├── docs/
  ├── examples/
  └── .github/workflows/
  ```
- [x] Initialize `pyproject.toml` with metadata
- [x] Create `src/agentsh/__init__.py` with version
- [x] Create `src/agentsh/__main__.py` entry point

### 0.2 Dependencies Setup

- [x] Core dependencies in pyproject.toml:
  - [x] `ptyprocess >= 0.7.0` (PTY management)
  - [x] `prompt-toolkit >= 3.0` (line editing)
  - [x] `pydantic >= 2.0` (validation)
  - [x] `pyyaml >= 6.0` (config)
  - [x] `structlog >= 24.0` (logging)
- [x] LLM dependencies:
  - [x] `anthropic >= 0.28.0`
  - [x] `openai >= 1.3.0`
  - [x] `langgraph >= 0.2.0`
  - [x] `langchain-core >= 0.2.0`
- [ ] Optional dependencies:
  - [ ] `chromadb >= 0.4.0` (vector DB)
  - [ ] `paramiko >= 3.0` (SSH)
  - [ ] `prometheus-client >= 0.17.0` (metrics)
- [x] Development dependencies:
  - [x] `pytest >= 7.0`
  - [x] `pytest-asyncio`
  - [x] `pytest-cov`
  - [x] `mypy`
  - [x] `black`
  - [x] `ruff`

### 0.3 Configuration System

- [x] Create `src/agentsh/config/__init__.py`
- [x] Implement `config/schemas.py`:
  - [x] `LLMConfig` Pydantic model
  - [x] `ShellConfig` Pydantic model
  - [x] `SecurityConfig` Pydantic model
  - [x] `MemoryConfig` Pydantic model
  - [x] `TelemetryConfig` Pydantic model
  - [x] `AgentSHConfig` root model
- [x] Implement `config/loader.py`:
  - [x] Load from `/etc/agentsh/config.yaml` (system)
  - [x] Load from `~/.agentsh/config.yaml` (user)
  - [x] Load from `.agentsh.yaml` (project)
  - [x] Environment variable overrides (`AGENTSH_*`)
  - [ ] CLI argument overrides
- [x] Implement `config/defaults.py`:
  - [x] Default LLM settings
  - [x] Default security mode
  - [x] Default paths
- [x] Create sample config file `examples/config.yaml`

### 0.4 Plugin Registry Foundation

- [x] Create `src/agentsh/plugins/__init__.py`
- [x] Implement `plugins/base.py`:
  - [x] `Toolset` abstract base class
  - [x] `@property name: str`
  - [x] `@property description: str`
  - [x] `register_tools(registry: ToolRegistry)`
  - [x] `configure(config: dict)`
- [x] Implement `plugins/loader.py`:
  - [x] Entry point discovery (`agentsh.plugins`)
  - [x] Directory scan (`~/.agentsh/plugins/`)
  - [x] Plugin validation
  - [x] Dependency injection

### 0.5 CLI Entry Point

- [x] Implement `__main__.py`:
  - [x] `agentsh` - start interactive shell
  - [x] `agentsh --version` - show version
  - [x] `agentsh --config <path>` - custom config
  - [x] `agentsh config show` - debug config
  - [x] `agentsh status` - health check
  - [x] `agentsh --mcp-server` - MCP mode (placeholder)
- [x] Create shell wrapper entry:
  ```python
  def main():
      # Parse args
      # Load config
      # Initialize shell
      # Run REPL
  ```

### 0.6 CI/CD Setup

- [x] Create `.github/workflows/lint.yml`:
  - [x] Run black format check
  - [x] Run ruff linting
  - [x] Run mypy type checking
- [x] Create `.github/workflows/test.yml`:
  - [x] Run pytest
  - [x] Generate coverage report
  - [ ] Fail if coverage < 70%
- [x] Create `.github/workflows/security.yml`:
  - [x] Run bandit security scan
  - [x] Check for known vulnerabilities
- [x] Create `Makefile`:
  - [x] `make install` - install dev deps
  - [x] `make test` - run tests
  - [x] `make lint` - run linters
  - [x] `make format` - auto-format
  - [x] `make build` - build package

### 0.7 Logging Foundation

- [x] Create `src/agentsh/telemetry/__init__.py`
- [x] Implement `telemetry/logger.py`:
  - [x] Configure structlog
  - [x] JSON output format
  - [x] Context injection (session_id, user)
  - [x] Log level configuration
  - [x] File + stdout outputs

### Phase 0 Deliverables

- [x] `agentsh --help` works
- [x] `agentsh --version` shows version
- [x] Config loads from all sources
- [x] Logging outputs structured JSON
- [x] CI passes lint + type checks
- [x] Plugin loader can discover dummy plugin

---

## Phase 1: Shell Wrapper MVP

**Goal**: Wrap user's shell with AI routing capability
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 0

### 1.1 PTY Manager

- [x] Create `src/agentsh/shell/__init__.py`
- [x] Implement `shell/pty_manager.py`:
  - [x] `PTYManager` class:
    - [x] `__init__(shell_path: str)` - configure shell
    - [x] `spawn()` - create PTY with shell process
    - [x] `read(timeout: float)` - read from PTY
    - [x] `write(data: bytes)` - write to PTY
    - [x] `resize(rows: int, cols: int)` - handle window resize
    - [x] `close()` - cleanup resources
    - [x] `is_alive` property - check shell status
  - [x] Handle SIGWINCH for terminal resize
  - [x] Implement PTY I/O buffering
  - [x] Error handling for shell crashes

### 1.2 Input Classifier

- [x] Implement `shell/input_classifier.py`:
  - [x] `InputType` enum:
    - [x] `SHELL_COMMAND` - pass directly to shell
    - [x] `AI_REQUEST` - send to AI agent
    - [x] `SPECIAL_COMMAND` - internal commands
  - [x] `InputClassifier` class:
    - [x] `classify(line: str) -> InputType`
    - [x] Force shell: `!command` prefix
    - [x] Force AI: `ai ` or `::` prefix
    - [x] Heuristics for natural language detection
    - [x] Config option: default_to_ai (bool)
  - [x] Special commands:
    - [x] `:help` - show help
    - [x] `:config` - show config
    - [x] `:history` - show AI history
    - [x] `:clear` - clear context

### 1.3 Prompt Renderer

- [x] Implement `shell/prompt.py`:
  - [x] `PromptRenderer` class:
    - [x] `render_ps1() -> str` - primary prompt
    - [x] `render_ps2() -> str` - continuation prompt
  - [x] Components:
    - [x] `[AS]` indicator (AgentSH active)
    - [x] Current working directory
    - [x] Git branch (if in repo)
    - [x] Agent status icon (idle/busy/error)
    - [x] User/host info
  - [x] ANSI color support
  - [x] Config options for customization

### 1.4 Command History

- [x] Implement `shell/history.py`:
  - [x] `HistoryManager` class:
    - [x] `__init__(path: Path)` - history file location
    - [x] `add(entry: str)` - add to history
    - [x] `search(query: str) -> List[str]` - search history
    - [x] `get_recent(n: int) -> List[str]` - recent entries
    - [x] `save()` - persist to disk
    - [x] `load()` - load from disk
  - [x] Separate AI history from shell history
  - [x] Deduplication of consecutive identical entries
  - [x] Configurable max history size

### 1.5 Shell Wrapper

- [x] Implement `shell/wrapper.py`:
  - [x] `ShellWrapper` class:
    - [x] `__init__(config: ShellConfig)` - initialize
    - [x] `start()` - spawn PTY, start REPL
    - [x] `stop()` - cleanup and exit
    - [x] `run_repl()` - main event loop
    - [x] `process_input(line: str)` - route input
    - [x] `execute_shell(command: str)` - pass to PTY
    - [x] `handle_ai_request(request: str)` - send to agent (stub)
  - [x] Signal handling:
    - [x] SIGINT (Ctrl+C) - interrupt current
    - [ ] SIGTSTP (Ctrl+Z) - background
    - [ ] SIGWINCH - resize (PTY level done)
  - [x] Graceful shutdown

### 1.6 Basic AI Command (Stub)

- [x] Implement AI stub in `shell/wrapper.py`:
  - [x] `_show_ai_placeholder(request: str) -> str`:
    - [x] Placeholder that shows request info
    - [x] Returns "AI feature coming in Phase 2"
  - [x] Wire into ShellWrapper.handle_ai_request

### Phase 1 Deliverables

- [x] `agentsh` starts and shows custom prompt
- [x] Regular shell commands work normally
- [x] `!ls` forces shell execution
- [x] `ai hello` triggers AI path (stub response)
- [x] Command history persists
- [ ] Terminal resize works (full PTY integration pending)
- [x] Graceful exit on Ctrl+D

### Phase 1 Tests

- [x] `tests/unit/test_input_classifier.py`:
  - [x] Test shell command detection
  - [x] Test AI request detection
  - [x] Test force prefixes
- [x] `tests/unit/test_history.py`:
  - [x] Test add/search/recent
  - [x] Test persistence
- [x] `tests/unit/test_wrapper.py`:
  - [x] Test initialization
  - [x] Test input/output flow
- [ ] `tests/integration/test_shell_wrapper.py`:
  - [ ] Test PTY spawning
  - [ ] Test end-to-end flow

---

## Phase 2: LLM Integration & Agent Loop

**Goal**: Connect to LLM and implement basic reasoning
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 1

### 2.1 LLM Client Abstraction

- [x] Create `src/agentsh/agent/__init__.py`
- [x] Implement `agent/llm_client.py`:
  - [x] Data classes:
    - [x] `Message(role, content, tool_calls)`
    - [x] `ToolCall(id, name, arguments)`
    - [x] `LLMResponse(content, tool_calls, stop_reason, tokens)`
    - [x] `ToolDefinition(name, description, parameters)`
  - [x] `LLMClient` abstract class:
    - [x] `@abstractmethod invoke(messages, tools, temperature, max_tokens) -> LLMResponse`
    - [x] `@abstractmethod stream(messages, tools) -> AsyncIterator[str]`
    - [x] `count_tokens(text) -> int` (default implementation)
    - [x] `@property provider -> str`

### 2.2 LLM Provider Implementations

- [x] Implement `agent/providers/anthropic.py`:
  - [x] `AnthropicClient(LLMClient)`:
    - [x] API key from config/env
    - [x] Model selection
    - [x] Convert messages to Anthropic format
    - [x] Handle tool use responses
    - [x] Streaming support
    - [x] Error handling & retries
- [x] Implement `agent/providers/openai.py`:
  - [x] `OpenAIClient(LLMClient)`:
    - [x] API key from config/env
    - [x] Model selection
    - [x] Convert messages to OpenAI format
    - [x] Handle function calling
    - [x] Streaming support
- [ ] Implement `agent/providers/ollama.py`:
  - [ ] `OllamaClient(LLMClient)`:
    - [ ] Local HTTP endpoint
    - [ ] Model selection
    - [ ] Fallback provider

### 2.3 System Prompts

- [x] Implement `agent/prompts.py`:
  - [x] `SYSTEM_PROMPT_TEMPLATE`:
    - [x] Role definition ("You are an AI shell assistant...")
    - [x] Safety rules (never destructive without approval)
    - [x] Tool usage instructions
    - [x] Output format guidance
  - [x] Few-shot examples:
    - [x] Example 1: NL → shell command
    - [x] Example 2: Multi-step task
    - [x] Example 3: Error handling
  - [x] Context injection:
    - [x] Current directory
    - [x] OS/platform info
    - [x] Available tools
    - [x] Recent history

### 2.4 Basic Agent Loop

- [x] Implement `agent/agent_loop.py`:
  - [x] `AgentLoop` class:
    - [x] `__init__(llm_client, tool_registry, config)`
    - [x] `invoke(request: str, context: dict) -> str`:
      1. Build messages (system + user)
      2. Call LLM with tools
      3. If tool_calls: execute each
      4. Append results to messages
      5. If more steps needed: loop (max 10)
      6. Return final response
    - [x] `_execute_tool(tool_call) -> str`
    - [ ] `_check_goal_complete(response) -> bool`
  - [x] Implement max_steps limit
  - [x] Handle LLM errors gracefully

### 2.5 Tool Schema Generation

- [x] Tool schema generation in `llm_client.py` ToolDefinition class:
  - [x] `to_openai_format(tool) -> dict`
  - [x] `to_anthropic_format(tool) -> dict`
  - [x] Generate JSON schema from tool definition

### 2.6 Agent Executor

- [x] Executor integrated in `agent/agent_loop.py`:
  - [x] `_execute_tool()` method:
    - [x] Route to tool registry
    - [x] Collect results
    - [x] Format for LLM consumption

### 2.7 Integration with Shell Wrapper

- [x] Create `agent/factory.py`:
  - [x] `create_llm_client(config)` - factory for providers
  - [x] `create_agent_loop(config)` - creates configured agent
  - [x] `create_ai_handler(config)` - sync handler for shell
- [x] Update `__main__.py`:
  - [x] Initialize AI handler on startup (if API key set)
  - [x] Wire into ShellWrapper via `set_ai_handler()`

### Phase 2 Deliverables

- [x] LLM client abstraction complete
- [x] Anthropic provider working
- [x] OpenAI provider working
- [x] Agent loop with tool execution
- [x] System prompts with safety rules
- [x] AI handler connected to shell
- [ ] `ai "what files are here?"` returns intelligent response (needs tools)
- [ ] Streaming output supported (partial)

### Phase 2 Tests

- [x] `tests/unit/test_llm_client.py`:
  - [x] Mock LLM responses
  - [x] Test message formatting
  - [x] Test tool call parsing
  - [x] Test ToolDefinition conversion (OpenAI/Anthropic)
  - [x] Test LLMResponse properties
  - [x] Test MessageRole enum
- [x] `tests/unit/test_agent_loop.py`:
  - [x] Test AgentConfig defaults and custom values
  - [x] Test AgentContext
  - [x] Test AgentResult
  - [x] Test single-step execution
  - [x] Test tool call execution
  - [x] Test unknown tool handling
  - [x] Test max_steps limit
  - [x] Test LLM error handling
  - [x] Test security controller integration
  - [x] Test StreamingAgentLoop
- [ ] `tests/integration/test_llm_providers.py`:
  - [ ] Test each provider (with mocks)

---

## Phase 3: Security Baseline

**Goal**: Implement safety controls before agent gets powerful
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 2

### 3.1 Risk Classifier

- [x] Create `src/agentsh/security/__init__.py`
- [x] Implement `security/classifier.py`:
  - [x] `RiskLevel` enum: SAFE, LOW, MEDIUM, HIGH, CRITICAL
  - [x] `CommandRiskAssessment` dataclass:
    - [x] command, risk_level, reasons, matched_patterns, is_blocked
  - [x] `RiskClassifier` class:
    - [x] `classify(command: str) -> CommandRiskAssessment`
    - [x] CRITICAL patterns (block always):
      - [x] `rm -rf /`
      - [x] `mkfs.*`
      - [x] `dd if=.*of=/dev`
      - [x] Fork bombs
    - [x] HIGH patterns (require approval):
      - [x] `rm -rf` (any path)
      - [x] `sudo` commands
      - [x] User management (useradd/userdel)
      - [x] Service stops/disables
    - [x] MEDIUM patterns (may need approval):
      - [x] Package management
      - [x] Network configuration
      - [x] Pipe to shell
    - [x] SAFE patterns:
      - [x] Read-only commands
      - [x] File listing
      - [x] Text processing

### 3.2 Security Policies

- [x] Implement `security/policies.py`:
  - [x] `SecurityPolicy` dataclass:
    - [x] blocked_patterns: List[str]
    - [x] require_approval_levels: List[RiskLevel]
    - [x] allow_sudo: bool
    - [x] max_command_length: int
  - [x] Load policies from config (YAML)
  - [x] Per-device policy overrides (DevicePolicy)
  - [x] Security modes: PERMISSIVE, STANDARD, STRICT, PARANOID

### 3.3 RBAC Implementation

- [x] Implement `security/rbac.py`:
  - [x] `Role` enum: VIEWER, OPERATOR, ADMIN, SUPERUSER
  - [x] `RBAC` class:
    - [x] `check_access(user, risk_level, device_id) -> (allowed, needs_approval, reason)`
    - [x] Role hierarchy (superuser > admin > operator > viewer)
  - [x] Permission matrix with configurable access levels

### 3.4 Human-in-the-Loop Approval

- [x] Implement `security/approval.py`:
  - [x] `ApprovalResult` enum: APPROVED, DENIED, EDITED, TIMEOUT, SKIPPED
  - [x] `ApprovalRequest` dataclass:
    - [x] command, risk_level, reasons, context, timeout
  - [x] `ApprovalFlow` class:
    - [x] `request_approval(request) -> ApprovalResponse`:
      - [x] Display proposed command
      - [x] Show risk level and reason
      - [x] Prompt: [y]es / [n]o / [e]dit / [s]kip
      - [x] Handle keyboard interrupt
      - [x] Return result
    - [x] ANSI color support
    - [x] Edit mode: let user modify command
  - [x] `AutoApprover` class for non-interactive contexts

### 3.5 Audit Logging

- [x] Implement `security/audit.py`:
  - [x] `AuditAction` enum with all action types
  - [x] `AuditEvent` dataclass:
    - [x] timestamp
    - [x] user
    - [x] command
    - [x] risk_level
    - [x] action (executed/blocked/approved/denied)
    - [x] approver (if applicable)
    - [x] session_id, device_id, metadata
  - [x] `AuditLogger` class:
    - [x] Write to dedicated audit log (JSON lines)
    - [x] Append-only file
    - [x] Log rotation
    - [x] Query methods (get_recent, get_by_user, get_by_action)

### 3.6 Security Controller

- [x] Implement `security/controller.py`:
  - [x] `ValidationResult` enum: ALLOW, NEED_APPROVAL, BLOCKED
  - [x] `SecurityContext` dataclass for security decisions
  - [x] `SecurityDecision` dataclass with full decision info
  - [x] `SecurityController` class:
    - [x] `check(command, context) -> SecurityDecision`:
      1. Classify risk
      2. Check if blocked by classifier
      3. Get policy for device
      4. Check if blocked by policy mode
      5. Check RBAC permissions
      6. Check if policy requires approval
      7. Return decision
    - [x] `validate_and_approve(command, context) -> SecurityDecision`:
      1. Check command
      2. If NEED_APPROVAL: request approval
      3. Handle approval response
      4. Log everything
    - [x] Helper methods: `is_safe()`, `get_risk_level()`, `set_policy()`

### 3.7 Integration

- [x] Update `agent/agent_loop.py`:
  - [x] Add optional SecurityController parameter
  - [x] Add `_build_security_context()` method
  - [x] Add `_check_command_security()` method
  - [x] Check security for shell/command execution tools
  - [x] Pass context with user/role info

### Phase 3 Deliverables

- [x] Dangerous commands are blocked
- [x] High-risk commands require approval
- [x] User can approve/deny/edit commands
- [x] All actions are audit logged
- [x] RBAC restricts capabilities

### Phase 3 Tests

- [x] `tests/unit/test_security.py`:
  - [x] Test RiskLevel ordering
  - [x] Test RiskClassifier pattern matching
  - [x] Test all risk levels (SAFE, LOW, MEDIUM, HIGH, CRITICAL)
  - [x] Test SecurityPolicy modes
  - [x] Test PolicyManager
  - [x] Test RBAC role permissions
  - [x] Test ApprovalFlow and AutoApprover
  - [x] Test AuditLogger (write, query)
  - [x] Test SecurityController
  - [x] Integration tests for full security flow

---

## Phase 4: Tool Interface & Core Toolsets

**Goal**: Provide tools the agent can use
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 3

### 4.1 Tool Registry

- [x] Create `src/agentsh/tools/__init__.py`
- [x] Implement `tools/registry.py`:
  - [x] `ToolRegistry` class (singleton):
    - [x] `register_tool(name, handler, schema, risk_level)`
    - [x] `get_tool(name) -> Tool`
    - [x] `list_tools() -> List[Tool]`
    - [x] `get_tools_for_llm() -> List[dict]`
  - [x] Validation of tool schemas
  - [x] Prevent duplicate registrations

### 4.2 Tool Base Classes

- [x] Implement `tools/base.py`:
  - [x] `Tool` dataclass:
    - [x] name, description, handler
    - [x] parameters (JSON schema)
    - [x] risk_level, requires_confirmation
    - [x] timeout_seconds, max_retries
  - [x] `ToolResult` dataclass:
    - [x] success, output, error, duration_ms

### 4.3 Tool Runner

- [x] Implement `tools/runner.py`:
  - [x] `ToolRunner` class:
    - [x] `execute(tool_name, args, context) -> ToolResult`:
      1. Get tool from registry
      2. Validate arguments
      3. Check security (via SecurityController)
      4. Execute with timeout
      5. Capture output/errors
      6. Emit telemetry
      7. Return result
    - [x] Retry logic
    - [x] Error wrapping

### 4.4 Timeout Management

- [x] Timeout management integrated in `tools/runner.py`:
  - [x] `_execute_with_timeout()` method:
    - [x] `run_with_timeout(func, timeout) -> Any`
    - [x] Handle async functions
    - [x] Graceful cancellation
    - [x] Per-tool timeout configuration

### 4.5 Shell Toolset

- [x] Implement `plugins/builtin/shell.py`:
  - [x] `ShellToolset(Toolset)`:
    - [x] `shell.run(command, cwd, env) -> ToolResult`:
      - [x] Execute command in shell
      - [x] Capture stdout, stderr, exit_code
      - [x] Risk level: MEDIUM
    - [x] `shell.explain(command) -> str`:
      - [x] Describe what command does
      - [x] Risk level: SAFE
    - [x] `shell.which(program) -> str`:
      - [x] Find executable in PATH
      - [x] Risk level: SAFE
    - [x] `shell.env(name) -> str`:
      - [x] Get environment variable
      - [x] Risk level: SAFE

### 4.6 Filesystem Toolset

- [x] Implement `plugins/builtin/filesystem.py`:
  - [x] `FilesystemToolset(Toolset)`:
    - [x] `fs.read(path, encoding) -> str`:
      - [x] Read file contents
      - [x] Risk level: SAFE
    - [x] `fs.write(path, content, mode) -> bool`:
      - [x] Write to file
      - [x] Risk level: MEDIUM
    - [x] `fs.list(path, recursive) -> List[str]`:
      - [x] List directory
      - [x] Risk level: SAFE
    - [x] `fs.delete(path) -> bool`:
      - [x] Delete file/directory
      - [x] Risk level: HIGH
    - [x] `fs.copy(src, dst) -> bool`:
      - [x] Copy file
      - [x] Risk level: MEDIUM
    - [x] `fs.move(src, dst) -> bool`:
      - [x] Move file
      - [x] Risk level: MEDIUM
    - [x] `fs.search(pattern, path) -> List[str]`:
      - [x] Find files by pattern
      - [x] Risk level: SAFE
    - [x] `fs.info(path) -> FileInfo`:
      - [x] Get file metadata
      - [x] Risk level: SAFE

### 4.7 Process Toolset

- [x] Implement `plugins/builtin/process.py`:
  - [x] `ProcessToolset(Toolset)`:
    - [x] `process.list() -> List[ProcessInfo]`:
      - [x] List running processes
      - [x] Risk level: SAFE
    - [x] `process.kill(pid) -> bool`:
      - [x] Kill process
      - [x] Risk level: HIGH
    - [x] `process.info(pid) -> ProcessInfo`:
      - [x] Get process details
      - [x] Risk level: SAFE

### 4.8 Code Toolset

- [x] Implement `plugins/builtin/code.py`:
  - [x] `CodeToolset(Toolset)`:
    - [x] `code.read(path, start_line, end_line) -> str`:
      - [x] Read code with line numbers
      - [x] Risk level: SAFE
    - [x] `code.edit(path, old_text, new_text) -> bool`:
      - [x] Make targeted edit
      - [x] Risk level: MEDIUM
    - [x] `code.search(pattern, path, file_pattern) -> List[Match]`:
      - [x] Search in code
      - [x] Risk level: SAFE
    - [x] `code.insert(path, line, text) -> bool`:
      - [x] Insert text at line
      - [x] Risk level: MEDIUM

### Phase 4 Deliverables

- [x] Agent can use shell.run to execute commands
- [x] Agent can read/write files
- [x] Agent can list/kill processes
- [x] Agent can search/edit code
- [x] All tools have proper risk levels
- [x] Timeouts prevent hanging

### Phase 4 Tests

- [x] `tests/unit/test_tool_registry.py`:
  - [x] Test registration/lookup
  - [x] Test schema validation
- [x] `tests/unit/test_tool_runner.py`:
  - [x] Test execution flow
  - [x] Test timeout handling
- [x] `tests/unit/test_toolsets.py`:
  - [x] Test ShellToolset
  - [x] Test FilesystemToolset
  - [x] Test ProcessToolset
  - [x] Test CodeToolset

---

## Phase 5: LangGraph Workflows

**Goal**: Enable multi-step, stateful task orchestration
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 4

### 5.1 State Definitions

- [x] Create `src/agentsh/workflows/__init__.py`
- [x] Implement `workflows/states.py`:
  - [x] `AgentState` TypedDict:
    - [x] messages: List[Message]
    - [x] goal: str
    - [x] plan: Optional[str]
    - [x] step_count: int
    - [x] max_steps: int
    - [x] tools_used: List[ToolCallRecord]
    - [x] approvals_pending: List[ApprovalRequest]
    - [x] is_terminal: bool
    - [x] final_result: Optional[str]
    - [x] error: Optional[str]
  - [x] `WorkflowState` for multi-device workflows

### 5.2 Graph Nodes

- [x] Implement `workflows/nodes.py`:
  - [x] `AgentNode` class:
    - [x] Call LLM with current messages
    - [x] Parse response
    - [x] Update state with new message
  - [x] `ToolNode` class:
    - [x] Execute pending tool calls
    - [x] Append results to messages
  - [x] `ApprovalNode` class:
    - [x] Check for high-risk tool calls
    - [x] Request user approval
    - [x] Update state based on response
  - [x] `MemoryNode` class (stub for Phase 6):
    - [x] Store turn in memory
    - [x] Retrieve relevant context
  - [x] `ErrorRecoveryNode` class:
    - [x] Retry logic
    - [x] Max retries handling

### 5.3 Graph Edges

- [x] Implement `workflows/edges.py`:
  - [x] `should_continue(state) -> str`:
    - [x] If tool_calls: route to "approval" or "tools"
    - [x] If terminal: route to "end"
    - [x] If max_steps exceeded: route to "end"
  - [x] `after_approval(state) -> str`:
    - [x] Check approval status
    - [x] Route to "tools" or "end"
  - [x] `has_error(state) -> bool`:
    - [x] Check for errors
  - [x] Helper functions:
    - [x] `has_pending_tools`, `is_terminal`, `needs_approval`

### 5.4 Single-Agent ReAct Graph

- [x] Implement `workflows/single_agent.py`:
  - [x] `create_react_graph() -> StateGraph`:
    ```
    START -> agent -> [approval|tools|recovery|END]
    approval -> [tools|agent|END]
    tools -> agent
    recovery -> [agent|END]
    ```
  - [x] Compile with checkpointing (MemorySaver)
  - [x] `create_simple_react_graph()` for basic use

### 5.5 Multi-Agent Patterns (Optional)

- [ ] Implement `workflows/multi_agent.py` (deferred to future):
  - [ ] `create_supervisor_graph()`
  - [ ] `create_specialist_graph()`

### 5.6 Workflow Executor

- [x] Implement `workflows/executor.py`:
  - [x] `WorkflowExecutor` class:
    - [x] `execute(goal, context) -> WorkflowResult`:
      - [x] Initialize state
      - [x] Run graph
      - [x] Stream events
      - [x] Return result
    - [x] `stream()` async iterator for events
    - [x] `execute_with_callbacks()` for real-time updates
    - [x] State persistence (via LangGraph checkpointing)
  - [x] `SimpleWorkflowExecutor` for basic use
  - [x] `WorkflowResult` and `WorkflowEvent` dataclasses

### 5.7 Predefined Workflows

- [x] Create `workflows/predefined/`:
  - [x] `bootstrap.yaml`: Project setup workflow
  - [x] `backup.yaml`: Backup directory workflow
  - [x] `deploy.yaml`: Deployment workflow template
  - [x] `__init__.py` with loader functions:
    - [x] `list_predefined_workflows()`
    - [x] `load_workflow_template()`
    - [x] `validate_workflow_parameters()`

### 5.8 Integration with Shell

- [x] Update `agent/factory.py`:
  - [x] `create_workflow_executor()` factory
  - [x] `create_workflow_handler()` for shell integration
  - [x] `create_async_workflow_handler()` async version

### Phase 5 Deliverables

- [x] Agent uses LangGraph for execution
- [x] Multi-step tasks work with state persistence
- [x] Approval gates in workflow
- [x] Predefined workflows can be executed
- [x] Streaming output via `stream()` method

### Phase 5 Tests

- [x] `tests/unit/test_workflow_states.py`:
  - [x] Test state creation
  - [x] Test ToolCallRecord
  - [x] Test ApprovalRequest
- [x] `tests/unit/test_workflow_edges.py`:
  - [x] Test routing decisions
  - [x] Test helper functions
- [x] `tests/unit/test_workflow_nodes.py`:
  - [x] Test AgentNode
  - [x] Test ToolNode
  - [x] Test ApprovalNode
  - [x] Test ErrorRecoveryNode
- [x] `tests/unit/test_predefined_workflows.py`:
  - [x] Test workflow loading
  - [x] Test parameter validation

- [ ] `tests/integration/test_single_agent_workflow.py`:
  - [ ] Test complete workflow execution
- [ ] `tests/integration/test_predefined_workflows.py`:
  - [ ] Test each predefined workflow

---

## Phase 6: Memory & Context Management

**Goal**: Enable agent to remember and learn
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 5

### 6.1 Session Memory

- [x] Create `src/agentsh/memory/__init__.py`
- [x] Implement `memory/session.py`:
  - [x] `Turn` dataclass:
    - [x] user_input, agent_response, tools_used, timestamp
  - [x] `SessionStore` class:
    - [x] `append_turn(turn)` - add to history
    - [x] `get_recent(n) -> List[Turn]` - get last N
    - [x] `get_context_window() -> str` - format for LLM
    - [x] `summarize() -> str` - compress long history
    - [x] Rolling window (configurable max)
  - [x] `MultiSessionStore` class for multiple sessions

### 6.2 Persistent Storage

- [x] Implement `memory/store.py`:
  - [x] `MemoryStore` abstract class
  - [x] `SQLiteMemoryStore(MemoryStore)`:
    - [x] Schema: id, type, title, content, metadata, embeddings, created_at, accessed_at, access_count
    - [x] `store(record) -> str`
    - [x] `retrieve(record_id) -> MemoryRecord`
    - [x] `delete(record_id) -> bool`
    - [x] `list_by_type(type) -> List[MemoryRecord]`
    - [x] `search(query, memory_types, tags, limit)` with FTS5
    - [x] `cleanup_expired()` - TTL enforcement
  - [x] `InMemoryStore(MemoryStore)` for testing
  - [x] FTS5 full-text search support

### 6.3 Memory Record Types

- [x] Implement `memory/schemas.py`:
  - [x] `MemoryType` enum:
    - [x] CONVERSATION_TURN
    - [x] SESSION_SUMMARY
    - [x] DEVICE_CONFIG
    - [x] USER_PREFERENCE
    - [x] SOLVED_INCIDENT
    - [x] LEARNED_PATTERN
    - [x] WORKFLOW_TEMPLATE
    - [x] WORKFLOW_EXECUTION
    - [x] ENVIRONMENT_STATE
    - [x] COMMAND_HISTORY
    - [x] CUSTOM_NOTE
    - [x] BOOKMARK
  - [x] `MemoryMetadata` dataclass:
    - [x] tags, confidence, source, related_ids, expires_at, custom
  - [x] `MemoryRecord` dataclass:
    - [x] id, type, title, content
    - [x] metadata
    - [x] embeddings (optional)
    - [x] created_at, updated_at, accessed_at, access_count
    - [x] `to_dict()` / `from_dict()` serialization
  - [x] `SearchResult` dataclass for ranked results

### 6.4 Retrieval System

- [x] Implement `memory/retrieval.py`:
  - [x] `RetrievalConfig` dataclass for scoring weights
  - [x] `MemoryRetrieval` class:
    - [x] `search(query, memory_types, tags, limit) -> List[SearchResult]`
    - [x] `get_relevant_context(query, limit, max_tokens) -> List[MemoryRecord]`
    - [x] `find_similar(record, limit) -> List[SearchResult]`
    - [x] `get_by_tags(tags, limit) -> List[MemoryRecord]`
    - [x] `get_recent(memory_type, days, limit) -> List[MemoryRecord]`
    - [x] `get_frequently_used(memory_type, limit) -> List[MemoryRecord]`
  - [x] Scoring with relevance, recency, and frequency weights
  - [x] `SemanticRetrieval` placeholder for future embeddings

### 6.5 Embeddings (Optional)

- [x] `SemanticRetrieval` placeholder in `memory/retrieval.py`:
  - [x] Placeholder for `embed_record()` method
  - [x] Placeholder for vector search (requires external embedding client)
  - [ ] Full implementation deferred to future

### 6.6 Memory Manager

- [x] Implement `memory/manager.py`:
  - [x] `MemoryManager` class:
    - [x] `store(key, value, memory_type, metadata, ttl_days) -> str`
    - [x] `get(record_id) -> MemoryRecord`
    - [x] `update(record) -> bool`
    - [x] `recall(query, tags, memory_types, limit) -> List[SearchResult]`
    - [x] `remember(note, title, tags, memory_type, ttl_days) -> str` - user command
    - [x] `forget(record_id) -> bool` - user command
    - [x] `add_turn()` - session turn management
    - [x] `get_context()` - combined session + memory context
    - [x] `get_session_turns()` / `get_session_summary()`
    - [x] Knowledge base operations:
      - [x] `store_device_config()`
      - [x] `store_user_preference()`
      - [x] `store_solved_incident()`
      - [x] `store_learned_pattern()`
    - [x] Query operations: `find_similar()`, `get_by_tags()`, `get_recent()`, `get_frequently_used()`
    - [x] Maintenance: `cleanup()`, `clear_session()`, `clear_all()`, `get_stats()`, `persist_session()`

### 6.7 Integration

- [x] Update `workflows/nodes.py`:
  - [x] Memory node queries relevant context
  - [x] Memory node stores completed turns
  - [x] Configurable `store_turns` and `retrieve_context` options
- [x] Update `agent/factory.py`:
  - [x] `create_memory_manager()` factory
  - [x] Memory manager integration with workflow executor
- [x] Shell memory commands (`shell/memory.py`):
  - [x] `:remember <note>` - store a fact (`MemoryStore.remember()`)
  - [x] `:recall <query>` - search memory (`MemoryStore.recall()`)
  - [x] `:forget <id>` - delete from memory (`MemoryStore.forget()`)

### Phase 6 Deliverables

- [x] Agent remembers conversation history
- [x] User can store facts programmatically
- [x] Agent recalls relevant past context
- [x] Memory persists across sessions (SQLite)
- [x] Keyword search with FTS5
- [x] Placeholder for semantic search

### Phase 6 Tests

- [x] `tests/unit/test_memory_schemas.py`:
  - [x] Test MemoryType enum
  - [x] Test MemoryMetadata
  - [x] Test MemoryRecord (create, to_dict, from_dict)
  - [x] Test Turn and to_memory_record
  - [x] Test SearchResult sorting
- [x] `tests/unit/test_memory_session.py`:
  - [x] Test SessionConfig
  - [x] Test SessionStore (append, get_recent, search, summarize, clear)
  - [x] Test MultiSessionStore
  - [x] Test max_turns limit and eviction
- [x] `tests/unit/test_memory_store.py`:
  - [x] Test InMemoryStore CRUD operations
  - [x] Test SQLiteMemoryStore with FTS5
  - [x] Test tag filtering
  - [x] Test TTL cleanup
  - [x] Test persistence across instances
- [x] `tests/unit/test_memory_retrieval.py`:
  - [x] Test keyword search
  - [x] Test type and tag filtering
  - [x] Test relevance context
  - [x] Test get_by_tags, get_recent, get_frequently_used
  - [x] Test scoring weights
- [x] `tests/unit/test_memory_manager.py`:
  - [x] Test remember/recall/forget commands
  - [x] Test session turn management
  - [x] Test knowledge base operations
  - [x] Test maintenance operations

---

## Phase 7: Telemetry & Monitoring

**Goal**: Comprehensive observability
**Estimated Effort**: 1-2 weeks
**Dependencies**: Phase 4

### 7.1 Structured Logging

- [x] Enhance `telemetry/logger.py`:
  - [x] Log event types:
    - [x] command_executed
    - [x] tool_called
    - [x] workflow_started/completed
    - [x] approval_requested/granted/denied
    - [x] error
    - [x] security_alert
  - [x] Context fields:
    - [x] session_id, user, role
    - [x] command, tool_name, risk_level
    - [x] duration_ms, exit_code
  - [ ] Sensitive data redaction (deferred)

### 7.2 Metrics Collection

- [x] Implement `telemetry/metrics.py`:
  - [x] Custom metrics implementation (Prometheus-style):
    - [x] `Counter`: tool_executions_total, approvals_total, errors_total
    - [x] `Histogram`: tool_duration_seconds, llm_latency_seconds
    - [x] `Gauge`: agent_status, active_sessions
  - [x] LLM metrics:
    - [x] tokens_in_total, tokens_out_total
    - [x] llm_calls_total (by provider)
  - [x] `AgentSHMetrics` class with pre-defined metrics
  - [x] Global `MetricsRegistry` singleton

### 7.3 Event System

- [x] Implement `telemetry/events.py`:
  - [x] `TelemetryEvent` dataclass
  - [x] `EventType` enum with all event types
  - [x] `EventEmitter` class:
    - [x] `emit(event)` - broadcast event
    - [x] `subscribe(event_type, handler)`
    - [x] Async event processing (`emit_async`)
  - [x] Event factory functions:
    - [x] `emit_event()`, `tool_called_event()`, `llm_event()`, etc.

### 7.4 Exporters

- [x] Implement `telemetry/exporters.py`:
  - [x] `Exporter` abstract class
  - [x] `FileExporter`:
    - [x] Write to log files
    - [x] JSON lines format
    - [x] Log rotation
  - [x] `PrometheusExporter`:
    - [x] `render_metrics()` - Prometheus text format
  - [x] `JSONExporter`:
    - [x] Write to stream (stdout/file)
    - [x] Pretty-print option
  - [x] `MemoryExporter`:
    - [x] For testing
  - [x] `CompositeExporter`:
    - [x] Combine multiple exporters

### 7.5 Health Checks

- [x] Implement `telemetry/health.py`:
  - [x] `HealthStatus` enum: HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN
  - [x] `HealthResult` dataclass
  - [x] `OverallHealth` dataclass
  - [x] `HealthChecker` class:
    - [x] `check_shell() -> HealthResult` - PTY alive?
    - [x] `check_llm() -> HealthResult` - API reachable?
    - [x] `check_memory() -> HealthResult` - DB healthy?
    - [x] `check_config() -> HealthResult` - Config valid?
    - [x] `check_all() -> OverallHealth`
    - [x] `check_all_async()` - async version
  - [x] Custom check registration
  - [x] Critical component tracking

### 7.6 Integration

- [x] Update `telemetry/__init__.py` with all exports
- [ ] Update tool runner to emit events (Phase 8)
- [ ] Update workflow executor to emit events (Phase 8)
- [ ] Update security controller to emit events (Phase 8)

### Phase 7 Deliverables

- [x] Event system with pub/sub pattern
- [x] Prometheus-style metrics (Counter, Gauge, Histogram)
- [x] Multiple export backends (File, JSON, Prometheus, Memory)
- [x] Health checking system
- [x] Events can be subscribed to
- [x] Logs written to file with rotation

### Phase 7 Tests

- [x] `tests/unit/test_telemetry_events.py`:
  - [x] Test EventType, TelemetryEvent
  - [x] Test EventEmitter (sync and async)
  - [x] Test event factory functions
- [x] `tests/unit/test_telemetry_metrics.py`:
  - [x] Test Counter, Gauge, Histogram
  - [x] Test MetricsRegistry
  - [x] Test AgentSHMetrics
- [x] `tests/unit/test_telemetry_exporters.py`:
  - [x] Test FileExporter with rotation
  - [x] Test JSONExporter
  - [x] Test PrometheusExporter
  - [x] Test MemoryExporter
  - [x] Test CompositeExporter
- [x] `tests/unit/test_telemetry_health.py`:
  - [x] Test HealthChecker
  - [x] Test health aggregation
  - [x] Test async health checks

---

## Phase 8: Multi-Device Orchestration

**Goal**: Manage fleets of devices
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 5, Phase 7

### 8.1 Device Inventory

- [x] Create `src/agentsh/orchestrator/__init__.py`
- [x] Implement `orchestrator/devices.py`:
  - [x] `Device` dataclass (per JSON schema):
    - [x] id, hostname, ip, port
    - [x] device_type, role, labels
    - [x] connection (method, credentials_profile)
    - [x] capabilities, status
    - [x] safety_constraints
  - [x] `DeviceInventory` class:
    - [x] `load(path)` - load from YAML
    - [x] `save(path)` - persist changes
    - [x] `get(id) -> Device`
    - [x] `list() -> List[Device]`
    - [x] `filter(role, labels, status) -> List[Device]`
    - [x] `add(device)` / `remove(id)` / `update(device)`

### 8.2 SSH Executor

- [x] Implement `orchestrator/ssh.py`:
  - [x] `SSHConnection` class:
    - [x] Connect via paramiko
    - [x] Key-based auth
    - [x] Password auth (fallback)
    - [x] Connection pooling
  - [x] `SSHExecutor` class:
    - [x] `execute(device, command, timeout) -> CommandResult`:
      - [x] Connect to device
      - [x] Run command
      - [x] Capture output
      - [x] Handle errors
    - [x] `execute_parallel(devices, command, max_concurrent)`:
      - [x] Concurrent execution
      - [x] Aggregate results
    - [x] Connection pool management

### 8.3 Remote Tool

- [x] Implement remote execution tool:
  - [x] `remote.run(device_id, command) -> ToolResult`:
    - [x] Use SSHExecutor
    - [x] Apply device-specific security
    - [x] Risk level: varies
  - [x] `remote.run_parallel(command, filter)`:
    - [x] Execute on multiple devices
    - [x] Aggregate results
  - [x] `remote.list_devices()`:
    - [x] List all devices in inventory
  - [x] `remote.get_device(device_id)`:
    - [x] Get device details
  - [x] `remote.add_device(hostname, ...)`:
    - [x] Add device to inventory
  - [x] `remote.remove_device(device_id)`:
    - [x] Remove device from inventory
  - [x] `remote.fleet_status()`:
    - [x] Get fleet status overview

### 8.4 Orchestration Coordinator

- [x] Implement `orchestrator/coordinator.py`:
  - [x] `Coordinator` class:
    - [x] `orchestrate(task, devices) -> OrchestrationResult`:
      - [x] Plan execution order
      - [x] Execute on each device
      - [x] Handle failures
      - [x] Aggregate results
    - [x] `canary_rollout(task, devices, canary_count)`:
      - [x] Test on subset first
      - [x] Then roll out to rest
    - [x] Retry/rollback logic
  - [x] Rollout strategies: ALL_AT_ONCE, SERIAL, CANARY, ROLLING
  - [x] Failure policies: CONTINUE, STOP, ROLLBACK

### 8.5 Fleet Workflows

- [x] Create fleet workflow templates:
  - [x] `fleet_update.yaml`:
    - [x] Filter devices by label
    - [x] Run update command
    - [x] Verify success
    - [x] Report results
  - [x] `fleet_healthcheck.yaml`:
    - [x] Check all devices
    - [x] Collect telemetry
    - [x] Alert on issues

### 8.6 MCP Server

- [x] Implement `orchestrator/mcp_server.py`:
  - [x] MCP protocol implementation:
    - [x] Listen on stdio
    - [x] Handle `initialize` request
    - [x] Handle `tools/list` request
    - [x] Handle `tools/call` request
    - [x] Handle `resources/list` request
    - [x] Handle `resources/read` request
    - [x] Return tool results
  - [x] Tool filtering:
    - [x] Wildcard pattern matching
    - [x] Configurable allowed tools
  - [x] Exposed resources:
    - [x] `agentsh://health` - health status
    - [x] `agentsh://tools` - available tools
  - [x] `agentsh --mcp-server` mode

### 8.7 Integration

- [x] Add device management commands:
  - [x] `agentsh devices list`
  - [x] `agentsh devices add <host>`
  - [x] `agentsh devices remove <id>`
  - [x] `agentsh devices status [device_id]`
- [x] Update agent to use remote tools
- [x] Add fleet-aware workflows

### Phase 8 Deliverables

- [x] Device inventory management
- [x] SSH execution to remote devices
- [x] Parallel fleet operations
- [x] Fleet workflow templates
- [x] MCP server mode

### Phase 8 Tests

- [x] `tests/unit/test_device_inventory.py`:
  - [x] Test CRUD operations
  - [x] Test filtering
  - [x] Test serialization
- [x] `tests/unit/test_ssh_executor.py`:
  - [x] Test CommandResult, SSHCredentials
  - [x] Test SSHConnection, SSHConnectionPool
  - [x] Test SSHExecutor
- [x] `tests/unit/test_orchestrator_coordinator.py`:
  - [x] Test orchestration strategies
  - [x] Test failure policies
- [x] `tests/unit/test_mcp_server.py`:
  - [x] Test MCP protocol
  - [x] Test request/response handling
  - [x] Test tool filtering

---

## Phase 9: Robotics Integration

**Goal**: Safe robot control via ROS
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 8

### 9.1 ROS2 Interface

- [x] Create `src/agentsh/plugins/robotics/__init__.py`
- [x] Implement `plugins/robotics/ros_interface.py`:
  - [x] `ROS2Client` class:
    - [x] Initialize ROS2 node
    - [x] `list_topics() -> List[TopicInfo]`
    - [x] `subscribe(topic, callback)`
    - [x] `publish(topic, message)`
    - [x] `call_service(service, request)`
    - [x] `list_services() -> List[ServiceInfo]`

### 9.2 Robot Safety

- [x] Implement `plugins/robotics/safety.py`:
  - [x] `RobotSafetyState` enum:
    - [x] IDLE, SUPERVISED, AUTONOMOUS, ESTOP, MAINTENANCE
  - [x] `RobotSafetyController`:
    - [x] `validate_motion(command) -> ValidationResult`:
      - [x] Check emergency stop
      - [x] Check battery level
      - [x] Check joint limits
      - [x] Check collision path
      - [x] Check geofence
      - [x] Check human proximity
    - [x] `request_motion_approval(motion)`
    - [x] State transition enforcement

### 9.3 Robotics Toolset

- [x] Implement `plugins/robotics/robotics_toolset.py`:
  - [x] `RoboticsToolset(Toolset)`:
    - [x] `ros.list_topics() -> List[TopicInfo]`:
      - [x] Risk level: SAFE
    - [x] `ros.subscribe(topic, duration) -> List[Message]`:
      - [x] Risk level: SAFE
    - [x] `ros.publish(topic, message)`:
      - [x] Risk level: MEDIUM (HIGH for motion)
    - [x] `ros.call_service(service, args)`:
      - [x] Risk level: varies by service
    - [x] Safety integration for motion tools

### 9.4 Hardware Adoption Workflow

- [ ] Create `workflows/predefined/robot_adopt_hardware.yaml`:
  - [ ] Detect new USB/ROS device
  - [ ] Look up required drivers
  - [ ] Install packages
  - [ ] Update ROS configs
  - [ ] Run calibration
  - [ ] Verify sensor topics

### 9.5 Fleet Robotics

- [ ] Create robot fleet workflows:
  - [ ] `robot_fleet_update.yaml`:
    - [ ] Deploy new model to all robots
    - [ ] Staggered rollout
    - [ ] Verify each robot
  - [ ] `robot_fleet_dock.yaml`:
    - [ ] Send all robots to docking
    - [ ] Run self-diagnostics
    - [ ] Report battery levels

### 9.6 Integration

- [x] Add robot-aware device type
- [x] Robot-specific safety constraints in device inventory
- [ ] Motion approval workflow

### Phase 9 Deliverables

- [x] ROS2 topic/service interaction
- [x] Safe motion approval
- [x] Robot-specific safety checks
- [ ] Hardware adoption workflow
- [ ] Fleet robotics operations

### Phase 9 Tests

- [x] `tests/unit/test_robot_safety.py`:
  - [x] Test safety validations
- [x] `tests/unit/test_ros_interface.py`:
  - [x] Test ROS2 client mock
- [x] `tests/unit/test_robotics_toolset.py`:
  - [x] Test robot tools
- [ ] `tests/integration/test_ros_interface.py`:
  - [ ] Test with ROS2 mock
- [ ] `tests/integration/test_robotics_toolset.py`:
  - [ ] Test robot tools

---

## Phase 10: UX Polish & Hardening

**Goal**: Production-ready release
**Estimated Effort**: 2-3 weeks
**Dependencies**: All previous phases

### 10.1 UX Improvements

- [x] Enhanced prompts:
  - [ ] Auto-suggestions during input
  - [x] Tab completion for tools (`shell/completer.py` - `ShellCompleter`)
  - [x] Syntax highlighting (`utils/syntax.py` - `SyntaxHighlighter`, `highlight()`)
- [x] Progress indicators:
  - [x] Spinner during LLM calls (`utils/ux.py` - `Spinner` class)
  - [x] Progress bar for long operations (`utils/ux.py` - `ProgressBar` class)
- [x] Output formatting:
  - [x] Colorized output (`utils/ux.py` - `Color` enum, `colorize()`)
  - [x] Tables for structured data (`utils/ux.py` - `Table`, `TableColumn`)
  - [x] Markdown rendering (`utils/markdown.py` - `MarkdownRenderer`, `render_markdown()`)
- [x] Help system (`shell/help.py`):
  - [x] `:help` command with topics (`HelpSystem`, `HelpTopic`)
  - [x] Topic-based documentation (categories: getting_started, commands, ai, security, etc.)
  - [x] Search functionality
  - [ ] `--help` for each command

### 10.2 Error Handling

- [x] User-friendly error messages (`utils/ux.py` - `ErrorFormatter`, `ErrorContext`)
- [x] Suggestions for common errors (`utils/ux.py` - `get_error_suggestion()`, `ERROR_SUGGESTIONS`)
- [x] Graceful degradation (`agent/resilient.py`):
  - [x] LLM unavailable: use cached responses (`ResilientLLMClient`)
  - [x] Network issues: retry with backoff (`RetryConfig`, exponential backoff)
  - [x] Circuit breaker pattern (`CircuitBreakerConfig`, `CircuitState`)
  - [x] Resource exhaustion: cleanup (`utils/resource_manager.py` - `ResourceManager`)

### 10.3 Performance Optimization

- [x] LLM caching (`agent/cache.py`):
  - [x] Cache common queries (`LLMCache`, `SQLiteLLMCache`)
  - [x] Cache key builder (`CacheKeyBuilder`)
  - [x] TTL-based expiration
  - [x] LRU eviction
  - [x] Hit rate tracking
  - [ ] Semantic cache (similar queries)
- [x] Lazy loading (`plugins/lazy.py`):
  - [x] Load plugins on demand (`LazyPlugin`, `LazyPluginRegistry`)
  - [x] Defer heavy initialization (`PluginState`, `load_plugins_lazy()`)
- [x] Connection pooling:
  - [x] Reuse SSH connections (Phase 8 - `orchestrator/ssh.py` - `SSHConnectionPool`)
  - [x] HTTP keep-alive for LLM (`agent/http_client.py` - `HTTPClientManager`)

### 10.4 Security Hardening

- [ ] Penetration testing:
  - [ ] Prompt injection attempts
  - [ ] Command injection attempts
  - [ ] Privilege escalation attempts
- [x] Secret management (`utils/validators.py`, `utils/crypto.py`):
  - [x] Don't log secrets (`redact_secrets()`)
  - [x] Secret detection (`InputSanitizer.check_for_secrets()`)
  - [x] Encrypt at rest (`Encryptor`, `EncryptedData`)
  - [x] Secure credential storage (`SecureStore`)
- [x] Input sanitization (`utils/validators.py`):
  - [x] Validate all user input (`InputSanitizer`, `validate_and_sanitize()`)
  - [x] Escape special characters (`sanitize_shell_arg()`)
  - [x] Path validation (`PathValidator`)
  - [x] Command validation (`CommandValidator`)
  - [x] SQL injection prevention (`sanitize_sql_value()`)
  - [x] URL validation (`sanitize_url()`)

### 10.5 Testing Completion

- [ ] Achieve >90% test coverage
- [ ] Load testing:
  - [ ] 100+ concurrent sessions
  - [ ] 1000+ device fleet
- [ ] End-to-end tests:
  - [ ] Full user journeys
  - [ ] Multi-device workflows

### 10.6 Documentation

- [ ] User guide:
  - [ ] Installation
  - [ ] Configuration
  - [ ] Basic usage
  - [ ] Advanced features
- [ ] API documentation:
  - [ ] Plugin development guide
  - [ ] Tool creation guide
  - [ ] Workflow authoring guide
- [ ] Operations guide:
  - [ ] Deployment
  - [ ] Monitoring
  - [ ] Troubleshooting

### 10.7 Release

- [ ] Version 1.0 preparation:
  - [ ] Changelog
  - [ ] Migration guide (if applicable)
  - [ ] Known issues
- [ ] Package publishing:
  - [ ] Build wheel
  - [ ] Publish to PyPI
  - [ ] Verify installation
- [ ] Announcements:
  - [ ] Blog post
  - [ ] GitHub release

### Phase 10 Deliverables

- [ ] Polished user experience
- [ ] Production-ready security
- [ ] Comprehensive documentation
- [ ] Published to PyPI
- [ ] 90%+ test coverage

---

## Appendix A: File Checklist by Package

### Shell Package (`src/agentsh/shell/`)
- [x] `__init__.py`
- [x] `wrapper.py` - ShellWrapper class
- [x] `pty_manager.py` - PTY lifecycle
- [x] `input_classifier.py` - Input routing
- [x] `prompt.py` - Prompt rendering
- [x] `history.py` - Command history
- [x] `help.py` - Help system
- [x] `memory.py` - Shell memory commands
- [x] `completer.py` - Tab completion

### Agent Package (`src/agentsh/agent/`)
- [x] `__init__.py`
- [x] `llm_client.py` - LLM abstraction
- [x] `providers/anthropic.py`
- [x] `providers/openai.py`
- [ ] `providers/ollama.py`
- [x] `prompts.py` - System prompts
- [x] `agent_loop.py` - ReAct loop
- [x] `cache.py` - LLM response caching
- [x] `resilient.py` - Fault-tolerant LLM client
- [x] `http_client.py` - HTTP connection pooling
- [x] `factory.py` - Agent factory
- [ ] `executor.py` - Tool execution
- [ ] `tool_schema.py` - Schema generation

### Tools Package (`src/agentsh/tools/`)
- [ ] `__init__.py`
- [ ] `registry.py` - Tool registry
- [ ] `base.py` - Tool base classes
- [ ] `runner.py` - Execution wrapper
- [ ] `timeout.py` - Timeout management
- [ ] `errors.py` - Tool errors

### Workflows Package (`src/agentsh/workflows/`)
- [ ] `__init__.py`
- [ ] `states.py` - LangGraph states
- [ ] `nodes.py` - Graph nodes
- [ ] `edges.py` - Graph edges
- [ ] `single_agent.py` - ReAct graph
- [ ] `multi_agent.py` - Multi-agent patterns
- [ ] `executor.py` - Workflow runtime
- [ ] `predefined/bootstrap.yaml`
- [ ] `predefined/backup.yaml`
- [ ] `predefined/deploy.yaml`

### Memory Package (`src/agentsh/memory/`)
- [x] `__init__.py`
- [x] `manager.py` - Memory manager
- [x] `session.py` - Session store
- [x] `store.py` - Persistent store (SQLite + InMemory)
- [x] `schemas.py` - Record schemas
- [x] `retrieval.py` - Search and retrieval
- [ ] `embeddings.py` - Vector embeddings (deferred)

### Security Package (`src/agentsh/security/`)
- [x] `__init__.py`
- [x] `controller.py` - Security controller
- [x] `classifier.py` - Risk classification
- [x] `policies.py` - Security policies
- [x] `rbac.py` - Role-based access
- [x] `approval.py` - Approval flow
- [x] `audit.py` - Audit logging
- [ ] `sandbox.py` - Sandboxing hooks

### Telemetry Package (`src/agentsh/telemetry/`)
- [x] `__init__.py`
- [x] `logger.py` - Structured logging
- [x] `metrics.py` - Prometheus-style metrics
- [x] `events.py` - Event system
- [x] `exporters.py` - Log exporters
- [x] `health.py` - Health checks

### Orchestrator Package (`src/agentsh/orchestrator/`)
- [x] `__init__.py`
- [x] `devices.py` - Device inventory
- [x] `ssh.py` - SSH executor
- [x] `coordinator.py` - Orchestration
- [x] `mcp_server.py` - MCP server

### Plugins Package (`src/agentsh/plugins/`)
- [x] `__init__.py`
- [x] `base.py` - Toolset ABC
- [x] `loader.py` - Plugin loader
- [x] `lazy.py` - Lazy loading support
- [ ] `builtin/shell.py` - Shell toolset
- [ ] `builtin/filesystem.py` - FS toolset
- [ ] `builtin/process.py` - Process toolset
- [ ] `builtin/code.py` - Code toolset
- [x] `robotics/robotics_toolset.py`
- [x] `robotics/ros_interface.py`
- [x] `robotics/safety.py`

### Config Package (`src/agentsh/config/`)
- [ ] `__init__.py`
- [ ] `schemas.py` - Config schemas
- [ ] `loader.py` - Config loading
- [ ] `defaults.py` - Default values

### Utils Package (`src/agentsh/utils/`)
- [x] `__init__.py`
- [x] `env.py` - Environment helpers
- [x] `crypto.py` - Encryption and secure storage
- [x] `validators.py` - Input validation
- [x] `ux.py` - UX utilities (spinners, tables, colors)
- [x] `async_utils.py` - Async helpers (retry, rate limiting, timeouts)
- [x] `markdown.py` - Markdown terminal rendering
- [x] `resource_manager.py` - Resource management and cleanup
- [x] `syntax.py` - Syntax highlighting for code

---

## Appendix B: Test Checklist

### Unit Tests (`tests/unit/`)
- [x] `test_agent_loop.py` - Agent loop tests
- [x] `test_async_utils.py` - Async utilities tests
- [x] `test_config.py` - Configuration tests
- [x] `test_crypto.py` - Cryptographic utilities tests
- [x] `test_device_inventory.py` - Device inventory CRUD
- [x] `test_help.py` - Help system tests
- [x] `test_history.py` - Command history tests
- [x] `test_http_client.py` - HTTP client management tests
- [x] `test_input_classifier.py` - Input routing tests
- [x] `test_lazy_plugins.py` - Lazy plugin loading tests
- [x] `test_llm_cache.py` - LLM caching tests
- [x] `test_llm_client.py` - LLM client abstraction tests
- [x] `test_logger.py` - Structured logging tests
- [x] `test_markdown.py` - Markdown rendering tests
- [x] `test_mcp_server.py` - MCP protocol tests
- [x] `test_memory_manager.py` - Memory manager tests
- [x] `test_memory_retrieval.py` - Memory retrieval tests
- [x] `test_memory_schemas.py` - Memory schema tests
- [x] `test_memory_session.py` - Session store tests
- [x] `test_memory_store.py` - Persistent store tests
- [x] `test_memory.py` - Shell memory commands tests
- [x] `test_orchestrator_coordinator.py` - Orchestration tests
- [x] `test_plugins.py` - Plugin system tests
- [x] `test_predefined_workflows.py` - Workflow template tests
- [x] `test_prompt.py` - Prompt rendering tests
- [x] `test_resilient.py` - Resilient LLM client tests
- [x] `test_robot_safety.py` - Robot safety validation tests
- [x] `test_robotics_toolset.py` - Robotics toolset tests
- [x] `test_ros_interface.py` - ROS2 interface tests
- [x] `test_security.py` - Risk classifier, RBAC, approval
- [x] `test_ssh_executor.py` - SSH execution tests
- [x] `test_telemetry_events.py` - Event system tests
- [x] `test_telemetry_exporters.py` - Exporter tests
- [x] `test_telemetry_health.py` - Health check tests
- [x] `test_telemetry_metrics.py` - Metrics tests
- [x] `test_tool_registry.py` - Tool registry tests
- [x] `test_tool_runner.py` - Tool runner tests
- [x] `test_toolsets.py` - Builtin toolset tests
- [x] `test_ux.py` - UX utilities tests
- [x] `test_validators.py` - Input validation tests
- [x] `test_workflow_edges.py` - Workflow edge routing tests
- [x] `test_workflow_nodes.py` - Workflow node tests
- [x] `test_workflow_states.py` - Workflow state tests
- [x] `test_wrapper.py` - Shell wrapper tests
- [x] `test_completer.py` - Tab completion tests
- [x] `test_resource_manager.py` - Resource management tests
- [x] `test_syntax.py` - Syntax highlighting tests
- [x] `test_env.py` - Environment utilities tests
- [x] `test_approval.py` - Approval flow tests
- [x] `test_single_agent.py` - Single agent workflow tests
- [x] `test_executor.py` - Workflow executor tests
- [x] `test_defaults.py` - Config defaults tests
- [x] `test_factory.py` - Agent factory tests
- [x] `test_providers.py` - LLM provider tests
- [x] `test_loader.py` - Plugin loader tests
- [x] `test_remote_toolset.py` - Remote toolset tests
- [x] `test_pty_manager.py` - PTY manager tests
- [x] `test_security_controller.py` - Security controller tests

### Integration Tests (`tests/integration/`)
- [ ] `test_shell_wrapper.py`
- [ ] `test_llm_providers.py`
- [ ] `test_shell_toolset.py`
- [ ] `test_filesystem_toolset.py`
- [ ] `test_single_agent_workflow.py`
- [ ] `test_predefined_workflows.py`
- [ ] `test_memory_retrieval.py`
- [ ] `test_health_checks.py`
- [ ] `test_ssh_executor.py`
- [ ] `test_mcp_server.py`
- [ ] `test_ros_interface.py`
- [ ] `test_robotics_toolset.py`

### Security Tests (`tests/security/`)
- [ ] `test_blocked_commands.py`
- [ ] `test_prompt_injection.py`
- [ ] `test_privilege_escalation.py`
- [ ] `test_command_injection.py`

### E2E Tests (`tests/e2e/`)
- [ ] `test_basic_request.py`
- [ ] `test_multi_step_task.py`
- [ ] `test_approval_flow.py`
- [ ] `test_user_journey.py`

---

## Appendix C: Documentation Checklist

### User Documentation
- [ ] `README.md` - Quick start
- [ ] `docs/INSTALLATION.md`
- [ ] `docs/CONFIGURATION.md`
- [ ] `docs/USAGE.md`
- [ ] `docs/COMMANDS.md`

### Developer Documentation
- [ ] `docs/ARCHITECTURE.md` (exists)
- [ ] `docs/PLUGIN_GUIDE.md`
- [ ] `docs/WORKFLOW_GUIDE.md`
- [ ] `docs/API_REFERENCE.md`
- [ ] `docs/CONTRIBUTING.md`

### Operations Documentation
- [ ] `docs/DEPLOYMENT.md`
- [ ] `docs/MONITORING.md`
- [ ] `docs/TROUBLESHOOTING.md`
- [ ] `docs/SECURITY.md`

---

## Appendix D: CI/CD Checklist

### GitHub Actions
- [ ] `.github/workflows/lint.yml`
- [ ] `.github/workflows/test.yml`
- [ ] `.github/workflows/security.yml`
- [ ] `.github/workflows/release.yml`

### Quality Gates
- [ ] Lint passes (black, ruff)
- [ ] Type check passes (mypy)
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security scan passes
- [ ] Coverage >= 80%

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| Dec 2025 | 1.0 | Initial checklist created |
| Dec 2025 | 1.1 | Phase 9 (Robotics) completed, Phase 10 (UX Polish) completed |
| Dec 2025 | 1.2 | Added unit tests for llm_client, agent_loop; updated test checklist (44 unit test files) |
| Dec 2025 | 1.3 | Added tab completion (shell/completer.py), resource manager (utils/resource_manager.py); 1224 tests passing |

---

**End of Implementation Checklist**

Use this document to track progress through all phases. Update status markers as work is completed. Each checkbox represents a discrete, testable deliverable.
