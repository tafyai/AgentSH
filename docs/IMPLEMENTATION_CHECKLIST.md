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
| 4 | Tool Interface & Core Toolsets | Not Started | High | Phase 3 |
| 5 | LangGraph Workflows | Not Started | High | Phase 4 |
| 6 | Memory & Context | Not Started | Medium | Phase 5 |
| 7 | Telemetry & Monitoring | Not Started | Medium | Phase 4 |
| 8 | Multi-Device Orchestration | Not Started | Medium | Phase 5, 7 |
| 9 | Robotics Integration | Not Started | Low | Phase 8 |
| 10 | UX Polish & Hardening | Not Started | Low | All |

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

- [ ] `tests/unit/test_llm_client.py`:
  - [ ] Mock LLM responses
  - [ ] Test message formatting
  - [ ] Test tool call parsing
- [ ] `tests/unit/test_agent_loop.py`:
  - [ ] Test single-step execution
  - [ ] Test multi-step planning
  - [ ] Test max_steps limit
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

- [ ] Create `src/agentsh/tools/__init__.py`
- [ ] Implement `tools/registry.py`:
  - [ ] `ToolRegistry` class (singleton):
    - [ ] `register_tool(name, handler, schema, risk_level)`
    - [ ] `get_tool(name) -> Tool`
    - [ ] `list_tools() -> List[Tool]`
    - [ ] `get_tools_for_llm() -> List[dict]`
  - [ ] Validation of tool schemas
  - [ ] Prevent duplicate registrations

### 4.2 Tool Base Classes

- [ ] Implement `tools/base.py`:
  - [ ] `Tool` dataclass:
    - [ ] name, description, handler
    - [ ] parameters (JSON schema)
    - [ ] risk_level, requires_confirmation
    - [ ] timeout_seconds, max_retries
  - [ ] `ToolResult` dataclass:
    - [ ] success, output, error, duration_ms

### 4.3 Tool Runner

- [ ] Implement `tools/runner.py`:
  - [ ] `ToolRunner` class:
    - [ ] `execute(tool_name, args, context) -> ToolResult`:
      1. Get tool from registry
      2. Validate arguments
      3. Check security (via SecurityController)
      4. Execute with timeout
      5. Capture output/errors
      6. Emit telemetry
      7. Return result
    - [ ] Retry logic
    - [ ] Error wrapping

### 4.4 Timeout Management

- [ ] Implement `tools/timeout.py`:
  - [ ] `TimeoutManager` class:
    - [ ] `run_with_timeout(func, timeout) -> Any`
    - [ ] Handle async functions
    - [ ] Graceful cancellation
    - [ ] Per-tool timeout configuration

### 4.5 Shell Toolset

- [ ] Implement `plugins/builtin/shell.py`:
  - [ ] `ShellToolset(Toolset)`:
    - [ ] `shell.run(command, cwd, env) -> ToolResult`:
      - [ ] Execute command in shell
      - [ ] Capture stdout, stderr, exit_code
      - [ ] Risk level: varies by command
    - [ ] `shell.explain(command) -> str`:
      - [ ] Describe what command does
      - [ ] Risk level: SAFE

### 4.6 Filesystem Toolset

- [ ] Implement `plugins/builtin/filesystem.py`:
  - [ ] `FilesystemToolset(Toolset)`:
    - [ ] `fs.read(path, encoding) -> str`:
      - [ ] Read file contents
      - [ ] Risk level: SAFE
    - [ ] `fs.write(path, content, mode) -> bool`:
      - [ ] Write to file
      - [ ] Risk level: MEDIUM
    - [ ] `fs.list(path, recursive) -> List[str]`:
      - [ ] List directory
      - [ ] Risk level: SAFE
    - [ ] `fs.delete(path) -> bool`:
      - [ ] Delete file/directory
      - [ ] Risk level: HIGH
    - [ ] `fs.copy(src, dst) -> bool`:
      - [ ] Copy file
      - [ ] Risk level: MEDIUM
    - [ ] `fs.search(pattern, path) -> List[str]`:
      - [ ] Find files by pattern
      - [ ] Risk level: SAFE

### 4.7 Process Toolset

- [ ] Implement `plugins/builtin/process.py`:
  - [ ] `ProcessToolset(Toolset)`:
    - [ ] `process.list() -> List[ProcessInfo]`:
      - [ ] List running processes
      - [ ] Risk level: SAFE
    - [ ] `process.kill(pid) -> bool`:
      - [ ] Kill process
      - [ ] Risk level: HIGH
    - [ ] `process.info(pid) -> ProcessInfo`:
      - [ ] Get process details
      - [ ] Risk level: SAFE

### 4.8 Code Toolset

- [ ] Implement `plugins/builtin/code.py`:
  - [ ] `CodeToolset(Toolset)`:
    - [ ] `code.read(path, start_line, end_line) -> str`:
      - [ ] Read code with line numbers
      - [ ] Risk level: SAFE
    - [ ] `code.edit(path, old_text, new_text) -> bool`:
      - [ ] Make targeted edit
      - [ ] Risk level: MEDIUM
    - [ ] `code.search(pattern, path, file_pattern) -> List[Match]`:
      - [ ] Search in code
      - [ ] Risk level: SAFE

### Phase 4 Deliverables

- [ ] Agent can use shell.run to execute commands
- [ ] Agent can read/write files
- [ ] Agent can list/kill processes
- [ ] Agent can search/edit code
- [ ] All tools have proper risk levels
- [ ] Timeouts prevent hanging

### Phase 4 Tests

- [ ] `tests/unit/test_tool_registry.py`:
  - [ ] Test registration/lookup
  - [ ] Test schema validation
- [ ] `tests/unit/test_tool_runner.py`:
  - [ ] Test execution flow
  - [ ] Test timeout handling
- [ ] `tests/integration/test_shell_toolset.py`:
  - [ ] Test command execution
- [ ] `tests/integration/test_filesystem_toolset.py`:
  - [ ] Test file operations

---

## Phase 5: LangGraph Workflows

**Goal**: Enable multi-step, stateful task orchestration
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 4

### 5.1 State Definitions

- [ ] Create `src/agentsh/workflows/__init__.py`
- [ ] Implement `workflows/states.py`:
  - [ ] `AgentState` TypedDict:
    - [ ] messages: List[Message]
    - [ ] goal: str
    - [ ] plan: Optional[str]
    - [ ] step_count: int
    - [ ] max_steps: int
    - [ ] tools_used: List[ToolCallRecord]
    - [ ] approvals_pending: List[ApprovalRequest]
    - [ ] is_terminal: bool
    - [ ] final_result: Optional[str]
    - [ ] error: Optional[str]
  - [ ] `WorkflowState` for multi-device workflows

### 5.2 Graph Nodes

- [ ] Implement `workflows/nodes.py`:
  - [ ] `agent_node(state) -> state`:
    - [ ] Call LLM with current messages
    - [ ] Parse response
    - [ ] Update state with new message
  - [ ] `tool_node(state) -> state`:
    - [ ] Execute pending tool calls
    - [ ] Append results to messages
  - [ ] `approval_node(state) -> state`:
    - [ ] Check for high-risk tool calls
    - [ ] Request user approval
    - [ ] Update state based on response
  - [ ] `memory_node(state) -> state`:
    - [ ] Store turn in memory
    - [ ] Retrieve relevant context

### 5.3 Graph Edges

- [ ] Implement `workflows/edges.py`:
  - [ ] `should_continue(state) -> str`:
    - [ ] If tool_calls: route to "approval" or "tools"
    - [ ] If terminal: route to "end"
    - [ ] If max_steps exceeded: route to "end"
  - [ ] `is_approved(state) -> str`:
    - [ ] Check approval status
    - [ ] Route to "tools" or "end"
  - [ ] `has_error(state) -> str`:
    - [ ] Check for errors
    - [ ] Route to "recovery" or "continue"

### 5.4 Single-Agent ReAct Graph

- [ ] Implement `workflows/single_agent.py`:
  - [ ] `create_react_graph() -> StateGraph`:
    ```
    START -> agent -> [approval|tools|END]
    approval -> [tools|END]
    tools -> agent
    ```
  - [ ] Compile with checkpointing
  - [ ] Add streaming support

### 5.5 Multi-Agent Patterns (Optional)

- [ ] Implement `workflows/multi_agent.py`:
  - [ ] `create_supervisor_graph()`:
    - [ ] Supervisor agent assigns tasks
    - [ ] Worker agents execute
    - [ ] Results aggregated
  - [ ] `create_specialist_graph()`:
    - [ ] Route to domain experts
    - [ ] Combine outputs

### 5.6 Workflow Executor

- [ ] Implement `workflows/executor.py`:
  - [ ] `WorkflowExecutor` class:
    - [ ] `execute(goal, context) -> WorkflowResult`:
      - [ ] Initialize state
      - [ ] Run graph
      - [ ] Stream events
      - [ ] Return result
    - [ ] `execute_workflow(workflow_name, params)`:
      - [ ] Load predefined workflow
      - [ ] Execute with parameters
    - [ ] State persistence (via LangGraph checkpointing)

### 5.7 Predefined Workflows

- [ ] Create `workflows/predefined/`:
  - [ ] `bootstrap.yaml`:
    ```yaml
    name: project_bootstrap
    description: Set up a new project environment
    parameters:
      project_type: { type: string, enum: [python, node, rust] }
    nodes:
      - id: detect_project
        type: tool_call
        tool: fs.list
      - id: create_venv
        type: tool_call
        tool: shell.run
        depends_on: [detect_project]
      - id: install_deps
        type: tool_call
        tool: shell.run
        depends_on: [create_venv]
    ```
  - [ ] `backup.yaml`: Backup directory workflow
  - [ ] `deploy.yaml`: Deployment workflow template

### 5.8 Integration with Shell

- [ ] Update `shell/wrapper.py`:
  - [ ] Use WorkflowExecutor for AI requests
  - [ ] Stream intermediate steps
  - [ ] Handle workflow status commands

### Phase 5 Deliverables

- [ ] Agent uses LangGraph for execution
- [ ] Multi-step tasks work with state persistence
- [ ] Approval gates in workflow
- [ ] Predefined workflows can be executed
- [ ] Streaming output during long tasks

### Phase 5 Tests

- [ ] `tests/unit/test_workflow_nodes.py`:
  - [ ] Test each node in isolation
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

- [ ] Create `src/agentsh/memory/__init__.py`
- [ ] Implement `memory/session.py`:
  - [ ] `Turn` dataclass:
    - [ ] user_input, agent_response, tools_used, timestamp
  - [ ] `SessionStore` class:
    - [ ] `append_turn(turn)` - add to history
    - [ ] `get_recent(n) -> List[Turn]` - get last N
    - [ ] `get_context_window() -> str` - format for LLM
    - [ ] `summarize() -> str` - compress long history
    - [ ] Rolling window (configurable max)

### 6.2 Persistent Storage

- [ ] Implement `memory/store.py`:
  - [ ] `MemoryStore` abstract class
  - [ ] `SQLiteMemoryStore(MemoryStore)`:
    - [ ] Schema: id, type, key, content, metadata, embeddings, created_at, accessed_count, ttl
    - [ ] `store(key, value, metadata, ttl)`
    - [ ] `retrieve(key) -> MemoryRecord`
    - [ ] `delete(key)`
    - [ ] `list_by_type(type) -> List[MemoryRecord]`
  - [ ] TTL enforcement (auto-delete expired)
  - [ ] Retention policies per type

### 6.3 Memory Record Types

- [ ] Implement `memory/schemas.py`:
  - [ ] `MemoryType` enum:
    - [ ] DEVICE_CONFIG
    - [ ] USER_PREFERENCE
    - [ ] SOLVED_INCIDENT
    - [ ] WORKFLOW_TEMPLATE
    - [ ] ENVIRONMENT_STATE
    - [ ] CUSTOM_NOTE
  - [ ] `MemoryRecord` dataclass:
    - [ ] id, type, title, content
    - [ ] metadata (tags, confidence, source)
    - [ ] embeddings (optional)
    - [ ] created_at, accessed_count

### 6.4 Retrieval System

- [ ] Implement `memory/retrieval.py`:
  - [ ] `keyword_search(query) -> List[MemoryRecord]`:
    - [ ] Full-text search on content
    - [ ] Tag filtering
  - [ ] `semantic_search(query, min_score) -> List[MemoryRecord]`:
    - [ ] Vector similarity search
    - [ ] Requires embeddings
  - [ ] `get_relevant_context(query, limit) -> List[MemoryRecord]`:
    - [ ] Combine keyword + semantic
    - [ ] Rank by relevance & recency

### 6.5 Embeddings (Optional)

- [ ] Implement `memory/embeddings.py`:
  - [ ] `EmbeddingClient` class:
    - [ ] `embed(text) -> List[float]`
    - [ ] Support OpenAI embeddings
    - [ ] Support local models (sentence-transformers)
  - [ ] Vector storage in SQLite (JSON column)
  - [ ] Cosine similarity search

### 6.6 Memory Manager

- [ ] Implement `memory/manager.py`:
  - [ ] `MemoryManager` class:
    - [ ] `store(key, value, metadata, ttl) -> str`:
      - [ ] Generate embeddings if enabled
      - [ ] Store in persistent store
    - [ ] `recall(query, tags, limit) -> List[MemoryRecord]`:
      - [ ] Search session + persistent
      - [ ] Rank and dedupe
    - [ ] `remember(note, tags)` - user command
    - [ ] `forget(key)` - user command

### 6.7 Integration

- [ ] Update `workflows/nodes.py`:
  - [ ] Memory node queries relevant context
  - [ ] Memory node stores completed turns
- [ ] Update `agent/prompts.py`:
  - [ ] Include memory context in system prompt
- [ ] Add shell commands:
  - [ ] `:remember <note>` - store a fact
  - [ ] `:recall <query>` - search memory
  - [ ] `:forget <key>` - delete from memory

### Phase 6 Deliverables

- [ ] Agent remembers conversation history
- [ ] User can store facts with `:remember`
- [ ] Agent recalls relevant past context
- [ ] Memory persists across sessions
- [ ] Optional semantic search works

### Phase 6 Tests

- [ ] `tests/unit/test_session_memory.py`:
  - [ ] Test turn management
  - [ ] Test summarization
- [ ] `tests/unit/test_persistent_store.py`:
  - [ ] Test CRUD operations
  - [ ] Test TTL enforcement
- [ ] `tests/integration/test_memory_retrieval.py`:
  - [ ] Test keyword search
  - [ ] Test semantic search

---

## Phase 7: Telemetry & Monitoring

**Goal**: Comprehensive observability
**Estimated Effort**: 1-2 weeks
**Dependencies**: Phase 4

### 7.1 Structured Logging

- [ ] Enhance `telemetry/logger.py`:
  - [ ] Log event types:
    - [ ] command_executed
    - [ ] tool_called
    - [ ] workflow_started/completed
    - [ ] approval_requested/granted/denied
    - [ ] error
    - [ ] security_alert
  - [ ] Context fields:
    - [ ] session_id, user, role
    - [ ] command, tool_name, risk_level
    - [ ] duration_ms, exit_code
  - [ ] Sensitive data redaction

### 7.2 Metrics Collection

- [ ] Implement `telemetry/metrics.py`:
  - [ ] Using prometheus_client:
    - [ ] `Counter`: tool_executions_total, approvals_total, errors_total
    - [ ] `Histogram`: tool_duration_seconds, llm_latency_seconds
    - [ ] `Gauge`: agent_status, active_sessions
  - [ ] LLM metrics:
    - [ ] tokens_in_total, tokens_out_total
    - [ ] llm_calls_total (by provider)
  - [ ] Expose /metrics endpoint (optional)

### 7.3 Event System

- [ ] Implement `telemetry/events.py`:
  - [ ] `TelemetryEvent` dataclass (per schema)
  - [ ] `EventEmitter` class:
    - [ ] `emit(event)` - broadcast event
    - [ ] `subscribe(event_type, handler)`
    - [ ] Async event processing
  - [ ] Hook into tool runner, workflow executor

### 7.4 Exporters

- [ ] Implement `telemetry/exporters.py`:
  - [ ] `Exporter` abstract class
  - [ ] `FileExporter`:
    - [ ] Write to log files
    - [ ] JSON lines format
    - [ ] Log rotation
  - [ ] `PrometheusExporter`:
    - [ ] Start metrics server
    - [ ] Configurable port
  - [ ] `StdoutExporter`:
    - [ ] For debugging

### 7.5 Health Checks

- [ ] Implement `telemetry/health.py`:
  - [ ] `HealthChecker` class:
    - [ ] `check_shell() -> HealthResult` - PTY alive?
    - [ ] `check_llm() -> HealthResult` - API reachable?
    - [ ] `check_memory() -> HealthResult` - DB healthy?
    - [ ] `check_all() -> HealthStatus`
  - [ ] `agentsh status` command:
    - [ ] Show health of all components
    - [ ] Show recent activity stats

### 7.6 Integration

- [ ] Update tool runner to emit events
- [ ] Update workflow executor to emit events
- [ ] Update security controller to emit events
- [ ] Add status dashboard (optional CLI)

### Phase 7 Deliverables

- [ ] All actions logged with context
- [ ] Prometheus metrics available
- [ ] `agentsh status` shows health
- [ ] Logs written to file
- [ ] Events can be subscribed to

### Phase 7 Tests

- [ ] `tests/unit/test_telemetry.py`:
  - [ ] Test event emission
  - [ ] Test metrics recording
- [ ] `tests/integration/test_health_checks.py`:
  - [ ] Test all health checks

---

## Phase 8: Multi-Device Orchestration

**Goal**: Manage fleets of devices
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 5, Phase 7

### 8.1 Device Inventory

- [ ] Create `src/agentsh/orchestrator/__init__.py`
- [ ] Implement `orchestrator/devices.py`:
  - [ ] `Device` dataclass (per JSON schema):
    - [ ] id, hostname, ip, port
    - [ ] device_type, role, labels
    - [ ] connection (method, credentials_profile)
    - [ ] capabilities, status
    - [ ] safety_constraints
  - [ ] `DeviceInventory` class:
    - [ ] `load(path)` - load from YAML
    - [ ] `save(path)` - persist changes
    - [ ] `get(id) -> Device`
    - [ ] `list() -> List[Device]`
    - [ ] `filter(role, labels, status) -> List[Device]`
    - [ ] `add(device)` / `remove(id)` / `update(device)`

### 8.2 SSH Executor

- [ ] Implement `orchestrator/ssh.py`:
  - [ ] `SSHConnection` class:
    - [ ] Connect via paramiko
    - [ ] Key-based auth
    - [ ] Password auth (fallback)
    - [ ] Connection pooling
  - [ ] `SSHExecutor` class:
    - [ ] `execute(device, command, timeout) -> CommandResult`:
      - [ ] Connect to device
      - [ ] Run command
      - [ ] Capture output
      - [ ] Handle errors
    - [ ] `execute_parallel(devices, command, max_concurrent)`:
      - [ ] Concurrent execution
      - [ ] Aggregate results
    - [ ] Connection pool management

### 8.3 Remote Tool

- [ ] Implement remote execution tool:
  - [ ] `remote.run(device_id, command) -> ToolResult`:
    - [ ] Use SSHExecutor
    - [ ] Apply device-specific security
    - [ ] Risk level: varies

### 8.4 Orchestration Coordinator

- [ ] Implement `orchestrator/coordinator.py`:
  - [ ] `Coordinator` class:
    - [ ] `orchestrate(task, devices) -> AggregatedResult`:
      - [ ] Plan execution order
      - [ ] Execute on each device
      - [ ] Handle failures
      - [ ] Aggregate results
    - [ ] `canary_rollout(task, devices, canary_count)`:
      - [ ] Test on subset first
      - [ ] Then roll out to rest
    - [ ] Retry/rollback logic

### 8.5 Fleet Workflows

- [ ] Create fleet workflow templates:
  - [ ] `fleet_update.yaml`:
    - [ ] Filter devices by label
    - [ ] Run update command
    - [ ] Verify success
    - [ ] Report results
  - [ ] `fleet_healthcheck.yaml`:
    - [ ] Check all devices
    - [ ] Collect telemetry
    - [ ] Alert on issues

### 8.6 MCP Server

- [ ] Implement `orchestrator/mcp_server.py`:
  - [ ] MCP protocol implementation:
    - [ ] Listen on socket
    - [ ] Handle `call_tool` requests
    - [ ] Return tool results
  - [ ] Authentication:
    - [ ] Token-based auth
    - [ ] Optional mTLS
  - [ ] Exposed tools (subset):
    - [ ] `execute_command`
    - [ ] `list_files`
    - [ ] `get_status`
  - [ ] `agentsh --mcp-server` mode

### 8.7 Integration

- [ ] Add device management commands:
  - [ ] `agentsh devices list`
  - [ ] `agentsh devices add <host>`
  - [ ] `agentsh devices remove <id>`
- [ ] Update agent to use remote tools
- [ ] Add fleet-aware workflows

### Phase 8 Deliverables

- [ ] Device inventory management
- [ ] SSH execution to remote devices
- [ ] Parallel fleet operations
- [ ] Fleet workflow templates
- [ ] MCP server mode

### Phase 8 Tests

- [ ] `tests/unit/test_device_inventory.py`:
  - [ ] Test CRUD operations
  - [ ] Test filtering
- [ ] `tests/integration/test_ssh_executor.py`:
  - [ ] Test with mock SSH server
- [ ] `tests/integration/test_mcp_server.py`:
  - [ ] Test MCP protocol

---

## Phase 9: Robotics Integration

**Goal**: Safe robot control via ROS
**Estimated Effort**: 2-3 weeks
**Dependencies**: Phase 8

### 9.1 ROS2 Interface

- [ ] Create `src/agentsh/plugins/robotics/__init__.py`
- [ ] Implement `plugins/robotics/ros_interface.py`:
  - [ ] `ROS2Client` class:
    - [ ] Initialize ROS2 node
    - [ ] `list_topics() -> List[TopicInfo]`
    - [ ] `subscribe(topic, callback)`
    - [ ] `publish(topic, message)`
    - [ ] `call_service(service, request)`
    - [ ] `list_services() -> List[ServiceInfo]`

### 9.2 Robot Safety

- [ ] Implement `plugins/robotics/safety.py`:
  - [ ] `RobotSafetyState` enum:
    - [ ] IDLE, SUPERVISED, AUTONOMOUS, ESTOP, MAINTENANCE
  - [ ] `RobotSafetyController`:
    - [ ] `validate_motion(command) -> ValidationResult`:
      - [ ] Check emergency stop
      - [ ] Check battery level
      - [ ] Check joint limits
      - [ ] Check collision path
      - [ ] Check geofence
      - [ ] Check human proximity
    - [ ] `request_motion_approval(motion)`
    - [ ] State transition enforcement

### 9.3 Robotics Toolset

- [ ] Implement `plugins/robotics/robotics_toolset.py`:
  - [ ] `RoboticsToolset(Toolset)`:
    - [ ] `ros.list_topics() -> List[TopicInfo]`:
      - [ ] Risk level: SAFE
    - [ ] `ros.subscribe(topic, duration) -> List[Message]`:
      - [ ] Risk level: SAFE
    - [ ] `ros.publish(topic, message)`:
      - [ ] Risk level: MEDIUM (HIGH for motion)
    - [ ] `ros.call_service(service, args)`:
      - [ ] Risk level: varies by service
    - [ ] Safety integration for motion tools

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

- [ ] Add robot-aware device type
- [ ] Robot-specific safety constraints in device inventory
- [ ] Motion approval workflow

### Phase 9 Deliverables

- [ ] ROS2 topic/service interaction
- [ ] Safe motion approval
- [ ] Robot-specific safety checks
- [ ] Hardware adoption workflow
- [ ] Fleet robotics operations

### Phase 9 Tests

- [ ] `tests/unit/test_robot_safety.py`:
  - [ ] Test safety validations
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

- [ ] Enhanced prompts:
  - [ ] Auto-suggestions during input
  - [ ] Tab completion for tools
  - [ ] Syntax highlighting
- [ ] Progress indicators:
  - [ ] Spinner during LLM calls
  - [ ] Progress bar for long operations
- [ ] Output formatting:
  - [ ] Colorized output
  - [ ] Tables for structured data
  - [ ] Markdown rendering
- [ ] Help system:
  - [ ] `:help` command with topics
  - [ ] `--help` for each command

### 10.2 Error Handling

- [ ] User-friendly error messages
- [ ] Suggestions for common errors
- [ ] Graceful degradation:
  - [ ] LLM unavailable: use cached responses
  - [ ] Network issues: retry with backoff
  - [ ] Resource exhaustion: cleanup

### 10.3 Performance Optimization

- [ ] LLM caching:
  - [ ] Cache common queries
  - [ ] Semantic cache (similar queries)
- [ ] Lazy loading:
  - [ ] Load plugins on demand
  - [ ] Defer heavy initialization
- [ ] Connection pooling:
  - [ ] Reuse SSH connections
  - [ ] HTTP keep-alive for LLM

### 10.4 Security Hardening

- [ ] Penetration testing:
  - [ ] Prompt injection attempts
  - [ ] Command injection attempts
  - [ ] Privilege escalation attempts
- [ ] Secret management:
  - [ ] Don't log secrets
  - [ ] Encrypt at rest
  - [ ] Secure credential storage
- [ ] Input sanitization:
  - [ ] Validate all user input
  - [ ] Escape special characters

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
- [ ] `__init__.py`
- [ ] `wrapper.py` - ShellWrapper class
- [ ] `pty_manager.py` - PTY lifecycle
- [ ] `input_classifier.py` - Input routing
- [ ] `prompt.py` - Prompt rendering
- [ ] `history.py` - Command history

### Agent Package (`src/agentsh/agent/`)
- [ ] `__init__.py`
- [ ] `llm_client.py` - LLM abstraction
- [ ] `providers/anthropic.py`
- [ ] `providers/openai.py`
- [ ] `providers/ollama.py`
- [ ] `prompts.py` - System prompts
- [ ] `agent_loop.py` - ReAct loop
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
- [ ] `__init__.py`
- [ ] `manager.py` - Memory manager
- [ ] `session.py` - Session store
- [ ] `store.py` - Persistent store
- [ ] `schemas.py` - Record schemas
- [ ] `retrieval.py` - Search
- [ ] `embeddings.py` - Vector embeddings

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
- [ ] `__init__.py`
- [ ] `logger.py` - Structured logging
- [ ] `metrics.py` - Prometheus metrics
- [ ] `events.py` - Event system
- [ ] `exporters.py` - Log exporters
- [ ] `health.py` - Health checks

### Orchestrator Package (`src/agentsh/orchestrator/`)
- [ ] `__init__.py`
- [ ] `devices.py` - Device inventory
- [ ] `ssh.py` - SSH executor
- [ ] `coordinator.py` - Orchestration
- [ ] `mcp_server.py` - MCP server
- [ ] `mcp_tools.py` - MCP tool definitions

### Plugins Package (`src/agentsh/plugins/`)
- [ ] `__init__.py`
- [ ] `base.py` - Toolset ABC
- [ ] `loader.py` - Plugin loader
- [ ] `builtin/shell.py` - Shell toolset
- [ ] `builtin/filesystem.py` - FS toolset
- [ ] `builtin/process.py` - Process toolset
- [ ] `builtin/code.py` - Code toolset
- [ ] `robotics/robotics_toolset.py`
- [ ] `robotics/ros_interface.py`
- [ ] `robotics/safety.py`

### Config Package (`src/agentsh/config/`)
- [ ] `__init__.py`
- [ ] `schemas.py` - Config schemas
- [ ] `loader.py` - Config loading
- [ ] `defaults.py` - Default values

### Utils Package (`src/agentsh/utils/`)
- [ ] `__init__.py`
- [ ] `env.py` - Environment helpers
- [ ] `crypto.py` - Encryption
- [ ] `validators.py` - Input validation
- [ ] `async_utils.py` - Async helpers

---

## Appendix B: Test Checklist

### Unit Tests (`tests/unit/`)
- [ ] `test_input_classifier.py`
- [ ] `test_history.py`
- [ ] `test_risk_classifier.py`
- [ ] `test_rbac.py`
- [ ] `test_approval.py`
- [ ] `test_llm_client.py`
- [ ] `test_agent_loop.py`
- [ ] `test_tool_registry.py`
- [ ] `test_tool_runner.py`
- [ ] `test_workflow_nodes.py`
- [ ] `test_session_memory.py`
- [ ] `test_persistent_store.py`
- [ ] `test_telemetry.py`
- [ ] `test_device_inventory.py`
- [ ] `test_robot_safety.py`

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

---

**End of Implementation Checklist**

Use this document to track progress through all phases. Update status markers as work is completed. Each checkbox represents a discrete, testable deliverable.
