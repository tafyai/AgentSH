# AgentSH Architecture Summary

**Quick Reference for Understanding AgentSH's Design**

---

## What is AgentSH?

An AI-enhanced terminal shell that wraps around traditional shells (Bash/Zsh/Fish) to provide:
- Natural language understanding of commands
- Multi-step autonomous task execution
- Multi-device orchestration (servers, robots, IoT)
- Strong security controls & human oversight
- Comprehensive telemetry & logging

---

## Core Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│ User                                                         │
│ (Interactive Terminal or Autonomous Instruction)            │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│ SHELL WRAPPER (shell/)                                       │
│ - PTY Management                                             │
│ - Input Classification (Shell vs AI)                         │
│ - Custom Prompt Rendering                                   │
│ - History Management                                        │
└──────────────┬────────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│ SECURITY GATE (security/)                                    │
│ - Risk Classification                                        │
│ - RBAC Validation                                            │
│ - Approval Flow (Human-in-the-Loop)                         │
│ - Command Filtering                                         │
└──────────────┬────────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│ AI CORE (agent/)                                             │
│ - LLM Client (OpenAI, Anthropic, Local)                     │
│ - Planning & Reasoning                                      │
│ - Tool Calling (ReAct Pattern)                              │
│ - Context Management                                        │
└──────────────┬────────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│ ORCHESTRATION ENGINE (workflows/)                            │
│ - LangGraph State Graphs                                    │
│ - Multi-Step Task Execution                                │
│ - Parallel Processing (with limits)                        │
│ - State Persistence                                        │
└──────────────┬────────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│ TOOL INTERFACE (tools/)                                      │
│ - Tool Registry (what can the agent do?)                    │
│ - Execution Wrapper (timeout, retry, telemetry)            │
│ - Tool Schemas (OpenAI-compatible format)                  │
│ - Plugin Integration                                       │
└──────────────┬────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ PLUGINS (plugins/)                                           │
│ - Core: Shell, FileSystem, Process, Code                   │
│ - Robotics: ROS integration, safety checks                │
│ - Cloud: Kubernetes, Docker                                │
│ - Custom: User-defined toolsets                            │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ SUPPORTING SYSTEMS                                           │
│                                                              │
│ ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ │   Memory    │  │  Telemetry   │  │ Orchestrator │       │
│ │             │  │              │  │              │       │
│ │ • Session   │  │ • Logging    │  │ • Devices    │       │
│ │ • Persistent│  │ • Metrics    │  │ • SSH Exec   │       │
│ │ • Vectors   │  │ • Health     │  │ • MCP Server │       │
│ │ • Recall    │  │ • Events     │  │ • Coord      │       │
│ └─────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ EXECUTION BACKENDS                                           │
│ - Local Shell (bash/zsh/fish)                              │
│ - Remote SSH                                                │
│ - ROS/Robotics Middleware                                  │
│ - APIs (HTTP, gRPC)                                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Data Flows

### 1. User Request → Execution

```
User: "find all Python files changed in the last 7 days"
  ↓
InputClassifier: "This is natural language" → AI_REQUEST
  ↓
AgentCore: Plan → Call LLM
  ↓
LLM: "I should use 'find' command with -mtime filter"
  ↓
SecurityController: Check risk → SAFE → ALLOW
  ↓
ToolRunner: Execute command
  ↓
Result displayed to user
  ↓
Memory: Store interaction for future reference
```

### 2. Dangerous Command → Approval

```
Agent: "sudo apt remove python3-dev"
  ↓
SecurityController.check(): Risk = HIGH
  ↓
ApprovalFlow.request(): Show to user → "Proceed? [y/n]"
  ↓
User: "y"
  ↓
Audit Log: Record WHO approved WHAT WHEN
  ↓
Execute command
```

### 3. Multi-Device Task

```
User: "Update all web servers"
  ↓
DeviceInventory: Filter devices by role="web" → [web1, web2, web3]
  ↓
WorkflowExecutor: Create LangGraph with parallel nodes
  ↓
For each device (concurrently):
  - SSH connect
  - Run "apt update && apt upgrade"
  - Capture output
  - Handle errors
  ↓
Aggregate results
  ↓
Report to user
```

---

## Key Concepts

### Tool
A callable action the agent can invoke. Examples:
- `shell.run(command)` - run bash command
- `fs.read(path)` - read file
- `ros.list_topics()` - list ROS topics
- `remote.run(device, command)` - SSH to device

Each tool has:
- **Name** (e.g., "shell.run")
- **Description** (what it does)
- **Parameters** (input schema)
- **Risk Level** (SAFE, MEDIUM, HIGH, CRITICAL)
- **Handler** (the actual code)

### Workflow
A directed acyclic graph (DAG) of nodes & edges using LangGraph.

**Node types**:
- **Agent node** - LLM planning/reasoning
- **Tool node** - execute tools
- **Approval node** - request human confirmation
- **Condition node** - conditional routing

**Edges**:
- Routes between nodes based on state
- Can be sequential or parallel

### Memory Record
A stored fact that the agent can recall.

Types:
- Device configuration ("server X is at IP Y")
- Solved incident ("we fixed issue Z by doing A")
- User preference ("use apt, not snap")
- Workflow template ("standard deployment steps")

The agent uses memory to:
1. Avoid repeating work
2. Make better decisions (based on past experience)
3. Maintain context across sessions

### Telemetry Event
A recorded action or state change.

Includes:
- **What happened** (tool execution, approval, error)
- **When** (timestamp)
- **Who** (user/agent)
- **Details** (command, duration, result)
- **Risk** (safety level)

Used for:
- Audit trails (compliance)
- Debugging (what went wrong?)
- Analytics (how is the system performing?)
- Alerting (notify on anomalies)

---

## Security Model

### Risk Levels

| Level | Example | Action |
|-------|---------|--------|
| **SAFE** | `ls`, `grep`, `pwd` | Execute immediately |
| **MEDIUM** | `apt list`, `curl`, `restart service` | May need approval (depends on RBAC) |
| **HIGH** | `rm -rf`, `userdel`, `format disk` | Always require approval |
| **CRITICAL** | `rm -rf /`, `mkfs /dev/sda` | Block (even admins can't do it) |

### RBAC Roles (Hierarchical)

```
VIEWER
  ├─ Read-only telemetry
  └─ No execution

OPERATOR
  ├─ All viewer permissions
  ├─ Execute safe commands
  ├─ Medium-risk with approval
  └─ Cannot: install packages, modify services

ADMIN
  ├─ All operator permissions
  ├─ Approve/deny HIGH-risk commands
  ├─ Cannot: override CRITICAL (requires 2+ admins)
  └─ Full device/workflow management
```

### Approval Flow

```
Agent proposes dangerous command
  ↓
SecurityController classifies risk
  ↓
Check RBAC: Can this user approve?
  ↓
If user role insufficient: Block or escalate
  ↓
If user role sufficient:
  - Present command to user
  - Request explicit approval
  - Option to edit command before executing
  ↓
If approved:
  - Audit log the approval
  - Execute
  ↓
If denied:
  - Tell agent "Not approved"
  - Agent suggests alternative
```

---

## Extension Points

### 1. Custom Toolset (Plugin)

```python
from agentsh.plugins.base import Toolset

class MyToolset(Toolset):
    name = "my_domain"

    def register_tools(self, registry):
        registry.register_tool(
            name="my_domain.action",
            handler=self.do_action,
            schema={...},
            risk_level="safe"
        )

    async def do_action(self, arg1):
        return f"Done: {arg1}"
```

Enable in config:
```yaml
plugins:
  enabled:
    - my_domain
```

### 2. Custom Workflow

```yaml
name: my_workflow
description: My custom process

parameters:
  param1:
    type: string

nodes:
  - id: step1
    type: tool_call
    tool: shell.run
    args:
      command: "echo {{param1}}"

  - id: step2
    type: approval_gate
    depends_on: [step1]
    message: "Proceed?"

  - id: step3
    type: tool_call
    depends_on: [step2]
    tool: fs.write
    args:
      path: /tmp/result.txt
      content: "done"
```

Use: `workflow run my_workflow --param1 "hello"`

### 3. Custom Security Policy

In config:
```yaml
security:
  blocked_patterns:
    - "^rm -rf /"
    - "^mkfs"
  require_approval_for:
    - HIGH
    - CRITICAL
  role_permissions:
    viewer:
      - read_telemetry
    operator:
      - execute_safe
      - execute_medium_with_approval
    admin:
      - approve_commands
      - manage_devices
```

---

## Configuration Hierarchy

Configs loaded in order (later overrides earlier):

1. **Default** (`agentsh/config/defaults.py`)
2. **System** (`/etc/agentsh.conf`)
3. **User** (`~/.agentsh/config.yaml`)
4. **Environment** (env vars like `AGENTSH_LLM_MODEL`)
5. **CLI args** (command-line flags)
6. **Project** (`.agentsh.yml` in current directory)

---

## Execution Model

### Interactive Mode (Typical User)

```
agentsh
$ (custom prompt)
user> ai "what's the status of my web servers?"
    ↓
Agent plans → executes tools → returns result
    ↓
$ (custom prompt)
user> cd /tmp
user> find . -name "*.py" | head -5
    (normal shell, no AI)
user> ai "explain what that command does"
    ↓
Agent explains
```

### Autonomous Mode (Scheduled/Triggered)

```
agentsh --mode autonomous "Backup all devices and report errors"
  ↓
Agent parses goal
  ↓
For 8 hours:
  - Check device health
  - Start backup on each
  - Monitor progress
  - Handle failures
  - Collect summary
  ↓
Send report to user (email/webhook)
```

### MCP Server Mode (Remote AI Integration)

```
agentsh --mcp-server --port 8001
  ↓
Listens for MCP requests from remote LLMs
  ↓
Remote AI: "execute_command(device=web1, cmd=uptime)"
  ↓
AgentSH: SSH → device → run command → return result
```

---

## Deployment Scenarios

### Scenario 1: Personal Development Helper

```
Laptop → AgentSH → Local shell

User asks: "Set up Python project"
  ↓
Agent: Creates venv, installs deps, runs tests
  ↓
User: "Why is test X failing?"
  ↓
Agent: Analyzes logs, suggests fix
```

### Scenario 2: DevOps Automation

```
Central Server (AgentSH)
  ↓
Manages 100+ servers via SSH
  ↓
Scheduled task: "Deploy app to all prod servers"
  ↓
Agent: Iterates devices, deploys, verifies, alerts on failures
  ↓
Audit log: Every action recorded
```

### Scenario 3: Robotics Fleet

```
Central Orchestrator (AgentSH + ROS bridge)
  ↓
Connected to 10 robots via ROS/MCP
  ↓
User: "Update perception model on all robots"
  ↓
Agent:
  - Check each robot's status
  - Download model
  - Copy to robot
  - Run calibration
  - Verify performance
  ↓
Report: All successful (or per-robot errors)
```

---

## Important Design Principles

### 1. **Human Remains in Control**
- Agent proposes, human approves for dangerous actions
- Transparent reasoning (agent explains its thinking)
- Audit trails record all actions

### 2. **Modularity**
- Each package has clear responsibility
- Plugins extend without modifying core
- Configs allow disabling features

### 3. **Observability**
- Every action logged with context
- Metrics enable performance monitoring
- Health checks detect issues early

### 4. **Security First**
- Defense in depth: multiple layers
- Deny by default (require explicit allow)
- Role-based access control (RBAC)

### 5. **Robustness**
- Timeouts prevent hanging
- Retries handle transient failures
- Graceful degradation (fail safely)

### 6. **Extensibility**
- Plugins for custom tools
- Workflows for complex processes
- Configurable everything

---

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Language | Python 3.10+ | Rich AI libraries, type hints |
| LLM | OpenAI/Anthropic APIs + Local (Ollama) | Flexibility, cost control |
| Workflows | LangGraph | State management, persistence |
| LLM Abstraction | LangChain | Unified interface |
| PTY Wrapper | ptyprocess | Cross-platform shell spawning |
| Config | PyYAML | Human-readable, hierarchical |
| Logging | structlog | JSON logs, context injection |
| Metrics | Prometheus | Industry standard |
| Persistence | SQLite (local) / PostgreSQL (distributed) | Flexible, no external deps |
| Security | sudo + RBAC | OS-level integration |
| Testing | pytest | Python standard |
| Type Checking | mypy | Early error detection |
| Linting | black, flake8 | Code quality |

---

## Next Steps for Implementation

1. **Phase 0-1**: Basic shell wrapper + MVP LLM integration
2. **Phase 2-3**: Tool interface + security baseline
3. **Phase 4-5**: LangGraph workflows + multi-agent patterns
4. **Phase 6-7**: Memory + telemetry infrastructure
5. **Phase 8-10**: Multi-device orchestration + robotics + polish

See `DeveloperChecklist.md` for detailed task breakdown.

---

## File Structure Quick Reference

```
agentsh/
├── shell/         → User I/O, PTY, input classification
├── agent/         → LLM client, planning, execution
├── tools/         → Tool interface, registry, schemas
├── workflows/     → LangGraph graphs, nodes, edges
├── memory/        → Session + persistent storage
├── security/      → Risk classifier, RBAC, approval
├── telemetry/     → Logging, metrics, health checks
├── orchestrator/  → Multi-device, SSH, MCP server
├── plugins/       → Toolsets (shell, fs, robotics, etc.)
├── config/        → Config parsing & validation
└── utils/         → Helpers, validators, crypto
```

---

**This summary provides the conceptual foundation. For details:**
- **ArchitecturalSpecification.md** - Component design & data models
- **ImplementationPlan.md** - Phase breakdown & timeline
- **DeveloperChecklist.md** - Specific tasks & acceptance criteria
