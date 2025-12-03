# AgentSH: Developer Implementation Checklist

**Purpose**: Detailed task breakdown for implementing AgentSH based on Architectural Specification.
**Last Updated**: December 2025

---

## Package Implementation Checklist

### Phase 0: Foundation & Project Setup

- [ ] **Repository Structure**
  - [ ] Create `src/agentsh/` with `__init__.py` and `__main__.py`
  - [ ] Create `tests/`, `examples/`, `docs/` directories
  - [ ] Set up `pyproject.toml` with dependencies:
    - [ ] LangChain & LangGraph (workflow orchestration)
    - [ ] `ptyprocess` (PTY management)
    - [ ] `pydantic` (validation & schemas)
    - [ ] `pyyaml` (config files)
    - [ ] `openai` or `anthropic` (LLM backends)
    - [ ] `sqlalchemy` (memory persistence)
    - [ ] `prometheus_client` (metrics)
    - [ ] `structlog` (structured logging)

- [ ] **Configuration System**
  - [ ] Implement `config/parser.py` - load YAML/JSON configs
  - [ ] Implement `config/resolver.py` - hierarchy: `/etc/agentsh.conf` → `~/.agentsh/config.yaml` → env vars → CLI args
  - [ ] Create `config/schemas.py` - Pydantic models for validation
  - [ ] Create default config template in `config/defaults.py`

- [ ] **Plugin Registry**
  - [ ] Implement `plugins/base.py` - `Toolset` abstract base class with:
    - [ ] `name: str`
    - [ ] `register_tools(registry: ToolRegistry)`
    - [ ] `configure(config: dict)`
  - [ ] Implement `plugins/loader.py` - dynamic plugin loading via entry points + directory scan
  - [ ] Create plugin discovery mechanism (iterate `~/.agentsh/plugins/`)

- [ ] **CLI Entrypoint**
  - [ ] Implement `__main__.py` with argparse:
    - [ ] `agentsh` (start interactive shell)
    - [ ] `agentsh --config <path>` (custom config)
    - [ ] `agentsh --mcp-server` (run as MCP server)
    - [ ] `agentsh status` (health check)
    - [ ] `agentsh config show` (debug config)

---

### Package 1: shell/

**Purpose**: User I/O & shell wrapper

- [ ] **shell/wrapper.py - Main Shell Wrapper Class**
  - [ ] `ShellWrapper` class:
    - [ ] `__init__(config)` - initialize PTY and configuration
    - [ ] `start()` - launch underlying shell in PTY
    - [ ] `stop()` - cleanup and exit
    - [ ] `read_line()` - get user input
    - [ ] `write_output(text)` - send to PTY
    - [ ] `run_repl()` - main event loop

- [ ] **shell/pty_manager.py - PTY Lifecycle**
  - [ ] `PTYManager` class:
    - [ ] Spawn shell process in PTY (`ptyprocess`)
    - [ ] Forward stdin/stdout/stderr
    - [ ] Handle window size changes
    - [ ] Graceful shutdown

- [ ] **shell/input_classifier.py - Route Input**
  - [ ] `InputClassifier` class:
    - [ ] `classify(line: str) → InputType` (SHELL_CMD, AI_REQUEST, SPECIAL_CMD)
    - [ ] Heuristics:
      - [ ] Starts with `!` → SHELL_CMD (force shell)
      - [ ] Starts with `ai ` or `::` → AI_REQUEST
      - [ ] Is valid shell syntax? → SHELL_CMD
      - [ ] Otherwise → AI_REQUEST
    - [ ] Config option to default to AI for unrecognized input

- [ ] **shell/prompt_renderer.py - Custom Prompt**
  - [ ] `PromptRenderer` class:
    - [ ] Build PS1 with:
      - [ ] `[AS]` indicator (AgentSH active)
      - [ ] Current directory
      - [ ] Git branch (if applicable)
      - [ ] Agent status (busy/idle/error)
    - [ ] Build PS2 for multiline input
    - [ ] Color coding (via ANSI codes)

- [ ] **shell/history.py - Command History**
  - [ ] `HistoryManager` class:
    - [ ] Store commands in `~/.agentsh/history`
    - [ ] Backward/forward search (Ctrl+R)
    - [ ] Deduplicate consecutive identical commands
    - [ ] Integration with shell readline

---

### Package 2: agent/

**Purpose**: AI core & planning loop

- [ ] **agent/llm_client.py - LLM Abstraction**
  - [ ] `LLMResult` dataclass:
    - [ ] `content: str` (text response)
    - [ ] `tool_calls: List[ToolCall]` (requested actions)
    - [ ] `stop_reason: str` ("tool_use" or "end_turn")
  - [ ] `LLMClient` abstract class:
    - [ ] `invoke(messages, tools=None, **kwargs) → LLMResult`
  - [ ] Concrete implementations:
    - [ ] `OpenAIClient` - via OpenAI API
    - [ ] `AnthropicClient` - via Anthropic API
    - [ ] `LocalClient` - via Ollama or local HTTP server
    - [ ] Error handling, retries, timeouts

- [ ] **agent/prompts.py - System Prompts**
  - [ ] `SYSTEM_PROMPT_TEMPLATE` - role, constraints, tool instructions
  - [ ] Few-shot examples:
    - [ ] Example 1: NL → shell command translation
    - [ ] Example 2: Multi-step task planning
    - [ ] Example 3: Tool error handling
  - [ ] Safety rules:
    - [ ] "Never execute destructive commands without approval"
    - [ ] "Always explain your reasoning"
    - [ ] "Ask for help if uncertain"

- [ ] **agent/agent_loop.py - ReAct Planning Loop**
  - [ ] `AgentLoop` class (pre-LangGraph MVP):
    - [ ] `invoke(request: str, context: dict) → str`
    - [ ] Loop implementation:
      1. [ ] Build messages with system prompt + context
      2. [ ] Call LLM.invoke()
      3. [ ] Parse tool_calls from response
      4. [ ] For each tool:
         - [ ] Check security
         - [ ] Execute (or request approval)
         - [ ] Collect result
      5. [ ] Append results to messages
      6. [ ] If more steps needed, repeat (max_steps=10)
      7. [ ] Return final response

- [ ] **agent/planning.py - Task Decomposition**
  - [ ] `Planner` class:
    - [ ] `decompose_goal(goal: str) → Plan`
    - [ ] Extract sub-goals
    - [ ] Estimate dependencies
    - [ ] Suggest parallel vs sequential execution

- [ ] **agent/executor.py - Execute LLM Decisions**
  - [ ] `Executor` class:
    - [ ] `execute_tool_calls(tool_calls, context) → List[ToolResult]`
    - [ ] Route each tool call to `ToolRunner`
    - [ ] Handle timeout & retry logic
    - [ ] Emit telemetry for each execution

---

### Package 3: tools/

**Purpose**: Tool interface & registry

- [ ] **tools/registry.py - Tool Registry**
  - [ ] `ToolRegistry` class (singleton or injected):
    - [ ] `register_tool(name, handler, schema, risk_level, plugin_name)`
    - [ ] `get_tool(name) → ToolDefinition`
    - [ ] `list_tools() → List[ToolDefinition]`
    - [ ] `get_tools_by_category(category) → List[ToolDefinition]`

- [ ] **tools/base.py - Tool Abstraction**
  - [ ] `ToolDefinition` dataclass:
    - [ ] `name: str`, `description: str`, `category: str`, `risk_level: str`
    - [ ] `parameters: dict` (JSON Schema)
    - [ ] `timeout_seconds: int`, `max_retries: int`
  - [ ] `ToolResult` dataclass:
    - [ ] `success: bool`, `output: str`, `error: str`, `duration_ms: int`

- [ ] **tools/runner.py - Execution Wrapper**
  - [ ] `ToolRunner` class:
    - [ ] `execute(tool_name, args, context) → ToolResult`
    - [ ] Call `SecurityController.check()` before execution
    - [ ] Wrap execution with timeout & error handling
    - [ ] Emit telemetry events (start/end)
    - [ ] Retry logic

- [ ] **tools/timeout.py - Timeout Enforcement**
  - [ ] `TimeoutManager` class:
    - [ ] Wrap async/sync functions with timeout
    - [ ] Graceful shutdown on timeout
    - [ ] Configurable per-tool timeouts

- [ ] **tools/schema.py - OpenAI Tool Schemas**
  - [ ] `tool_to_openai_schema(tool_def) → dict`
  - [ ] Convert `ToolDefinition` to OpenAI format:
    ```json
    {
      "type": "function",
      "function": {
        "name": "...",
        "description": "...",
        "parameters": {...}
      }
    }
    ```

- [ ] **tools/errors.py**
  - [ ] `ToolError` exception
  - [ ] `ToolTimeoutError`
  - [ ] `ToolSecurityError`

---

### Package 4: workflows/

**Purpose**: LangGraph-based orchestration

- [ ] **workflows/states.py - LangGraph State Definitions**
  - [ ] Define `TypedDict` states for LangGraph:
    - [ ] `AgentState` (messages, goal, plan, tools_used, etc.)
    - [ ] Support state persistence (checkpointing)

- [ ] **workflows/nodes.py - Graph Nodes**
  - [ ] `agent_node(state) → state` - LLM planning & tool calling
  - [ ] `tool_node(state) → state` - execute tools
  - [ ] `approval_node(state) → state` - request human approval
  - [ ] `memory_node(state) → state` - store turn in memory
  - [ ] Each node updates state and returns modified copy

- [ ] **workflows/edges.py - Graph Transitions**
  - [ ] Edge conditions:
    - [ ] `should_continue` - more steps needed?
    - [ ] `is_approved` - approval granted?
    - [ ] `has_error` - continue or pivot?

- [ ] **workflows/single_agent_react.py - Simple ReAct Graph**
  - [ ] `create_agent_graph() → StateGraph`
  - [ ] Nodes: agent → tool → check → [continue/end]
  - [ ] Compile to runnable with checkpointing

- [ ] **workflows/multi_agent.py - Multi-Agent Patterns**
  - [ ] `create_supervisor_graph()` - 1 supervisor + N workers
  - [ ] `create_specialist_graph()` - domain-specific agents
  - [ ] Agent selection logic

- [ ] **workflows/executor.py - Workflow Runtime**
  - [ ] `WorkflowExecutor` class:
    - [ ] `execute_workflow(workflow_def, params) → WorkflowResult`
    - [ ] State persistence/recovery
    - [ ] Stream intermediate events
    - [ ] Timeout management

- [ ] **workflows/predefined/** - YAML Workflow Definitions
  - [ ] `bootstrap.yaml` - "Setup new project environment"
  - [ ] `deployment.yaml` - "Deploy service to device"
  - [ ] `backup.yaml` - "Backup directory & upload"

---

### Package 5: memory/

**Purpose**: Session + persistent memory

- [ ] **memory/manager.py - Main Memory Controller**
  - [ ] `MemoryManager` class:
    - [ ] `store_turn(query, result, tags)` - save interaction
    - [ ] `recall(query, tags, limit) → List[MemoryRecord]` - retrieve
    - [ ] `forget(record_id)` - delete a record
    - [ ] `update_record(id, new_content)` - edit

- [ ] **memory/session.py - Session Storage**
  - [ ] `SessionStore` class:
    - [ ] In-memory rolling window of last N turns
    - [ ] `append_turn(user_input, ai_response, tools_used)`
    - [ ] `get_recent_turns(n=5) → List[Turn]`
    - [ ] `summarize()` - compress into summary

- [ ] **memory/store.py - Persistent Storage**
  - [ ] `PersistentStore` abstract class
  - [ ] `SQLiteMemoryStore` implementation:
    - [ ] Schema: id, type, title, content, metadata, created_at, accessed_count
    - [ ] CRUD operations
    - [ ] TTL enforcement (auto-delete old records)
  - [ ] Optional: PostgreSQL backend for distributed deployments

- [ ] **memory/schemas.py - Record Definitions**
  - [ ] `MemoryRecord` dataclass
  - [ ] `Turn` dataclass (single interaction)
  - [ ] Validation via Pydantic

- [ ] **memory/retrieval.py - Search**
  - [ ] `keyword_search(query) → List[MemoryRecord]`
  - [ ] `semantic_search(query, min_score) → List[MemoryRecord]` (if embeddings enabled)
  - [ ] Ranking by relevance & recency

- [ ] **memory/embedding.py - Vector Embeddings (Optional)**
  - [ ] `EmbeddingClient` - wrapper around OpenAI/local embedding service
  - [ ] Store vectors in persistent store
  - [ ] Cosine similarity search

---

### Package 6: security/

**Purpose**: Permission controller & RBAC

- [ ] **security/controller.py - Main Security Gate**
  - [ ] `SecurityController` class:
    - [ ] `check_command(command, user_role, context) → Decision`
    - [ ] Decision enum: ALLOW, NEED_APPROVAL, BLOCKED
    - [ ] Delegate to RiskClassifier, RBAC, Policy checks

- [ ] **security/classifier.py - Risk Classification**
  - [ ] `RiskClassifier` class:
    - [ ] `classify(command) → RiskLevel` (SAFE, MEDIUM, HIGH, CRITICAL)
    - [ ] Pattern matching (regex):
      - [ ] CRITICAL: `rm -rf /`, `mkfs`, `dd if=.*of=/dev`
      - [ ] HIGH: `rm -rf`, `userdel`, `service restart`
      - [ ] MEDIUM: `apt install`, `systemctl`, `ssh`
      - [ ] SAFE: read-only commands
    - [ ] Heuristic scoring

- [ ] **security/policies.py - Security Rules**
  - [ ] `SecurityPolicy` dataclass:
    - [ ] `blocked_patterns: List[str]` (regex)
    - [ ] `require_approval_levels: List[str]` (HIGH, CRITICAL, etc.)
    - [ ] `role_permissions: Dict[str, List[str]]`
  - [ ] Load from config

- [ ] **security/rbac.py - Role-Based Access Control**
  - [ ] `Role` enum: VIEWER, OPERATOR, ADMIN
  - [ ] `RBAC` class:
    - [ ] `can_execute(role, risk_level) → bool`
    - [ ] `can_approve(role, risk_level) → bool`
    - [ ] Hierarchical: admin > operator > viewer

- [ ] **security/approval.py - Human-in-the-Loop**
  - [ ] `ApprovalFlow` class:
    - [ ] `request_approval(command, reason) → ApprovalResult`
    - [ ] Present to user (stdin prompt or UI)
    - [ ] Return: approved/denied/edited
    - [ ] Log approval in audit trail

- [ ] **security/sandbox.py - Sandboxing Hooks**
  - [ ] `Sandbox` abstract class
  - [ ] `NoOpSandbox` (no sandboxing)
  - [ ] `DockerSandbox` (run in container - future)
  - [ ] `ChRootSandbox` (Unix chroot - future)

---

### Package 7: telemetry/

**Purpose**: Logging, metrics, health

- [ ] **telemetry/logger.py - Structured Logging**
  - [ ] Configure `structlog`:
    - [ ] JSON output to file/stdout
    - [ ] Include: timestamp, event_type, user, command, result, duration
  - [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - [ ] Redact sensitive data (passwords, keys)

- [ ] **telemetry/metrics.py - Metrics Collection**
  - [ ] Prometheus client:
    - [ ] `Counter`: tool_executions_total, approvals_granted, approvals_denied
    - [ ] `Histogram`: tool_execution_duration_seconds
    - [ ] `Gauge`: agent_status, last_error
  - [ ] Collect LLM metrics: tokens_in, tokens_out, latency

- [ ] **telemetry/events.py - Event Emission**
  - [ ] `EventEmitter` class:
    - [ ] `emit(event_type, data)` - async event broadcasting
    - [ ] Subscribe to events for custom handlers

- [ ] **telemetry/exporters.py - Log/Metrics Export**
  - [ ] `LogExporter` abstract class
  - [ ] `FileExporter` - write to local files
  - [ ] `PrometheusExporter` - expose /metrics endpoint
  - [ ] `ELKExporter` - send to Elasticsearch/Logstash (optional)

- [ ] **telemetry/health.py - Health Checks**
  - [ ] `HealthChecker` class:
    - [ ] `check_shell_status()` - Is PTY alive?
    - [ ] `check_llm_connectivity()` - Can reach LLM?
    - [ ] `check_memory_store()` - DB healthy?
    - [ ] `get_status() → HealthStatus`

---

### Package 8: orchestrator/

**Purpose**: Multi-device, SSH, MCP

- [ ] **orchestrator/devices.py - Device Inventory**
  - [ ] `Device` dataclass (per schema in Architectural Spec)
  - [ ] `DeviceInventory` class:
    - [ ] Load from YAML file (`~/.agentsh/devices.yaml`)
    - [ ] `get_device(id) → Device`
    - [ ] `get_by_role(role) → List[Device]`
    - [ ] `get_by_label(key, value) → List[Device]`
    - [ ] CRUD operations (add/remove/update devices)

- [ ] **orchestrator/ssh_executor.py - SSH Execution**
  - [ ] `SSHExecutor` class:
    - [ ] Connection pooling (paramiko or fabric)
    - [ ] `execute(device_id, command, cwd) → CommandResult`
    - [ ] Parallel execution (limit concurrency)
    - [ ] Timeout & retry logic
    - [ ] Log all commands to audit trail

- [ ] **orchestrator/coordinator.py - Central Orchestrator**
  - [ ] `Coordinator` class:
    - [ ] `orchestrate_task(task_def, devices) → AggregatedResult`
    - [ ] Route tasks to local shell or remote SSH
    - [ ] Aggregate results across devices
    - [ ] Error handling & rollback (basic)

- [ ] **orchestrator/mcp_server.py - MCP Server**
  - [ ] Implement MCP protocol (JSON-RPC):
    - [ ] Listen on socket (localhost:8001 by default)
    - [ ] Handle `call_tool` requests
    - [ ] Return tool results
  - [ ] Authentication:
    - [ ] Token validation (env var: `MCP_AUTH_TOKEN`)
    - [ ] Optional mTLS

- [ ] **orchestrator/mcp_tools.py - MCP Tool Definitions**
  - [ ] Export subset of tools as MCP server tools:
    - [ ] `execute_command(command, device_id)`
    - [ ] `list_files(device_id, path)`
    - [ ] `get_device_status(device_id)`
  - [ ] Risk-aware (don't expose critical tools by default)

- [ ] **orchestrator/agent_deployer.py - Remote Agent Deploy**
  - [ ] Deploy lightweight agent to remote device
  - [ ] Agent listens on local socket for commands
  - [ ] Return results to orchestrator

---

### Package 9: plugins/

**Purpose**: Domain-specific toolsets

- [ ] **plugins/core/shell_toolset.py - Shell Commands**
  - [ ] Tools:
    - [ ] `shell.run(command, cwd, env)` - execute shell command
    - [ ] `shell.explain(command)` - explain what a command does
  - [ ] Register with `ToolRegistry`

- [ ] **plugins/core/filesystem_toolset.py - File Operations**
  - [ ] Tools:
    - [ ] `fs.read(path, encoding)` - read file
    - [ ] `fs.write(path, content, mode)` - write file
    - [ ] `fs.list(path, recursive)` - list directory
    - [ ] `fs.delete(path)` - delete file (HIGH risk)
    - [ ] `fs.copy(src, dst)` - copy file
    - [ ] `fs.search(pattern, path)` - find files

- [ ] **plugins/core/process_toolset.py - Process Management**
  - [ ] Tools:
    - [ ] `process.list()` - list running processes
    - [ ] `process.kill(pid)` - kill process
    - [ ] `process.get_info(pid)` - CPU/memory stats

- [ ] **plugins/core/code_toolset.py - Code Editing**
  - [ ] Tools:
    - [ ] `code.edit(path, old_text, new_text)` - make edits
    - [ ] `code.view(path, start_line, end_line)` - show code

- [ ] **plugins/robotics/robotics_toolset.py - ROS Integration**
  - [ ] Detect ROS installation
  - [ ] Tools:
    - [ ] `ros.list_topics()` - ROS2 topic discovery
    - [ ] `ros.call_service(service, args)` - invoke ROS service
    - [ ] `ros.publish(topic, message)` - publish to topic
  - [ ] Safety gates for motion commands

- [ ] **plugins/robotics/safety.py - Robot Safety**
  - [ ] `RobotSafetyChecker` class:
    - [ ] Validate commands don't violate safety constraints
    - [ ] Check for emergency stop condition
    - [ ] Require maintenance mode before manipulation

---

### Package 10: utils/

**Purpose**: Common utilities

- [ ] **utils/env.py**
  - [ ] `get_env_or_fail(var_name)` - require env var
  - [ ] `get_env_or_default(var_name, default)` - optional env var

- [ ] **utils/crypto.py**
  - [ ] `encrypt_sensitive(data, key)` - encrypt secrets in memory
  - [ ] `decrypt_sensitive(encrypted, key)` - decrypt

- [ ] **utils/validators.py**
  - [ ] `is_valid_device_id(id)` - identifier validation
  - [ ] `is_safe_path(path)` - prevent path traversal
  - [ ] `sanitize_log_entry(entry)` - remove secrets

- [ ] **utils/async_utils.py**
  - [ ] `async_timeout(coro, timeout_seconds)`
  - [ ] `gather_with_limit(tasks, limit)` - limit concurrency

---

## Testing Checklist

- [ ] **Unit Tests** (tests/unit/)
  - [ ] `test_input_classifier.py` - input routing
  - [ ] `test_risk_classifier.py` - command risk scoring
  - [ ] `test_rbac.py` - permission checks
  - [ ] `test_tool_registry.py` - tool registration & lookup
  - [ ] `test_memory_store.py` - memory operations
  - [ ] `test_llm_client.py` - LLM client mocking

- [ ] **Integration Tests** (tests/integration/)
  - [ ] `test_agent_loop.py` - agent planning & execution
  - [ ] `test_shell_wrapper.py` - shell I/O
  - [ ] `test_security_flow.py` - approval requests
  - [ ] `test_workflow_execution.py` - LangGraph workflows
  - [ ] `test_remote_execution.py` - SSH to mock device

- [ ] **E2E Tests** (tests/e2e/)
  - [ ] `test_basic_request.py` - user types command, get response
  - [ ] `test_multi_step_task.py` - agent chains multiple tools
  - [ ] `test_approval_flow.py` - risky command requires approval

- [ ] **Security Tests** (tests/security/)
  - [ ] `test_prompt_injection.py` - LLM doesn't execute injected commands
  - [ ] `test_privilege_escalation.py` - RBAC prevents escalation
  - [ ] `test_blocked_commands.py` - patterns are actually blocked

---

## Documentation Checklist

- [ ] **API.md** - API reference for all public classes/functions
- [ ] **SECURITY.md** - Security model, threat model, best practices
- [ ] **PLUGIN_GUIDE.md** - How to write custom toolsets
- [ ] **WORKFLOW_GUIDE.md** - How to define workflows in YAML
- [ ] **TROUBLESHOOTING.md** - Common issues & solutions
- [ ] **DEPLOYMENT.md** - Production setup & configuration

---

## CI/CD Checklist

- [ ] **GitHub Actions Workflows** (.github/workflows/)
  - [ ] `lint.yml` - Run black, flake8, mypy
  - [ ] `test.yml` - Run pytest, coverage reports
  - [ ] `security.yml` - Bandit for security issues
  - [ ] `release.yml` - Build & publish to PyPI

---

## Deployment Checklist

- [ ] **Package Publishing**
  - [ ] Build: `python -m build`
  - [ ] Publish: `twine upload dist/*`
  - [ ] Verify on PyPI

- [ ] **Installation Testing**
  - [ ] `pip install agentsh`
  - [ ] `agentsh --help` works
  - [ ] `agentsh` starts interactive shell

- [ ] **Configuration Deployment**
  - [ ] Install script creates `~/.agentsh/` directory
  - [ ] Generate default config
  - [ ] Document first-time setup (API keys, etc.)

---

## Known Limitations & Future Work

- [ ] Phase 1-5: Single-agent local shell + basic LLM
- [ ] Phase 6-7: Memory & telemetry infrastructure
- [ ] Phase 8+: Multi-device, MCP server, robotics plugins

---

**Legend**:
- `[ ]` = Not started
- `[x]` = Complete
- `[~]` = In progress

Keep this checklist updated as development progresses!
