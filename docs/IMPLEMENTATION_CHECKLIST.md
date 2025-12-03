# AgentSH Implementation Checklist

**Purpose**: Master tracking document for AgentSH buildout
**Version**: 1.0
**Last Updated**: December 2025
**Status**: Ready for Implementation

---

## Quick Reference

| Phase | Name | Status | Priority | Dependencies |
|-------|------|--------|----------|--------------|
| 0 | Foundation & Project Setup | Not Started | Critical | None |
| 1 | Shell Wrapper MVP | Not Started | Critical | Phase 0 |
| 2 | LLM Integration & Agent Loop | Not Started | Critical | Phase 1 |
| 3 | Security Baseline | Not Started | Critical | Phase 2 |
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

- [ ] Create project directory structure:
  ```
  agentsh/
  ├── src/agentsh/
  ├── tests/
  ├── docs/
  ├── examples/
  └── .github/workflows/
  ```
- [ ] Initialize `pyproject.toml` with metadata
- [ ] Create `src/agentsh/__init__.py` with version
- [ ] Create `src/agentsh/__main__.py` entry point

### 0.2 Dependencies Setup

- [ ] Core dependencies in pyproject.toml:
  - [ ] `ptyprocess >= 0.7.0` (PTY management)
  - [ ] `prompt-toolkit >= 3.0` (line editing)
  - [ ] `pydantic >= 2.0` (validation)
  - [ ] `pyyaml >= 6.0` (config)
  - [ ] `structlog >= 24.0` (logging)
- [ ] LLM dependencies:
  - [ ] `anthropic >= 0.28.0`
  - [ ] `openai >= 1.3.0`
  - [ ] `langgraph >= 0.2.0`
  - [ ] `langchain-core >= 0.2.0`
- [ ] Optional dependencies:
  - [ ] `chromadb >= 0.4.0` (vector DB)
  - [ ] `paramiko >= 3.0` (SSH)
  - [ ] `prometheus-client >= 0.17.0` (metrics)
- [ ] Development dependencies:
  - [ ] `pytest >= 7.0`
  - [ ] `pytest-asyncio`
  - [ ] `pytest-cov`
  - [ ] `mypy`
  - [ ] `black`
  - [ ] `ruff`

### 0.3 Configuration System

- [ ] Create `src/agentsh/config/__init__.py`
- [ ] Implement `config/schemas.py`:
  - [ ] `LLMConfig` Pydantic model
  - [ ] `ShellConfig` Pydantic model
  - [ ] `SecurityConfig` Pydantic model
  - [ ] `MemoryConfig` Pydantic model
  - [ ] `TelemetryConfig` Pydantic model
  - [ ] `AgentSHConfig` root model
- [ ] Implement `config/loader.py`:
  - [ ] Load from `/etc/agentsh/config.yaml` (system)
  - [ ] Load from `~/.agentsh/config.yaml` (user)
  - [ ] Load from `.agentsh.yaml` (project)
  - [ ] Environment variable overrides (`AGENTSH_*`)
  - [ ] CLI argument overrides
- [ ] Implement `config/defaults.py`:
  - [ ] Default LLM settings
  - [ ] Default security mode
  - [ ] Default paths
- [ ] Create sample config file `examples/config.yaml`

### 0.4 Plugin Registry Foundation

- [ ] Create `src/agentsh/plugins/__init__.py`
- [ ] Implement `plugins/base.py`:
  - [ ] `Toolset` abstract base class
  - [ ] `@property name: str`
  - [ ] `@property description: str`
  - [ ] `register_tools(registry: ToolRegistry)`
  - [ ] `configure(config: dict)`
- [ ] Implement `plugins/loader.py`:
  - [ ] Entry point discovery (`agentsh.plugins`)
  - [ ] Directory scan (`~/.agentsh/plugins/`)
  - [ ] Plugin validation
  - [ ] Dependency injection

### 0.5 CLI Entry Point

- [ ] Implement `__main__.py`:
  - [ ] `agentsh` - start interactive shell
  - [ ] `agentsh --version` - show version
  - [ ] `agentsh --config <path>` - custom config
  - [ ] `agentsh config show` - debug config
  - [ ] `agentsh status` - health check
  - [ ] `agentsh --mcp-server` - MCP mode (placeholder)
- [ ] Create shell wrapper entry:
  ```python
  def main():
      # Parse args
      # Load config
      # Initialize shell
      # Run REPL
  ```

### 0.6 CI/CD Setup

- [ ] Create `.github/workflows/lint.yml`:
  - [ ] Run black format check
  - [ ] Run ruff linting
  - [ ] Run mypy type checking
- [ ] Create `.github/workflows/test.yml`:
  - [ ] Run pytest
  - [ ] Generate coverage report
  - [ ] Fail if coverage < 70%
- [ ] Create `.github/workflows/security.yml`:
  - [ ] Run bandit security scan
  - [ ] Check for known vulnerabilities
- [ ] Create `Makefile`:
  - [ ] `make install` - install dev deps
  - [ ] `make test` - run tests
  - [ ] `make lint` - run linters
  - [ ] `make format` - auto-format
  - [ ] `make build` - build package

### 0.7 Logging Foundation

- [ ] Create `src/agentsh/telemetry/__init__.py`
- [ ] Implement `telemetry/logger.py`:
  - [ ] Configure structlog
  - [ ] JSON output format
  - [ ] Context injection (session_id, user)
  - [ ] Log level configuration
  - [ ] File + stdout outputs

### Phase 0 Deliverables

- [ ] `agentsh --help` works
- [ ] `agentsh --version` shows version
- [ ] Config loads from all sources
- [ ] Logging outputs structured JSON
- [ ] CI passes lint + type checks
- [ ] Plugin loader can discover dummy plugin

---

## Phase 1: Shell Wrapper MVP

**Goal**: Wrap user's shell with AI routing capability
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 0

### 1.1 PTY Manager

- [ ] Create `src/agentsh/shell/__init__.py`
- [ ] Implement `shell/pty_manager.py`:
  - [ ] `PTYManager` class:
    - [ ] `__init__(shell_path: str)` - configure shell
    - [ ] `spawn()` - create PTY with shell process
    - [ ] `read(timeout: float)` - read from PTY
    - [ ] `write(data: bytes)` - write to PTY
    - [ ] `resize(rows: int, cols: int)` - handle window resize
    - [ ] `close()` - cleanup resources
    - [ ] `is_alive` property - check shell status
  - [ ] Handle SIGWINCH for terminal resize
  - [ ] Implement PTY I/O buffering
  - [ ] Error handling for shell crashes

### 1.2 Input Classifier

- [ ] Implement `shell/input_classifier.py`:
  - [ ] `InputType` enum:
    - [ ] `SHELL_COMMAND` - pass directly to shell
    - [ ] `AI_REQUEST` - send to AI agent
    - [ ] `SPECIAL_COMMAND` - internal commands
  - [ ] `InputClassifier` class:
    - [ ] `classify(line: str) -> InputType`
    - [ ] Force shell: `!command` prefix
    - [ ] Force AI: `ai ` or `::` prefix
    - [ ] Heuristics for natural language detection
    - [ ] Config option: default_to_ai (bool)
  - [ ] Special commands:
    - [ ] `:help` - show help
    - [ ] `:config` - show config
    - [ ] `:history` - show AI history
    - [ ] `:clear` - clear context

### 1.3 Prompt Renderer

- [ ] Implement `shell/prompt.py`:
  - [ ] `PromptRenderer` class:
    - [ ] `render_ps1() -> str` - primary prompt
    - [ ] `render_ps2() -> str` - continuation prompt
  - [ ] Components:
    - [ ] `[AS]` indicator (AgentSH active)
    - [ ] Current working directory
    - [ ] Git branch (if in repo)
    - [ ] Agent status icon (idle/busy/error)
    - [ ] User/host info
  - [ ] ANSI color support
  - [ ] Config options for customization

### 1.4 Command History

- [ ] Implement `shell/history.py`:
  - [ ] `HistoryManager` class:
    - [ ] `__init__(path: Path)` - history file location
    - [ ] `add(entry: str)` - add to history
    - [ ] `search(query: str) -> List[str]` - search history
    - [ ] `get_recent(n: int) -> List[str]` - recent entries
    - [ ] `save()` - persist to disk
    - [ ] `load()` - load from disk
  - [ ] Separate AI history from shell history
  - [ ] Deduplication of consecutive identical entries
  - [ ] Configurable max history size

### 1.5 Shell Wrapper

- [ ] Implement `shell/wrapper.py`:
  - [ ] `ShellWrapper` class:
    - [ ] `__init__(config: ShellConfig)` - initialize
    - [ ] `start()` - spawn PTY, start REPL
    - [ ] `stop()` - cleanup and exit
    - [ ] `run_repl()` - main event loop
    - [ ] `process_input(line: str)` - route input
    - [ ] `execute_shell(command: str)` - pass to PTY
    - [ ] `handle_ai_request(request: str)` - send to agent (stub)
  - [ ] Signal handling:
    - [ ] SIGINT (Ctrl+C) - interrupt current
    - [ ] SIGTSTP (Ctrl+Z) - background
    - [ ] SIGWINCH - resize
  - [ ] Graceful shutdown

### 1.6 Basic AI Command (Stub)

- [ ] Implement `shell/ai_stub.py`:
  - [ ] `ai_explain(request: str) -> str`:
    - [ ] Placeholder that echoes request
    - [ ] Returns "AI feature coming in Phase 2"
  - [ ] Wire into ShellWrapper.handle_ai_request

### Phase 1 Deliverables

- [ ] `agentsh` starts and shows custom prompt
- [ ] Regular shell commands work normally
- [ ] `!ls` forces shell execution
- [ ] `ai hello` triggers AI path (stub response)
- [ ] Command history persists
- [ ] Terminal resize works
- [ ] Graceful exit on Ctrl+D

### Phase 1 Tests

- [ ] `tests/unit/test_input_classifier.py`:
  - [ ] Test shell command detection
  - [ ] Test AI request detection
  - [ ] Test force prefixes
- [ ] `tests/unit/test_history.py`:
  - [ ] Test add/search/recent
  - [ ] Test persistence
- [ ] `tests/integration/test_shell_wrapper.py`:
  - [ ] Test PTY spawning
  - [ ] Test input/output flow

---

## Phase 2: LLM Integration & Agent Loop

**Goal**: Connect to LLM and implement basic reasoning
**Estimated Effort**: 2 weeks
**Dependencies**: Phase 1

### 2.1 LLM Client Abstraction

- [ ] Create `src/agentsh/agent/__init__.py`
- [ ] Implement `agent/llm_client.py`:
  - [ ] Data classes:
    - [ ] `Message(role, content, tool_calls)`
    - [ ] `ToolCall(id, name, arguments)`
    - [ ] `LLMResponse(content, tool_calls, stop_reason, tokens)`
    - [ ] `ToolDefinition(name, description, parameters)`
  - [ ] `LLMClient` abstract class:
    - [ ] `@abstractmethod invoke(messages, tools, temperature, max_tokens) -> LLMResponse`
    - [ ] `@abstractmethod stream(messages, tools) -> AsyncIterator[str]`
    - [ ] `@abstractmethod count_tokens(text) -> int`
    - [ ] `@property provider -> str`

### 2.2 LLM Provider Implementations

- [ ] Implement `agent/providers/anthropic.py`:
  - [ ] `AnthropicClient(LLMClient)`:
    - [ ] API key from config/env
    - [ ] Model selection
    - [ ] Convert messages to Anthropic format
    - [ ] Handle tool use responses
    - [ ] Streaming support
    - [ ] Error handling & retries
- [ ] Implement `agent/providers/openai.py`:
  - [ ] `OpenAIClient(LLMClient)`:
    - [ ] API key from config/env
    - [ ] Model selection
    - [ ] Convert messages to OpenAI format
    - [ ] Handle function calling
    - [ ] Streaming support
- [ ] Implement `agent/providers/ollama.py`:
  - [ ] `OllamaClient(LLMClient)`:
    - [ ] Local HTTP endpoint
    - [ ] Model selection
    - [ ] Fallback provider

### 2.3 System Prompts

- [ ] Implement `agent/prompts.py`:
  - [ ] `SYSTEM_PROMPT_TEMPLATE`:
    - [ ] Role definition ("You are an AI shell assistant...")
    - [ ] Safety rules (never destructive without approval)
    - [ ] Tool usage instructions
    - [ ] Output format guidance
  - [ ] Few-shot examples:
    - [ ] Example 1: NL → shell command
    - [ ] Example 2: Multi-step task
    - [ ] Example 3: Error handling
  - [ ] Context injection:
    - [ ] Current directory
    - [ ] OS/platform info
    - [ ] Available tools
    - [ ] Recent history

### 2.4 Basic Agent Loop

- [ ] Implement `agent/agent_loop.py`:
  - [ ] `AgentLoop` class:
    - [ ] `__init__(llm_client, tool_registry, config)`
    - [ ] `invoke(request: str, context: dict) -> str`:
      1. Build messages (system + user)
      2. Call LLM with tools
      3. If tool_calls: execute each
      4. Append results to messages
      5. If more steps needed: loop (max 10)
      6. Return final response
    - [ ] `_execute_tool(tool_call) -> str`
    - [ ] `_check_goal_complete(response) -> bool`
  - [ ] Implement max_steps limit
  - [ ] Handle LLM errors gracefully

### 2.5 Tool Schema Generation

- [ ] Implement `agent/tool_schema.py`:
  - [ ] `tool_to_openai_format(tool) -> dict`
  - [ ] `tool_to_anthropic_format(tool) -> dict`
  - [ ] Generate JSON schema from tool definition
  - [ ] Include examples in descriptions

### 2.6 Agent Executor

- [ ] Implement `agent/executor.py`:
  - [ ] `Executor` class:
    - [ ] `execute_tool_calls(calls, context) -> List[ToolResult]`
    - [ ] Route to tool registry
    - [ ] Collect results
    - [ ] Format for LLM consumption

### 2.7 Integration with Shell Wrapper

- [ ] Update `shell/wrapper.py`:
  - [ ] Initialize AgentLoop on startup
  - [ ] `handle_ai_request(request)`:
    - [ ] Build context (cwd, env)
    - [ ] Call agent_loop.invoke()
    - [ ] Display response
    - [ ] Handle streaming output

### Phase 2 Deliverables

- [ ] `ai "what files are here?"` returns intelligent response
- [ ] Agent proposes shell commands
- [ ] Agent explains its reasoning
- [ ] Multiple LLM providers work
- [ ] Streaming output supported

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

- [ ] Create `src/agentsh/security/__init__.py`
- [ ] Implement `security/classifier.py`:
  - [ ] `RiskLevel` enum: SAFE, MEDIUM, HIGH, CRITICAL
  - [ ] `CommandRiskAssessment` dataclass:
    - [ ] command, risk_level, reasons, dangerous_patterns
  - [ ] `RiskClassifier` class:
    - [ ] `classify(command: str) -> CommandRiskAssessment`
    - [ ] CRITICAL patterns (block always):
      - [ ] `rm -rf /`
      - [ ] `mkfs.*`
      - [ ] `dd if=.*of=/dev`
      - [ ] Fork bombs
    - [ ] HIGH patterns (require approval):
      - [ ] `rm -rf` (any path)
      - [ ] `sudo` commands
      - [ ] User management (useradd/userdel)
      - [ ] Service stops/disables
    - [ ] MEDIUM patterns (may need approval):
      - [ ] Package management
      - [ ] Network configuration
      - [ ] Pipe to shell
    - [ ] SAFE patterns:
      - [ ] Read-only commands
      - [ ] File listing
      - [ ] Text processing

### 3.2 Security Policies

- [ ] Implement `security/policies.py`:
  - [ ] `SecurityPolicy` dataclass:
    - [ ] blocked_patterns: List[str]
    - [ ] require_approval_levels: List[RiskLevel]
    - [ ] allow_autonomous: bool
    - [ ] max_command_length: int
  - [ ] Load policies from config
  - [ ] Per-device policy overrides

### 3.3 RBAC Implementation

- [ ] Implement `security/rbac.py`:
  - [ ] `Role` enum: VIEWER, OPERATOR, ADMIN
  - [ ] `RBAC` class:
    - [ ] `can_execute(role, risk_level) -> bool`
    - [ ] `can_approve(role, risk_level) -> bool`
    - [ ] Role hierarchy (admin > operator > viewer)
  - [ ] Permission matrix:
    | Role | SAFE | MEDIUM | HIGH | CRITICAL |
    |------|------|--------|------|----------|
    | VIEWER | No | No | No | No |
    | OPERATOR | Yes | Approval | No | No |
    | ADMIN | Yes | Yes | Approval | Block |

### 3.4 Human-in-the-Loop Approval

- [ ] Implement `security/approval.py`:
  - [ ] `ApprovalResult` enum: APPROVED, DENIED, EDITED, TIMEOUT
  - [ ] `ApprovalRequest` dataclass:
    - [ ] command, risk_level, reason, timeout
  - [ ] `ApprovalFlow` class:
    - [ ] `request_approval(request) -> ApprovalResult`:
      - [ ] Display proposed command
      - [ ] Show risk level and reason
      - [ ] Prompt: [y]es / [n]o / [e]dit
      - [ ] Handle timeout
      - [ ] Return result
    - [ ] Configurable timeout
    - [ ] Edit mode: let user modify command

### 3.5 Audit Logging

- [ ] Implement `security/audit.py`:
  - [ ] `AuditLogger` class:
    - [ ] `log_action(event: AuditEvent)`:
      - [ ] timestamp
      - [ ] user
      - [ ] command
      - [ ] risk_level
      - [ ] action (executed/blocked/approved/denied)
      - [ ] approver (if applicable)
    - [ ] Write to dedicated audit log
    - [ ] Append-only file
    - [ ] Optional: send to external system

### 3.6 Security Controller

- [ ] Implement `security/controller.py`:
  - [ ] `ValidationResult` enum: ALLOW, NEED_APPROVAL, BLOCKED
  - [ ] `SecurityController` class:
    - [ ] `check(command, context) -> ValidationResult`:
      1. Classify risk
      2. Check RBAC
      3. Apply policies
      4. Return decision
    - [ ] `validate_and_execute(command, context)`:
      1. Check command
      2. If NEED_APPROVAL: request
      3. If approved/allowed: execute
      4. Log everything
    - [ ] Wire into agent executor

### 3.7 Integration

- [ ] Update `agent/executor.py`:
  - [ ] Call SecurityController.check() before tool execution
  - [ ] Handle approval flow
  - [ ] Respect blocked commands
- [ ] Update `agent/agent_loop.py`:
  - [ ] Pass context with user/role info

### Phase 3 Deliverables

- [ ] Dangerous commands are blocked
- [ ] High-risk commands require approval
- [ ] User can approve/deny/edit commands
- [ ] All actions are audit logged
- [ ] RBAC restricts capabilities

### Phase 3 Tests

- [ ] `tests/unit/test_risk_classifier.py`:
  - [ ] Test pattern matching
  - [ ] Test all risk levels
- [ ] `tests/unit/test_rbac.py`:
  - [ ] Test role permissions
  - [ ] Test hierarchy
- [ ] `tests/unit/test_approval.py`:
  - [ ] Test approval flow
  - [ ] Test timeout handling
- [ ] `tests/security/test_blocked_commands.py`:
  - [ ] Test CRITICAL commands blocked
  - [ ] Test prompt injection resistance

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
- [ ] `__init__.py`
- [ ] `controller.py` - Security controller
- [ ] `classifier.py` - Risk classification
- [ ] `policies.py` - Security policies
- [ ] `rbac.py` - Role-based access
- [ ] `approval.py` - Approval flow
- [ ] `audit.py` - Audit logging
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
