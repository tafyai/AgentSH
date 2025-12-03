# AgentSH: Comprehensive Architectural Specification

**Version:** 1.0
**Date:** December 2025
**Status:** Detailed Architecture Analysis & Design (No Implementation)

---

## Table of Contents

1. [Package Structure](#package-structure)
2. [Data Flow Analysis](#data-flow-analysis)
3. [Key Data Models (JSON Schemas)](#key-data-models-json-schemas)
4. [State Machines](#state-machines)
5. [Component Interactions](#component-interactions)
6. [Security Model](#security-model)
7. [Extension Points](#extension-points)

---

## Package Structure

### Recommended Directory Layout

```
agentsh/
├── src/
│   └── agentsh/
│       ├── __init__.py
│       ├── __main__.py              # CLI entrypoint
│       │
│       ├── shell/                   # Shell wrapper & PTY management
│       │   ├── __init__.py
│       │   ├── wrapper.py           # Main shell wrapper class
│       │   ├── pty_manager.py       # PTY lifecycle & I/O handling
│       │   ├── input_classifier.py  # Route input: shell vs AI
│       │   ├── prompt_renderer.py   # Custom prompt (PS1/PS2)
│       │   └── history.py           # Command history management
│       │
│       ├── agent/                   # AI core: planning loop & LLM integration
│       │   ├── __init__.py
│       │   ├── llm_client.py        # LLM backend abstraction
│       │   ├── agent_loop.py        # ReAct pattern: plan → execute → observe
│       │   ├── planning.py          # Task decomposition & reasoning
│       │   ├── prompts.py           # System prompts & few-shot examples
│       │   └── executor.py          # Execute LLM decisions
│       │
│       ├── tools/                   # Tool interface & registry
│       │   ├── __init__.py
│       │   ├── registry.py          # Tool registry & discovery
│       │   ├── base.py              # Abstract tool interface
│       │   ├── runner.py            # Tool execution wrapper
│       │   ├── timeout.py           # Timeout enforcement
│       │   ├── errors.py            # Tool-specific errors
│       │   └── schema.py            # OpenAI-compatible tool schemas
│       │
│       ├── workflows/               # LangGraph-based orchestration
│       │   ├── __init__.py
│       │   ├── base.py              # Base workflow definitions
│       │   ├── single_agent_react.py # Simple ReAct graph
│       │   ├── multi_agent.py       # Multi-agent patterns
│       │   ├── states.py            # LangGraph state definitions
│       │   ├── nodes.py             # Graph nodes (AI, tool, approval)
│       │   ├── edges.py             # Graph transitions
│       │   ├── predefined/          # YAML/Python workflow definitions
│       │   │   ├── bootstrap.yaml
│       │   │   ├── deployment.yaml
│       │   │   └── ...
│       │   └── executor.py          # Workflow runtime
│       │
│       ├── memory/                  # Session + persistent memory
│       │   ├── __init__.py
│       │   ├── manager.py           # Main memory controller
│       │   ├── session.py           # In-memory session storage
│       │   ├── store.py             # Persistent storage backend
│       │   ├── schemas.py           # Memory record schemas
│       │   ├── retrieval.py         # Semantic & keyword retrieval
│       │   └── embedding.py         # Vector embeddings (optional)
│       │
│       ├── security/                # Permission controller & RBAC
│       │   ├── __init__.py
│       │   ├── controller.py        # Main security gate
│       │   ├── classifier.py        # Risk level classification
│       │   ├── policies.py          # Security policies & rules
│       │   ├── rbac.py              # Role-based access control
│       │   ├── approval.py          # Human-in-the-loop flow
│       │   └── sandbox.py           # Sandboxing hooks
│       │
│       ├── telemetry/               # Logging, metrics, health
│       │   ├── __init__.py
│       │   ├── logger.py            # Structured logging
│       │   ├── metrics.py           # Metrics collection
│       │   ├── events.py            # Event emission
│       │   ├── exporters.py         # Log/metrics exporters
│       │   └── health.py            # Health checks
│       │
│       ├── orchestrator/            # Multi-device, SSH, MCP
│       │   ├── __init__.py
│       │   ├── coordinator.py       # Central orchestrator
│       │   ├── devices.py           # Device inventory model
│       │   ├── ssh_executor.py      # SSH connection pool & execution
│       │   ├── mcp_server.py        # MCP server implementation
│       │   ├── mcp_tools.py         # MCP tool definitions
│       │   └── agent_deployer.py    # Deploy agents to remote hosts
│       │
│       ├── plugins/                 # Extensible toolset plugins
│       │   ├── __init__.py
│       │   ├── base.py              # Plugin interface (Toolset ABC)
│       │   ├── loader.py            # Plugin discovery & loading
│       │   │
│       │   ├── core/                # Built-in toolsets
│       │   │   ├── shell_toolset.py     # Shell command execution
│       │   │   ├── filesystem_toolset.py # File operations
│       │   │   ├── process_toolset.py   # Process management
│       │   │   └── code_toolset.py      # Code editing
│       │   │
│       │   ├── robotics/
│       │   │   ├── robotics_toolset.py  # ROS integration
│       │   │   ├── safety.py            # Robot-specific safety rules
│       │   │   └── ros_interface.py     # ROS topic/service wrappers
│       │   │
│       │   ├── cloud/
│       │   │   └── kubernetes_toolset.py # K8s management
│       │   │
│       │   └── custom/              # User-defined plugins
│       │
│       ├── config/                  # Configuration management
│       │   ├── __init__.py
│       │   ├── parser.py            # YAML/JSON config parsing
│       │   ├── resolver.py          # Config hierarchy resolution
│       │   ├── schemas.py           # Config validation schemas
│       │   └── defaults.py          # Default configurations
│       │
│       └── utils/                   # Common utilities
│           ├── __init__.py
│           ├── env.py               # Environment variable helpers
│           ├── crypto.py            # Encryption/decryption
│           ├── validators.py        # Input validation
│           └── async_utils.py       # Async/await helpers
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── examples/
│   ├── workflows/
│   ├── plugins/
│   └── configs/
│
├── docs/
│   ├── DesignSpec.md
│   ├── ImplementationPlan.md
│   ├── ArchitecturalSpecification.md (this file)
│   ├── SECURITY.md
│   ├── API.md
│   └── PLUGIN_GUIDE.md
│
├── pyproject.toml
├── setup.py
├── Makefile
└── .github/
    └── workflows/
        ├── lint.yml
        ├── test.yml
        └── security.yml
```

### Package Boundaries & Responsibilities

| Package | Responsibility | Key Classes/Functions | Inputs | Outputs |
|---------|-----------------|----------------------|--------|---------|
| **shell** | User I/O & shell wrapping | `ShellWrapper`, `PTYManager`, `InputClassifier` | User keystrokes, shell I/O | Classified requests (raw shell cmd vs AI) |
| **agent** | LLM integration & planning | `LLMClient`, `AgentLoop`, `Executor` | Classified request, tools, memory | Plan, tool calls, response text |
| **tools** | Safe tool execution interface | `ToolRegistry`, `ToolRunner`, `BaseTask` | Tool name, args, context | Tool result (stdout, exit code, errors) |
| **workflows** | Multi-step orchestration | `StateGraph`, `LangGraph*`, `WorkflowExecutor` | Goal, workflow def, state | Workflow completion status, outputs |
| **memory** | Context persistence | `MemoryManager`, `SessionStore`, `VectorStore` | Facts, queries, context windows | Retrieved records, summaries |
| **security** | Permission enforcement | `SecurityController`, `RiskClassifier`, `RBAC` | Proposed command, user role | Allow/Block/NeedConfirmation decision |
| **telemetry** | Observability | `StructuredLogger`, `MetricsCollector`, `HealthCheck` | Events, actions, metrics | Logs, metrics exports, health status |
| **orchestrator** | Multi-device coordination | `Coordinator`, `DeviceInventory`, `MCPServer` | Devices, tasks, remote commands | Aggregated results, remote execution |
| **plugins** | Domain capabilities | `Toolset` (ABC), `RoboticsToolset`, etc. | Config, tool requests | Domain-specific tool results |

---

## Data Flow Analysis

### Flow 1: User Input → Shell Command Execution

```
┌─────────────────────────────────────────────────────────────────┐
│ User types: "find all Python files changed in last 7 days"      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                    ┌──────────────┐
                    │ ShellWrapper │
                    │  (capture)   │
                    └───────┬──────┘
                            │
                            ▼
                    ┌──────────────────────┐
                    │ InputClassifier      │
                    │ - Is valid shell cmd? No
                    │ - Starts with "!"?   No
                    │ - Starts with "ai "? No
                    │ → Treat as NL query  │
                    └───────┬──────────────┘
                            │
                            ▼
                    ┌──────────────────────┐
                    │ AgentCore.invoke()   │
                    │ - Load tools defs    │
                    │ - Get relevant mem   │
                    └───────┬──────────────┘
                            │
              ┌─────────────┼─────────────┐
              │ LLM.invoke(messages,     │
              │   tools=[shell, fs])     │
              │ - System prompt          │
              │ - User query             │
              │ - Available tools        │
              └─────────────┬─────────────┘
                            │
                    ┌───────▼────────────┐
                    │ LLM decides:       │
                    │ tool_calls:        │
                    │  [{name: shell.run,│
                    │    args: find ...}]│
                    └───────┬────────────┘
                            │
              ┌─────────────▼─────────────┐
              │ SecurityController.check()│
              │ - Risk level: SAFE        │
              │ - Action: ALLOW           │
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────────┐
              │ ToolRunner.execute_tool()     │
              │ - Run: find ... -mtime -7     │
              │ - Timeout: 30s                │
              │ - Telemetry: log start        │
              └─────────────┬─────────────────┘
                            │
                    ┌───────▼────────────┐
                    │ Shell execution    │
                    │ Returns stdout,    │
                    │ stderr, exit_code  │
                    └───────┬────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ Telemetry.log_event()      │
              │ - cmd, duration, result    │
              │ - Metrics: count++         │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ Memory.store_turn()        │
              │ - Query, result summary    │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ LLM.invoke() [2nd turn]    │
              │ - Append tool result       │
              │ - "Here are the results…"  │
              └─────────────┬──────────────┘
                            │
                    ┌───────▼────────────┐
                    │ Present to user    │
                    │ Display result +   │
                    │ optional summary   │
                    └────────────────────┘
```

### Flow 2: Security Validation & Approval

```
┌────────────────────────────────────────────────────────┐
│ AI proposes: "rm -rf /tmp/old_build"                   │
└──────────────────┬─────────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │ SecurityController  │
        │   .check_command()  │
        └──────────┬──────────┘
                   │
          ┌────────▼───────────┐
          │ RiskClassifier     │
          │ - Pattern match:   │
          │   "rm -rf" found   │
          │ - Risk: HIGH       │
          │ - Action: CONFIRM  │
          └────────┬───────────┘
                   │
          ┌────────▼────────────────────┐
          │ Check RBAC + mode           │
          │ - Current user role: admin  │
          │ - Can approve HIGH? Yes     │
          │ - Mode: normal (not lenient)│
          │ - Action: REQUEST APPROVAL  │
          └────────┬────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │ ApprovalFlow.request()           │
        │ Present plan:                    │
        │  "Proposed: rm -rf /tmp/…       │
        │   Risk Level: HIGH               │
        │   Reason: Recursive delete       │
        │   Approve? [y/n/edit]"          │
        └──────────┬───────────────────────┘
                   │
        ┌──────────▼──────────┐
        │ User responds       │
        │ Option 1: "y"       │
        │ Option 2: "n"       │
        │ Option 3: edit cmd  │
        └──────────┬──────────┘
                   │
        ┌──────────▼────────────────┐
        │ if approved:              │
        │ - Audit log: WHO, WHEN    │
        │ - Execute tool            │
        │                           │
        │ if rejected:              │
        │ - Tell AI: "Not approved" │
        │ - Offer alternative       │
        └──────────────────────────┘
```

### Flow 3: Memory Query & Storage

```
┌─────────────────────────────────────────────────────┐
│ Agent needs context: "What's the IP of db-prod?"    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────▼─────────────┐
        │ MemoryManager.recall() │
        │ - Query: "db-prod IP"  │
        └──────────┬─────────────┘
                   │
     ┌─────────────▼──────────────┐
     │ SessionStore (in-memory)   │
     │ - Check last N turns       │
     │ - Found: "server db-prod   │
     │   at 10.0.0.5"             │
     │ - Relevance score: HIGH    │
     └─────────────┬──────────────┘
                   │
     ┌─────────────▼──────────────┐
     │ Return to Agent:           │
     │ "10.0.0.5" (from session)  │
     └─────────────┬──────────────┘
                   │
                   ├─ If not in session ──┐
                   │                      │
                   │    ┌────────────────▼─────────────┐
                   │    │ PersistentStore (SQLite)     │
                   │    │ - Semantic search on vector  │
                   │    │   DB for "db-prod IP"        │
                   │    │ - Retrieve: device configs   │
                   │    └────────────────┬──────────────┘
                   │                    │
                   │    ┌───────────────▼──────────────┐
                   │    │ Return best match            │
                   │    │ Fallback: ask user or API    │
                   │    └──────────────────────────────┘
                   │
        ┌──────────▼──────────────┐
        │ Usage: Add to prompt    │
        │ "Context: db-prod IP is │
        │  10.0.0.5 (from memory)"│
        └──────────┬──────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │ After execution:         │
        │ Memory.store_turn()      │
        │ - Query, result, context │
        │ - Summary for future use │
        └──────────────────────────┘
```

### Flow 4: Multi-Device Orchestration

```
┌──────────────────────────────────────────────────────────┐
│ User: "Update all web servers to latest patch"          │
└──────────────────┬─────────────────────────────────────┘
                   │
        ┌──────────▼────────────────┐
        │ AgentCore.plan()          │
        │ - Parse intent            │
        │ - Query device inventory  │
        └──────────┬────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │ DeviceInventory.get_by_label()  │
        │ - Filter: role == "web"         │
        │ - Returns: [web1, web2, web3]   │
        └──────────┬──────────────────────┘
                   │
        ┌──────────▼────────────────────────────┐
        │ WorkflowExecutor.create_from_template()
        │ - Template: "patch_all_servers"      │
        │ - Substitute: devices=[web1,2,3]    │
        │ - Build LangGraph state              │
        └──────────┬───────────────────────────┘
                   │
     ┌─────────────▼────────────────────────┐
     │ LangGraph Workflow (Parallel nodes)  │
     │                                      │
     │  ┌─────────┐  ┌─────────┐            │
     │  │ web1    │  │ web2    │  …web3     │
     │  │ Patch   │  │ Patch   │  │ Patch   │
     │  └────┬────┘  └────┬────┘  └────┬────│
     │       │            │             │   │
     │       └────────────┼─────────────┘   │
     │                    │                 │
     │            ┌───────▼─────────┐       │
     │            │ Merge Results   │       │
     │            │ (success/fails) │       │
     │            └───────┬─────────┘       │
     └────────────────────┼────────────────┘
                          │
            ┌─────────────▼───────────┐
            │ Each device:            │
            │ 1. SSH connect (pool)   │
            │ 2. Check patch status   │
            │ 3. Run update cmd       │
            │ 4. Verify success       │
            │ 5. Telemetry log        │
            └─────────────┬───────────┘
                          │
            ┌─────────────▼──────────────────┐
            │ Aggregation node:              │
            │ - Count successes/failures     │
            │ - Compile report               │
            │ - Store in telemetry           │
            │ - Return to user               │
            └───────────────────────────────┘
```

### Flow 5: Telemetry Event Propagation

```
┌───────────────────────────────────────┐
│ Agent executes: "sudo apt update"     │
└──────────────┬────────────────────────┘
               │
    ┌──────────▼────────────┐
    │ ToolRunner.execute()  │
    │ - Start: emit event   │
    └──────────┬────────────┘
               │
    ┌──────────▼──────────────────┐
    │ StructuredLogger.log_event()│
    │ {                           │
    │   "timestamp": "2025-12-03", │
    │   "user": "admin",          │
    │   "agent_id": "main",       │
    │   "tool": "shell.run",      │
    │   "command": "apt update",  │
    │   "risk_level": "MEDIUM",   │
    │   "approved_by": "user123", │
    │   "status": "executing"     │
    │ }                           │
    └──────────┬──────────────────┘
               │
    ┌──────────▼─────────────────┐
    │ MetricsCollector.observe() │
    │ - Start timer              │
    │ - Inc tool call counter    │
    │ - Record risk level stats  │
    └──────────┬────────────────┘
               │
    ┌──────────▼────────────────┐
    │ Command executes…         │
    │ Exit code: 0, duration: 2s│
    └──────────┬────────────────┘
               │
    ┌──────────▼──────────────────┐
    │ StructuredLogger.log_event()│
    │ {                           │
    │   "timestamp": "...",       │
    │   "status": "completed",    │
    │   "exit_code": 0,           │
    │   "duration_ms": 2000,      │
    │   "output_lines": 42        │
    │ }                           │
    └──────────┬──────────────────┘
               │
    ┌──────────▼──────────────────┐
    │ MetricsCollector.observe()  │
    │ - Stop timer                │
    │ - Histogram: duration_ms    │
    │ - Counter: success_count++  │
    │ - Gauge: last_cmd_duration  │
    └──────────┬──────────────────┘
               │
    ┌──────────▼──────────────────────┐
    │ Exporter (async):                │
    │ - To stdout (JSON lines)         │
    │ - To file (~/.agentsh/logs/)     │
    │ - To Prometheus endpoint         │
    │ - To ELK stack (if configured)   │
    └──────────┬───────────────────────┘
               │
    ┌──────────▼─────────────────────────┐
    │ HealthCheck.evaluate():             │
    │ - Recent success rate: 98%          │
    │ - Avg tool duration: 1.5s           │
    │ - Status: HEALTHY                   │
    └─────────────────────────────────────┘
```

---

## Key Data Models (JSON Schemas)

### 1. Device Inventory Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Device",
  "description": "A managed device (server, robot, IoT device)",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique device identifier",
      "pattern": "^[a-z0-9_-]+$",
      "examples": ["web-server-1", "robot-arm-5", "sensor-pi"]
    },
    "name": {
      "type": "string",
      "description": "Human-readable name"
    },
    "hostname": {
      "type": "string",
      "description": "FQDN or IP address"
    },
    "port": {
      "type": "integer",
      "description": "SSH port",
      "default": 22,
      "minimum": 1,
      "maximum": 65535
    },
    "connection_method": {
      "type": "string",
      "enum": ["ssh", "local_agent", "mcp_server", "ros_bridge"],
      "description": "How to communicate with this device"
    },
    "credentials_profile": {
      "type": "string",
      "description": "Reference to credentials config (e.g., 'prod-ssh-key')"
    },
    "role": {
      "type": "string",
      "enum": ["web", "db", "cache", "compute", "robot", "sensor", "gateway"],
      "description": "Device role for task filtering"
    },
    "labels": {
      "type": "object",
      "description": "Arbitrary key-value labels for filtering",
      "additionalProperties": {
        "type": "string"
      },
      "examples": [
        {"env": "prod", "region": "us-west"},
        {"robot_type": "arm", "battery_type": "li-ion"}
      ]
    },
    "capabilities": {
      "type": "array",
      "description": "Device capabilities (e.g., tools it supports)",
      "items": {
        "type": "string",
        "enum": ["shell", "ros", "kubernetes", "docker", "python"]
      }
    },
    "telemetry_enabled": {
      "type": "boolean",
      "description": "Collect telemetry from this device",
      "default": true
    },
    "telemetry_interval_seconds": {
      "type": "integer",
      "description": "How often to poll telemetry",
      "default": 300
    },
    "metadata": {
      "type": "object",
      "description": "Additional metadata",
      "properties": {
        "os": {
          "type": "string",
          "enum": ["linux", "macos", "windows"],
          "description": "Operating system"
        },
        "os_version": {
          "type": "string"
        },
        "cpu_cores": {
          "type": "integer"
        },
        "memory_gb": {
          "type": "number"
        },
        "last_seen": {
          "type": "string",
          "format": "date-time"
        },
        "last_updated": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "safety_constraints": {
      "type": "object",
      "description": "Device-specific safety rules",
      "properties": {
        "requires_approval_for_motion": {
          "type": "boolean",
          "description": "Always request approval before robot motion"
        },
        "max_concurrent_operations": {
          "type": "integer",
          "description": "Max operations running simultaneously"
        },
        "restricted_commands": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Regex patterns of commands never to run on this device"
        }
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    }
  },
  "required": ["id", "hostname", "connection_method", "role"]
}
```

### 2. Memory Record Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MemoryRecord",
  "description": "A stored fact or context for agent recall",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique record ID (UUID)"
    },
    "type": {
      "type": "string",
      "enum": [
        "device_config",
        "user_preference",
        "solved_incident",
        "workflow_template",
        "environment_state",
        "custom_note"
      ],
      "description": "Type of memory"
    },
    "title": {
      "type": "string",
      "description": "Short title for recall"
    },
    "content": {
      "type": "string",
      "description": "Full text content"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "device_id": {
          "type": "string",
          "description": "Associated device (if any)"
        },
        "tags": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Searchable tags"
        },
        "importance": {
          "type": "string",
          "enum": ["low", "medium", "high", "critical"],
          "default": "medium"
        },
        "confidence": {
          "type": "number",
          "description": "How confident is this fact (0.0 - 1.0)",
          "minimum": 0,
          "maximum": 1
        },
        "source": {
          "type": "string",
          "enum": ["user_input", "inference", "external_api", "log_extraction"],
          "description": "How was this fact learned"
        },
        "related_records": {
          "type": "array",
          "items": {"type": "string"},
          "description": "IDs of related records"
        }
      }
    },
    "embeddings": {
      "type": "object",
      "description": "Vector embeddings for semantic search",
      "properties": {
        "model": {
          "type": "string",
          "description": "Embedding model used"
        },
        "vector": {
          "type": "array",
          "items": {"type": "number"},
          "description": "Dense vector (1536 dims for OpenAI embedding v3)"
        },
        "created_at": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "retention_policy": {
      "type": "object",
      "properties": {
        "ttl_days": {
          "type": "integer",
          "description": "Days until auto-deletion (null = keep forever)",
          "nullable": true
        },
        "sensitive": {
          "type": "boolean",
          "description": "Contains sensitive data (encrypt at rest)"
        },
        "pii_fields": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Paths to PII that should be redacted in logs"
        }
      }
    },
    "created_by": {
      "type": "string",
      "description": "User or agent that created this record"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    },
    "accessed_count": {
      "type": "integer",
      "description": "Number of times recalled",
      "default": 0
    }
  },
  "required": ["id", "type", "title", "content", "created_by"]
}
```

### 3. Tool Definition Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ToolDefinition",
  "description": "Schema for a callable tool (OpenAI-compatible format)",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Unique tool identifier",
      "pattern": "^[a-z][a-z0-9_.]*$",
      "examples": ["shell.run", "fs.read", "ros.list_topics"]
    },
    "description": {
      "type": "string",
      "description": "What does this tool do"
    },
    "category": {
      "type": "string",
      "enum": ["shell", "filesystem", "process", "network", "robotics", "cloud", "custom"],
      "description": "Tool category for organizing & filtering"
    },
    "risk_level": {
      "type": "string",
      "enum": ["safe", "medium", "high", "critical"],
      "description": "How dangerous is this tool"
    },
    "requires_approval_if": {
      "type": "object",
      "description": "Conditions that trigger approval requirement",
      "properties": {
        "patterns": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Regex patterns that match dangerous arguments"
        },
        "resources_above": {
          "type": "object",
          "description": "Resource thresholds that require approval",
          "properties": {
            "cpu_percent": {"type": "number"},
            "memory_mb": {"type": "number"},
            "disk_gb": {"type": "number"}
          }
        }
      }
    },
    "parameters": {
      "type": "object",
      "description": "Input schema (JSON Schema format)",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["object"]
        },
        "properties": {
          "type": "object",
          "description": "Argument definitions",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "type": {"type": "string"},
              "description": {"type": "string"},
              "enum": {"type": "array"},
              "default": {},
              "minimum": {"type": "number"},
              "maximum": {"type": "number"}
            }
          }
        },
        "required": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Required parameters"
        }
      }
    },
    "returns": {
      "type": "object",
      "description": "Output schema",
      "properties": {
        "type": {
          "type": "string"
        },
        "properties": {
          "type": "object"
        }
      }
    },
    "examples": {
      "type": "array",
      "description": "Usage examples for the LLM",
      "items": {
        "type": "object",
        "properties": {
          "description": {"type": "string"},
          "arguments": {"type": "object"},
          "expected_output": {"type": "string"}
        }
      }
    },
    "timeout_seconds": {
      "type": "integer",
      "description": "Max execution time",
      "default": 300
    },
    "max_retries": {
      "type": "integer",
      "description": "How many times to retry on failure",
      "default": 0
    },
    "plugin": {
      "type": "string",
      "description": "Which plugin provides this tool"
    },
    "available_on": {
      "type": "array",
      "items": {"type": "string"},
      "description": "OS/device types where available (empty = all)",
      "examples": [["linux", "macos"], ["robot"], ["kubernetes"]]
    }
  },
  "required": ["name", "description", "category", "risk_level", "parameters"]
}
```

### 4. Telemetry Event Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TelemetryEvent",
  "description": "An event logged by AgentSH for observability",
  "type": "object",
  "properties": {
    "event_id": {
      "type": "string",
      "description": "Unique event ID (UUID)"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "When event occurred"
    },
    "event_type": {
      "type": "string",
      "enum": [
        "tool_execution_start",
        "tool_execution_end",
        "approval_requested",
        "approval_granted",
        "approval_denied",
        "command_blocked",
        "agent_planning",
        "agent_reasoning",
        "memory_store",
        "memory_recall",
        "workflow_start",
        "workflow_end",
        "device_online",
        "device_offline",
        "error",
        "warning"
      ]
    },
    "context": {
      "type": "object",
      "description": "Contextual information",
      "properties": {
        "user": {
          "type": "string",
          "description": "Username or agent ID"
        },
        "role": {
          "type": "string",
          "description": "User role for RBAC"
        },
        "session_id": {
          "type": "string",
          "description": "Session ID for correlation"
        },
        "device_id": {
          "type": "string",
          "description": "Device being operated on"
        },
        "workflow_id": {
          "type": "string",
          "description": "If part of a workflow"
        }
      }
    },
    "event_data": {
      "type": "object",
      "description": "Type-specific event data",
      "properties": {
        "tool_name": {
          "type": "string",
          "description": "For tool_execution events"
        },
        "command": {
          "type": "string",
          "description": "Command string (sanitized)"
        },
        "exit_code": {
          "type": "integer",
          "description": "Process exit code"
        },
        "duration_ms": {
          "type": "integer",
          "description": "Execution time in ms"
        },
        "stdout_lines": {
          "type": "integer",
          "description": "Lines of output"
        },
        "stderr_snippet": {
          "type": "string",
          "description": "First error line (if any)"
        },
        "approval_reason": {
          "type": "string",
          "description": "Why approval was needed"
        },
        "approved_by": {
          "type": "string",
          "description": "Who approved it"
        },
        "memory_action": {
          "type": "string",
          "enum": ["store", "recall", "update", "forget"],
          "description": "For memory events"
        },
        "memory_record_id": {
          "type": "string",
          "description": "Reference to memory record"
        },
        "llm_tokens_in": {
          "type": "integer",
          "description": "Tokens sent to LLM"
        },
        "llm_tokens_out": {
          "type": "integer",
          "description": "Tokens received from LLM"
        },
        "error_message": {
          "type": "string",
          "description": "For error events"
        },
        "error_traceback": {
          "type": "string",
          "description": "Python traceback (for debug logs)"
        }
      }
    },
    "risk_level": {
      "type": "string",
      "enum": ["safe", "medium", "high", "critical"],
      "description": "Risk classification of the action"
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure", "pending", "cancelled"],
      "description": "Outcome"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Searchable tags for filtering"
    }
  },
  "required": ["event_id", "timestamp", "event_type", "status"]
}
```

### 5. LangGraph State Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentState",
  "description": "LangGraph state for single-agent ReAct workflow",
  "type": "object",
  "properties": {
    "messages": {
      "type": "array",
      "description": "Conversation history",
      "items": {
        "type": "object",
        "properties": {
          "role": {
            "type": "string",
            "enum": ["user", "assistant", "system", "tool"]
          },
          "content": {
            "type": "string"
          },
          "tool_calls": {
            "type": "array",
            "description": "Tools the assistant wants to call",
            "items": {
              "type": "object",
              "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "arguments": {"type": "object"}
              }
            }
          },
          "tool_results": {
            "type": "array",
            "description": "Results from tool execution",
            "items": {
              "type": "object",
              "properties": {
                "tool_call_id": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "goal": {
      "type": "string",
      "description": "High-level task or user request"
    },
    "plan": {
      "type": "string",
      "description": "Agent's decomposition of the goal into steps"
    },
    "step_count": {
      "type": "integer",
      "description": "Number of planning/execution steps taken"
    },
    "max_steps": {
      "type": "integer",
      "description": "Maximum iterations to prevent infinite loops"
    },
    "context": {
      "type": "object",
      "description": "Contextual data (retrieved from memory, device state, etc.)",
      "additionalProperties": true
    },
    "memory_context": {
      "type": "object",
      "description": "Retrieved memory records",
      "properties": {
        "records": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": {"type": "string"},
              "type": {"type": "string"},
              "content": {"type": "string"},
              "relevance_score": {"type": "number"}
            }
          }
        }
      }
    },
    "tools_used": {
      "type": "array",
      "description": "List of tools called so far",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "arguments": {"type": "object"},
          "timestamp": {"type": "string", "format": "date-time"},
          "result_summary": {"type": "string"}
        }
      }
    },
    "approvals_needed": {
      "type": "array",
      "description": "Pending approvals",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "tool_name": {"type": "string"},
          "arguments": {"type": "object"},
          "reason": {"type": "string"}
        }
      }
    },
    "is_terminal": {
      "type": "boolean",
      "description": "Whether workflow should end"
    },
    "final_result": {
      "type": "string",
      "description": "Result to return to user"
    },
    "error": {
      "type": "string",
      "description": "Any error encountered"
    },
    "telemetry_events": {
      "type": "array",
      "description": "Events to emit",
      "items": {
        "type": "object"
      }
    }
  },
  "required": ["messages", "goal", "step_count", "max_steps"]
}
```

---

## State Machines

### 1. Agent Execution States

```
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LIFECYCLE                            │
└─────────────────────────────────────────────────────────────────┘

START
  │
  ▼
┌─────────────────────┐
│ INITIALIZED         │  • Config loaded
│ (ready to execute)  │  • LLM client ready
└────────┬────────────┘  • Tools registered
         │
         ▼
┌─────────────────────┐
│ PLANNING            │  • Analyze user goal
│ (decomposing task)  │  • Query memory for context
└────────┬────────────┘  • Call LLM to create plan
         │
         ▼
┌─────────────────────────┐
│ AWAITING_DECISION       │  • LLM has decided actions
│ (ready for execution)   │  • May need approval
└────────┬────────────────┘
         │
         ├─ Has tool_calls? ───────┐
         │                         │
         │                    ┌────▼─────────────────┐
         │                    │ APPROVAL_PENDING     │  • Present plan to user
         │                    │ (waiting for human)  │  • User can: approve / deny / edit
         │                    └────┬────────────────┘
         │                         │
         │                    ┌────▼──────┐
         │                    │ APPROVED  │ (continue to execution)
         │                    │ DENIED    │ (go to REPLANNING)
         │                    │ EDITED    │ (go to REPLANNING)
         │                    └────┬──────┘
         │                         │
         └────────────┬────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │ EXECUTING              │  • Run tool(s)
         │ (tools running)        │  • Collect outputs
         └────────┬───────────────┘  • Handle errors
                  │
        ┌─────────┴──────────┐
        │                    │
   SUCCESS            TOOL_ERROR
        │                    │
        ▼                    ▼
    ┌────────┐       ┌─────────────────┐
    │        │       │ REPLANNING      │  • Analyze error
    │ Ready  │       │ (recovering)    │  • Modify plan
    │ for    │       │                 │  • Retry or pivot
    │next    │       └────────┬────────┘
    │step    │                │
    │        │                └──────┐
    └────┬───┘                       │
         │                           │
         └───────────┬───────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │ MORE_STEPS_NEEDED?   │
         │ (check goal progress)│
         └────┬──────────┬──────┘
              │          │
           YES│          │NO
              │          │
              ▼          ▼
         ┌─────┐   ┌──────────────┐
         │     │   │ COMPLETED    │  • Goal reached
         │     │   │ (success)    │  • Return result
         │     │   │              │  • Store in memory
         │     │   └──────┬───────┘
         │     │          │
         │     │    ┌─────┴──────┐
         │     │    │ TERMINAL?  │
         │     │    └──┬──────┬──┘
         └─────┘       │      │
            │          YES   NO
            │          │      │
         PLANNING <─────┘      └─ CONTINUE (user follow-up)
            │
            ▼
      (loop back)


         ┌──────────────────┐
         │ ERROR            │  • Unexpected failure
         │ (unrecoverable)  │  • Log & exit
         └────────┬─────────┘  • Report to user
                  │
                  ▼
            (END - failure)
```

### 2. Security Approval Flow

```
┌──────────────────────────────────────────┐
│ Tool execution requested                 │
│ Args: command="rm -rf /tmp/old"          │
└──────────────┬───────────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ SecurityController   │
    │ .check()             │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ RiskClassifier           │
    │ Analyze patterns:        │
    │ - "rm -rf" found         │
    │ - Risk level = HIGH      │
    └──────────┬───────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ RBAC check               │
    │ - User role: admin       │
    │ - Can do HIGH? YES       │
    │ - Mode: "normal"         │
    └──────────┬───────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ Policy lookup            │
    │ - Requires approval?     │
    │ - Always for HIGH+       │
    │ Result: NEED_APPROVAL    │
    └──────────┬───────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ ApprovalFlow.request()   │
    │ Display:                 │
    │  "Proposed: rm -rf …     │
    │   Risk: HIGH             │
    │   Reason: recursive del  │
    │   Approve? [y/n/e]"      │
    └──────────┬───────────────┘
               │
    ┌──────────┴──────────────┐
    │                         │
    ▼                         ▼
  APPROVED                  DENIED
    │                         │
    ▼                         ▼
┌─────────────┐       ┌─────────────────┐
│ Audit log   │       │ Tell agent:     │
│ WHO, WHEN   │       │ "Not approved"  │
│ Execute     │       │ Return to plan  │
│ command     │       │ (try different) │
└──────┬──────┘       └────────┬────────┘
       │                       │
       ▼                       ▼
  (tool runs)              (next step)


Other outcomes:

  ALLOW (safe cmds, RBAC permits):
    │
    ▼
  Skip approval → Execute immediately

  BLOCK (forbidden pattern, failed RBAC):
    │
    ▼
  Audit log (blocked attempt) → Error to agent
```

### 3. Workflow Execution Lifecycle

```
WORKFLOW LIFECYCLE (LangGraph)

  START
    │
    ▼
┌─────────────────────────┐
│ WORKFLOW_INITIALIZED    │  • Parse workflow def
│ (load template)         │  • Resolve parameters
└──────────┬──────────────┘  • Build state graph
           │
           ▼
┌─────────────────────────┐
│ WORKFLOW_STARTED        │  • Emit event
│ (execution begins)      │  • Start telemetry
└──────────┬──────────────┘  • Persist state
           │
           ▼
  ┌─ Node 1: Agent/Tool ─┐
  │                      │
  │  Input: state        │
  │  Output: new state   │
  │  Timeout: 300s       │
  │  Retry: if error     │
  │                      │
  └──────────┬───────────┘
             │
             ▼
  ┌─────────────────────────┐
  │ NODE_SUCCESS / ERROR    │
  │ - Log outcome           │
  │ - Update metrics        │
  │ - Store snapshot        │
  └──────────┬──────────────┘
             │
             ▼
  ┌─────────────────────┐
  │ EDGE CONDITION      │  Routes based on:
  │ (check next step)   │  - State.is_terminal
  │                     │  - Error flags
  │                     │  - Approval status
  └──────────┬──────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
  Node2   Node3    Terminal?
    │        │        │
    └────────┼─────────┘
             │
             ▼
    ┌──────────────────┐
    │ WORKFLOW_SUCCESS │  • All nodes succeeded
    │ WORKFLOW_FAILURE │  • Some node failed
    │ WORKFLOW_STOPPED │  • User halted
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ WORKFLOW_CLEANUP │  • Finalize resources
    │ (persist result) │  • Store in memory
    │                  │  • Emit completion event
    └────────┬─────────┘
             │
             ▼
            END
```

---

## Component Interactions

### Interaction Diagram: Request → Execution

```
┌──────────────────────────────────────────────────────────────────────┐
│  ShellWrapper                                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ User enters: ai "update all servers"                           │  │
│  │                                                                 │  │
│  │ InputClassifier.classify() → "AI_REQUEST"                      │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────────────────┘
                          │
            ┌─────────────▼──────────────┐
            │ AgentCore                  │
            │ .invoke(request)           │
            │ ┌────────────────────────┐ │
            │ │ 1. Check config        │ │
            │ │ 2. Load LLM client     │ │
            │ │ 3. Query memory        │ │
            │ │ 4. Build prompt        │ │
            │ │ 5. Classify tools      │ │
            │ └────────┬───────────────┘ │
            └─────────┬─────────────────┘
                      │
        ┌─────────────▼──────────────┐
        │ LLMClient.invoke()         │
        │ ┌──────────────────────┐   │
        │ │ system_prompt        │   │
        │ │ user_query           │   │
        │ │ tool_definitions     │   │
        │ │ previous_context     │   │
        │ │ memory_context       │   │
        │ └──────────┬───────────┘   │
        │            │               │
        │ ┌──────────▼────────────┐  │
        │ │ LLM responds:         │  │
        │ │ {                     │  │
        │ │  "reasoning": "...",  │  │
        │ │  "tool_calls": [      │  │
        │ │    {name, args}...    │  │
        │ │  ]                    │  │
        │ │ }                     │  │
        │ └──────────┬────────────┘  │
        └────────────┼──────────────┘
                     │
        ┌────────────▼──────────────────┐
        │ For each tool_call:           │
        │                              │
        │ 1. SecurityController        │
        │    .check_command()          │
        │    → ALLOW/NEED_APPROVAL/    │
        │      BLOCKED                 │
        │                              │
        │ 2. If NEED_APPROVAL:         │
        │    ApprovalFlow.request()    │
        │    → Wait for user yes/no    │
        │                              │
        │ 3. If APPROVED:              │
        │    ToolRunner.execute()      │
        │    ├─ Run in timeout wrapper │
        │    ├─ Emit telemetry start   │
        │    ├─ Execute tool           │
        │    ├─ Capture output         │
        │    └─ Emit telemetry end     │
        │                              │
        │ 4. Memory.store_turn()       │
        │    → Save query & result     │
        └────────────┬─────────────────┘
                     │
        ┌────────────▼──────────────────┐
        │ Loop back (until goal met)    │
        │                              │
        │ • Check: is_terminal?        │
        │ • If no: call LLM again      │
        │   with tool results as       │
        │   new context                │
        │ • If yes: return final       │
        │   response to user           │
        └────────────┬─────────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │ Present to user      │
         │ + Store in memory    │
         └──────────────────────┘
```

---

## Security Model

### Command Risk Classification Matrix

| Command Pattern | Risk Level | RBAC Required | Approval Flow | Sandbox Option |
|---|---|---|---|---|
| `ls`, `pwd`, `grep` | SAFE | Any user | None | No |
| `apt list`, `find` | SAFE | Any user | None | No |
| `curl`, `wget` | MEDIUM | operator+ | Auto-approve for operator | Yes |
| `systemctl restart` | MEDIUM | admin | Manual approval | Yes |
| `apt install` | MEDIUM | admin | Manual approval | Yes (chroot) |
| `rm -f <file>` | HIGH | admin | Manual approval | Yes |
| `rm -rf /` | CRITICAL | (blocked) | Blocked | N/A |
| `mkfs` | CRITICAL | (blocked) | Blocked | N/A |
| `dd if=...` | CRITICAL | (blocked) | Blocked | N/A |

### RBAC Model

```
Roles (hierarchical):
  viewer
    ├─ read-only telemetry
    ├─ no command execution
    └─ no device modification

  operator
    ├─ all viewer permissions
    ├─ execute safe commands
    ├─ execute medium-risk with approval
    ├─ manage standard workflows
    └─ cannot: install packages, restart services

  admin
    ├─ all operator permissions
    ├─ approve/deny medium+ commands
    ├─ create custom workflows
    ├─ manage device inventory
    ├─ configure security policies
    └─ cannot: bypass security checks (even admins need approval for CRITICAL)

Device-level RBAC:
  device.role == "production"
    → extra restrictions: require 2 admins to approve

  device.safety_constraints.requires_approval_for_motion == true
    → all motion commands require explicit approval
```

---

## Extension Points

### 1. Plugin Architecture (Toolset)

```python
# Template for creating a plugin

from agentsh.plugins.base import Toolset
from agentsh.tools.registry import ToolRegistry

class MyCustomToolset(Toolset):
    """Custom toolset for domain-specific operations."""

    name = "my_custom"
    version = "1.0.0"

    def register_tools(self, registry: ToolRegistry):
        """Register tools provided by this toolset."""
        registry.register_tool(
            name="my_custom.action1",
            handler=self.action1,
            schema={...},
            risk_level="safe",
            plugin_name=self.name
        )

    def configure(self, config: dict):
        """Load configuration for this toolset."""
        self.api_key = config.get("api_key")

    async def action1(self, arg1: str) -> str:
        """Do something custom."""
        return f"Processed {arg1}"

# In ~/.agentsh/config.yaml:
# plugins:
#   enabled:
#     - my_custom
#   my_custom:
#     api_key: "secret..."
```

### 2. Custom Workflow Definition

```yaml
# workflows/my_custom_workflow.yaml

name: "deploy_service"
description: "Deploy a service to a device"
version: "1.0"

parameters:
  service_name:
    type: string
    required: true
    description: "Name of service to deploy"
  device_id:
    type: string
    required: true
  version:
    type: string
    default: "latest"

nodes:
  - id: "check_device"
    type: "tool_call"
    tool: "process.list"
    args:
      filter: "check if device online"

  - id: "build"
    type: "tool_call"
    depends_on: ["check_device"]
    tool: "shell.run"
    args:
      command: "build service {{service_name}}"

  - id: "approval"
    type: "approval_gate"
    depends_on: ["build"]
    message: "Deploy {{service_name}} to {{device_id}}?"

  - id: "deploy"
    type: "tool_call"
    depends_on: ["approval"]
    tool: "remote.run"
    args:
      device_id: "{{device_id}}"
      command: "systemctl restart {{service_name}}"

edges:
  - from: "check_device"
    to: "build"
    condition: "status == success"
  - from: "build"
    to: "approval"
    condition: "always"
  - from: "approval"
    to: "deploy"
    condition: "approved"
```

### 3. Memory Record Querying

```python
# Agent can use memory context

memory_records = agent.memory.recall(
    query="robot arm calibration",
    tags=["robot", "calibration"],
    limit=5,
    min_confidence=0.8
)

for record in memory_records:
    # Use in prompt: "I found previous notes about robot calibration…"
    pass
```

### 4. Custom LLM Provider

```python
# Implement custom LLM client

from agentsh.agent.llm_client import LLMClient

class MyCustomLLM(LLMClient):
    """Wrapper around custom LLM service."""

    def invoke(self, messages: List[dict], tools=None, **kwargs) -> LLMResult:
        # Call your custom service
        response = my_service.call(messages, tools)

        return LLMResult(
            content=response["text"],
            tool_calls=parse_tools(response.get("actions", [])),
            stop_reason=response.get("stop_reason")
        )

# In config.yaml:
# llm:
#   provider: "custom"
#   handler_class: "mymodule.MyCustomLLM"
#   config:
#     service_url: "http://localhost:8000"
```

---

## Appendix: Configuration Schema Example

```yaml
# ~/.agentsh/config.yaml

shell:
  backend: /bin/zsh
  login_shell: true
  history_file: ~/.agentsh/history

llm:
  provider: openai  # or 'anthropic', 'local', 'custom'
  model: gpt-4o
  api_key_env: OPENAI_API_KEY
  temperature: 0.7
  max_tokens: 2000
  timeout_seconds: 60

agent:
  max_planning_steps: 10
  default_mode: "interactive"  # or 'autonomous'
  approval_mode: "normal"      # 'strict' | 'normal' | 'lenient'
  enable_memory: true
  enable_memory_learning: true

security:
  mode: "normal"  # 'strict' | 'normal' | 'lenient'
  require_approval_for:
    - "CRITICAL"
    - "HIGH"
  blocked_patterns:
    - "^rm -rf /"
    - "^mkfs"
    - "^dd if=.*of=/dev"
  rbac_enabled: true
  audit_log_path: ~/.agentsh/audit.log

memory:
  backend: "sqlite"  # or 'postgres', 'redis'
  path: ~/.agentsh/memory.db
  ttl_days: 90
  enable_embeddings: false  # set true for semantic search
  embedding_model: "text-embedding-3-small"

telemetry:
  enabled: true
  log_level: "info"
  exporters:
    - type: "file"
      path: ~/.agentsh/logs/
      format: "jsonl"
    - type: "prometheus"
      port: 9090
      enabled: true

plugins:
  enabled:
    - "core.shell"
    - "core.filesystem"
    - "core.process"
    - "robotics"

  robotics:
    ros_version: 2
    default_robot_namespace: "/robot"

orchestrator:
  devices_file: ~/.agentsh/devices.yaml
  ssh_config_path: ~/.ssh/config
  ssh_key_env: SSH_KEY_PATH
  connection_pool_size: 10

  mcp_server:
    enabled: false
    listen_addr: "127.0.0.1"
    listen_port: 8001
    require_auth: true
    auth_token_env: MCP_AUTH_TOKEN
```

---

**End of Architectural Specification**

This specification provides developers with:
1. Clear package structure and responsibilities
2. Data flow diagrams showing request → execution journeys
3. JSON schemas for key data models (devices, memory, tools, telemetry)
4. State machines for agent execution, approvals, and workflows
5. Component interaction diagrams
6. Security model with RBAC and risk classification
7. Extension points for plugins, workflows, and custom LLMs
8. Configuration examples

Developers can use this as a reference during implementation to ensure alignment with the overall architecture.
