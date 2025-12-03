# AgentSH: Complete End-to-End Solution Design

## Executive Summary

AgentSH is an AI-enhanced terminal shell that wraps traditional shells (Bash/Zsh/Fish) with LLM-powered capabilities. This document presents a complete end-to-end solution design synthesized from comprehensive analysis of the design specification and implementation plan.

**Key Capabilities:**
- Natural language to command translation
- Multi-step agentic task execution
- Multi-device/robotics orchestration
- Strong security with human-in-the-loop
- Memory and context management
- LangGraph workflow integration

---

## 1. Technology Stack

### 1.1 Core Technologies

| Component | Primary Choice | Alternative | Rationale |
|-----------|---------------|-------------|-----------|
| **Language** | Python 3.10+ | - | Rich AI ecosystem, type hints, async support |
| **PTY Wrapping** | ptyprocess + prompt_toolkit | pexpect | Cross-platform, mature, handles edge cases |
| **LLM Primary** | Anthropic Claude | OpenAI GPT-4 | Superior reasoning, 200k context, safety focus |
| **LLM Local** | Ollama (Mistral) | vLLM | Privacy-first, offline capability |
| **Workflows** | LangGraph >= 0.2.0 | Prefect | Multi-agent orchestration, LLM-native |
| **MCP Server** | Official MCP SDK | Custom JSON-RPC | Standard protocol for tool exposure |
| **Vector DB** | ChromaDB | FAISS (at scale) | Simple API, built-in embeddings |
| **Config** | YAML + Pydantic | JSON | Human-readable, validation support |

### 1.2 Key Libraries

```python
# Core dependencies
ptyprocess >= 0.7.0          # PTY management
prompt_toolkit >= 3.0        # Line editing, completion
anthropic >= 0.28.0          # Claude API
openai >= 1.3.0              # OpenAI API
langgraph >= 0.2.0           # Workflow orchestration
chromadb >= 0.4.0            # Vector database
pydantic >= 2.0              # Config validation
structlog >= 24.0            # Structured logging
paramiko >= 3.0              # SSH client
mcp >= 0.1.0                 # MCP protocol

# Optional/Plugins
rclpy                        # ROS2 integration
kubernetes                   # K8s plugin
```

---

## 2. System Architecture

### 2.1 Package Structure

```
agentsh/
├── __init__.py
├── main.py                    # Entry point
├── shell/                     # Shell Wrapper Interface
│   ├── __init__.py
│   ├── wrapper.py             # PTY wrapper implementation
│   ├── router.py              # Input routing (shell vs AI)
│   ├── history.py             # Command history
│   └── prompt.py              # Prompt customization
├── agent/                     # AI Agent Core
│   ├── __init__.py
│   ├── core.py                # Main agent loop
│   ├── llm_client.py          # LLM abstraction
│   ├── providers/             # LLM provider implementations
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── ollama.py
│   └── prompts.py             # System prompts
├── tools/                     # Tool Interface
│   ├── __init__.py
│   ├── registry.py            # Tool registration
│   ├── executor.py            # Tool execution
│   └── schema.py              # Tool schemas
├── workflows/                 # LangGraph Workflows
│   ├── __init__.py
│   ├── graphs.py              # Graph definitions
│   ├── nodes.py               # Node implementations
│   └── persistence.py         # State persistence
├── memory/                    # Memory Manager
│   ├── __init__.py
│   ├── session.py             # Session memory
│   ├── persistent.py          # Long-term storage
│   └── embeddings.py          # Vector search
├── security/                  # Security Controller
│   ├── __init__.py
│   ├── classifier.py          # Risk classification
│   ├── rbac.py                # Role-based access
│   ├── approval.py            # Human-in-the-loop
│   └── audit.py               # Audit logging
├── telemetry/                 # Telemetry Module
│   ├── __init__.py
│   ├── logging.py             # Structured logs
│   ├── metrics.py             # Prometheus metrics
│   └── health.py              # Health checks
├── orchestrator/              # Multi-device Orchestration
│   ├── __init__.py
│   ├── inventory.py           # Device management
│   ├── ssh.py                 # SSH execution
│   └── mcp_server.py          # MCP server
├── plugins/                   # Plugin System
│   ├── __init__.py
│   ├── base.py                # Toolset base class
│   ├── builtin/               # Built-in plugins
│   │   ├── shell.py
│   │   ├── filesystem.py
│   │   └── code.py
│   └── robotics/              # Robotics plugin
│       ├── __init__.py
│       ├── ros_bridge.py
│       └── safety.py
└── config/                    # Configuration
    ├── __init__.py
    ├── loader.py              # Config loading
    └── schema.py              # Config schema
```

### 2.2 Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SHELL WRAPPER (PTY)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Router    │  │   History   │  │   Prompt    │                 │
│  └──────┬──────┘  └─────────────┘  └─────────────┘                 │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ├─── Shell Command ───► Native Shell Execution
          │
          └─── AI Request ───────────────────────┐
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SECURITY CONTROLLER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │Risk Classify│  │    RBAC     │  │  Approval   │  │   Audit   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
└─────────┼────────────────┼────────────────┼───────────────┼─────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AI AGENT CORE                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │  LLM Client │  │   Planner   │  │       Memory Manager        │ │
│  │ (multi-prov)│  │  (ReAct)    │  │  ┌─────────┐  ┌──────────┐  │ │
│  └──────┬──────┘  └──────┬──────┘  │  │ Session │  │Persistent│  │ │
│         │                │         │  └─────────┘  └──────────┘  │ │
│         ▼                ▼         └─────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    LANGGRAPH WORKFLOWS                       │   │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────────┐   │   │
│  │  │ Plan │──│ Tool │──│Observe│──│Refine│──│Human Approval│   │   │
│  │  └──────┘  └──────┘  └──────┘  └──────┘  └──────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TOOL INTERFACE & REGISTRY                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      PLUGIN SYSTEM                           │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │   │
│  │  │   Shell   │  │FileSystem │  │   Code    │  │ Robotics  │ │   │
│  │  │  Toolset  │  │  Toolset  │  │  Toolset  │  │  Toolset  │ │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   LOCAL SHELL    │   │  REMOTE DEVICES  │   │  ROBOTICS (ROS)  │
│   (PTY Process)  │   │   (SSH/MCP)      │   │                  │
└──────────────────┘   └──────────────────┘   └──────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TELEMETRY MODULE                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Structured │  │  Prometheus │  │   Health    │                 │
│  │    Logs     │  │   Metrics   │  │   Checks    │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Interfaces

### 3.1 LLMClient Interface

```python
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    stop_reason: Optional[str] = None
    tokens_used: Optional[Dict[str, int]] = None


class LLMClient(ABC):
    """Multi-provider LLM abstraction."""

    @property
    @abstractmethod
    def provider(self) -> ProviderType:
        """Return provider type."""
        pass

    @abstractmethod
    def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Invoke LLM with messages and optional tools."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from LLM."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count."""
        pass
```

### 3.2 Toolset Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters: Dict[str, Any]  # JSON Schema
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False


class ToolRegistry:
    """Central registry for all tools."""

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str,
        parameters: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.SAFE,
    ) -> Tool:
        """Register a tool."""
        pass

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        pass

    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        pass

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """Execute a tool with validation."""
        pass


class Toolset(ABC):
    """Base class for plugins providing related tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique toolset name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @abstractmethod
    def register_tools(self, registry: ToolRegistry) -> None:
        """Register all tools with the registry."""
        pass

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure toolset from config dict."""
        pass
```

### 3.3 MemoryStore Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    id: str
    key: str
    value: Any
    metadata: Dict[str, Any]
    created_at: datetime
    embedding: Optional[List[float]] = None
    ttl_seconds: Optional[int] = None


@dataclass
class SearchResult:
    record: MemoryRecord
    relevance_score: float


class MemoryStore(ABC):
    """Abstract memory storage interface."""

    @abstractmethod
    def store(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Store a value with optional TTL."""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Optional[MemoryRecord]:
        """Retrieve by key."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        min_relevance: float = 0.0,
    ) -> List[SearchResult]:
        """Semantic search."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete by key."""
        pass
```

### 3.4 SecurityController Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationResult(str, Enum):
    APPROVED = "approved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"


@dataclass
class CommandRiskAssessment:
    command: str
    risk_level: RiskLevel
    reasons: List[str]
    dangerous_patterns: Optional[List[str]] = None


@dataclass
class ValidationContext:
    user: Optional[str] = None
    role: Optional[str] = None
    hostname: Optional[str] = None
    is_autonomous: bool = False


class SecurityController(ABC):
    """Security validation and control interface."""

    @abstractmethod
    def classify_risk(self, command: str) -> CommandRiskAssessment:
        """Classify command risk level."""
        pass

    @abstractmethod
    def validate(
        self,
        command: str,
        context: Optional[ValidationContext] = None,
    ) -> ValidationResult:
        """Validate command with context."""
        pass

    @abstractmethod
    def request_approval(
        self,
        command: str,
        reason: str,
    ) -> bool:
        """Request human approval."""
        pass

    @abstractmethod
    def log_action(
        self,
        action: str,
        command: str,
        user: Optional[str],
        result: str,
        risk_level: RiskLevel,
    ) -> None:
        """Log action for audit."""
        pass
```

---

## 4. Data Models

### 4.1 Device Inventory Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "device_id": {"type": "string"},
    "hostname": {"type": "string"},
    "ip_address": {"type": "string", "format": "ipv4"},
    "device_type": {
      "type": "string",
      "enum": ["server", "workstation", "robot", "iot_device", "edge_node"]
    },
    "role": {"type": "string"},
    "labels": {
      "type": "object",
      "additionalProperties": {"type": "string"}
    },
    "connection": {
      "type": "object",
      "properties": {
        "method": {"type": "string", "enum": ["ssh", "mcp", "ros"]},
        "port": {"type": "integer"},
        "credentials_profile": {"type": "string"}
      }
    },
    "capabilities": {
      "type": "array",
      "items": {"type": "string"}
    },
    "status": {
      "type": "string",
      "enum": ["online", "offline", "maintenance", "error"]
    },
    "last_heartbeat": {"type": "string", "format": "date-time"},
    "safety_constraints": {
      "type": "object",
      "properties": {
        "requires_approval": {"type": "boolean"},
        "max_velocity": {"type": "number"},
        "geofence": {"type": "object"}
      }
    }
  },
  "required": ["device_id", "hostname", "device_type"]
}
```

### 4.2 Tool Definition Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "description": {"type": "string"},
    "plugin_name": {"type": "string"},
    "risk_level": {
      "type": "string",
      "enum": ["safe", "low", "medium", "high", "critical"]
    },
    "requires_confirmation": {"type": "boolean"},
    "parameters": {
      "type": "object",
      "properties": {
        "type": {"const": "object"},
        "properties": {"type": "object"},
        "required": {"type": "array", "items": {"type": "string"}}
      }
    },
    "examples": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["name", "description", "parameters"]
}
```

### 4.3 Telemetry Event Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "timestamp": {"type": "string", "format": "date-time"},
    "event_type": {
      "type": "string",
      "enum": ["command_executed", "tool_called", "workflow_step", "error", "approval_request", "security_alert"]
    },
    "context": {
      "type": "object",
      "properties": {
        "session_id": {"type": "string"},
        "user": {"type": "string"},
        "device_id": {"type": "string"},
        "workflow_id": {"type": "string"}
      }
    },
    "event_data": {
      "type": "object",
      "properties": {
        "command": {"type": "string"},
        "tool_name": {"type": "string"},
        "duration_ms": {"type": "number"},
        "exit_code": {"type": "integer"},
        "risk_level": {"type": "string"}
      }
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure", "pending", "timeout"]
    }
  },
  "required": ["event_id", "timestamp", "event_type"]
}
```

---

## 5. Security Model

### 5.1 Risk Classification

```python
# Risk patterns and classification
BLOCKED_PATTERNS = [
    r'^rm\s+-rf\s+/$',           # rm -rf /
    r'^mkfs\.',                   # Format filesystems
    r'^dd\s+if=/dev/zero',        # Overwrite with zeros
    r'^:(){ :|:& };:',            # Fork bomb
]

HIGH_RISK_PATTERNS = [
    r'^rm\s+-rf\s+',              # Any recursive delete
    r'^sudo\s+',                  # Privileged commands
    r'^(useradd|userdel)',        # User management
    r'^systemctl\s+(stop|disable)', # Service changes
    r'^(reboot|shutdown)',        # System restart
]

MEDIUM_RISK_PATTERNS = [
    r'^apt-get\s+(install|remove)', # Package management
    r'^pip\s+install',            # Python packages
    r'^curl\s+.*\|\s*bash',       # Pipe to shell
]
```

### 5.2 RBAC Model

| Role | Capabilities | Restrictions |
|------|--------------|--------------|
| **viewer** | Read files, view telemetry, list processes | No modifications, no execution |
| **operator** | Execute safe/medium commands, restart services | No user management, no root access |
| **admin** | Full access with logging | Dangerous ops still require confirmation |
| **robot_tech** | Robot diagnostics, calibration, safe motion | No fast motion without approval |

### 5.3 Approval Workflow

```
┌─────────────────┐
│ Command Request │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      SAFE        ┌─────────────────┐
│ Risk Classify   │ ───────────────► │    Execute      │
└────────┬────────┘                  └─────────────────┘
         │ MEDIUM/HIGH
         ▼
┌─────────────────┐
│   RBAC Check    │
└────────┬────────┘
         │
         ├─── Denied ────► Block + Log
         │
         ▼
┌─────────────────┐
│ Request Approval│ ◄──────────────────────────────────┐
└────────┬────────┘                                    │
         │                                             │
         ├─── Approved ───► Execute + Log              │
         │                                             │
         ├─── Denied ─────► Block + Log                │
         │                                             │
         └─── Timeout ────► Block + Log ───────────────┘
```

---

## 6. LangGraph Workflow Patterns

### 6.1 ReAct Agent Loop

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    tool_calls_made: int
    awaiting_approval: bool


def agent_node(state: AgentState):
    """Main agent reasoning node."""
    response = llm_client.invoke(
        messages=state["messages"],
        tools=tool_registry.get_tools_as_definitions()
    )
    return {"messages": [response]}


def should_continue(state: AgentState):
    """Route based on last message."""
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        # Check if any tool requires approval
        for call in last_message.tool_calls:
            tool = tool_registry.get_tool(call.name)
            if tool.requires_confirmation:
                return "approval"
        return "tools"
    return "end"


# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("approval", approval_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {
    "tools": "tools",
    "approval": "approval",
    "end": END
})
workflow.add_edge("tools", "agent")
workflow.add_edge("approval", "tools")

graph = workflow.compile()
```

### 6.2 Multi-Device Orchestration Workflow

```python
def device_filter_node(state):
    """Filter devices by criteria."""
    devices = device_inventory.get_devices(
        role=state.get("target_role"),
        labels=state.get("target_labels"),
        status="online"
    )
    return {"target_devices": devices}


def parallel_execution_node(state):
    """Execute command on all target devices in parallel."""
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                execute_on_device, device, state["command"]
            ): device
            for device in state["target_devices"]
        }

        for future in concurrent.futures.as_completed(futures):
            device = futures[future]
            try:
                results[device.device_id] = future.result()
            except Exception as e:
                results[device.device_id] = {"error": str(e)}

    return {"results": results}


def aggregation_node(state):
    """Aggregate and summarize results."""
    successes = sum(1 for r in state["results"].values() if "error" not in r)
    failures = len(state["results"]) - successes

    return {
        "summary": {
            "total": len(state["results"]),
            "successes": successes,
            "failures": failures,
            "details": state["results"]
        }
    }
```

---

## 7. Configuration System

### 7.1 Configuration Schema

```yaml
# ~/.agentsh/config.yaml

llm:
  provider: anthropic          # openai, anthropic, ollama
  model: claude-3-opus-20240229
  api_key_env: ANTHROPIC_API_KEY
  temperature: 0.7
  max_tokens: 4096
  fallback_provider: ollama    # Use local if API unavailable
  fallback_model: mistral

shell:
  backend: zsh                 # bash, zsh, fish
  init_script: ~/.zshrc
  history_size: 10000
  ai_prefix: "ai "             # Prefix to force AI routing
  shell_prefix: "!"            # Prefix to force shell routing

security:
  mode: normal                 # strict, normal, lenient
  require_confirmation: true
  allow_autonomous: false
  audit_log_path: ~/.agentsh/audit.log
  deny_patterns:
    - "rm -rf /"
    - "mkfs"
  max_command_length: 10000

memory:
  type: persistent             # in-memory, persistent
  db_path: ~/.agentsh/memory.db
  session_max_entries: 100
  enable_semantic_search: true
  embedding_model: all-MiniLM-L6-v2
  retention_days:
    configuration: 730
    incident: 365
    interaction: 90

plugins:
  - name: shell
    enabled: true
  - name: filesystem
    enabled: true
  - name: code
    enabled: true
  - name: robotics
    enabled: false
    config:
      ros_master_uri: http://localhost:11311
      safety_mode: strict

orchestrator:
  enabled: false
  devices_file: ~/.agentsh/devices.yaml
  ssh_timeout: 30
  max_parallel_connections: 10
  mcp_server:
    enabled: false
    port: 9999
    auth_token_env: AGENTSH_MCP_TOKEN

telemetry:
  enabled: true
  log_level: INFO
  log_file: ~/.agentsh/agentsh.log
  metrics_enabled: false
  metrics_port: 9090

log_level: INFO
```

### 7.2 Configuration Loading Order

1. `/etc/agentsh/config.yaml` (system-wide)
2. `~/.agentsh/config.yaml` (user-level)
3. `.agentsh.yaml` (project-level)
4. Environment variables (`AGENTSH_*`)

---

## 8. Robotics Integration

### 8.1 ROS2 MCP Bridge

```python
class ROS2MCPBridge:
    """Bridge between ROS2 and MCP protocol."""

    def __init__(self):
        self.node = rclpy.create_node('agentsh_bridge')
        self.subscriptions = {}
        self.services = {}

    async def expose_ros_topics_as_mcp_tools(self):
        """Expose ROS topics as MCP tools."""
        topics = await self.node.get_topic_names_and_types()

        for topic_name, topic_types in topics:
            tool = Tool(
                name=f"ros_subscribe_{topic_name.replace('/', '_')}",
                description=f"Subscribe to ROS topic {topic_name}",
                parameters={"duration_seconds": {"type": "number"}}
            )
            self.tool_registry.register_tool(tool)

    async def call_ros_service(self, service_name: str, args: dict):
        """Call a ROS service."""
        # Implementation
        pass
```

### 8.2 Robot Safety Controller

```python
class RobotSafetyState(Enum):
    IDLE = "idle"
    ACTIVE_SUPERVISED = "supervised"
    ACTIVE_AUTONOMOUS = "autonomous"
    EMERGENCY_STOP = "estop"
    MAINTENANCE = "maintenance"


class RobotSafetyController:
    """Safety controller for robot operations."""

    VALID_TRANSITIONS = {
        RobotSafetyState.IDLE: [
            RobotSafetyState.ACTIVE_SUPERVISED,
            RobotSafetyState.MAINTENANCE
        ],
        RobotSafetyState.ACTIVE_SUPERVISED: [
            RobotSafetyState.IDLE,
            RobotSafetyState.EMERGENCY_STOP,
            RobotSafetyState.ACTIVE_AUTONOMOUS
        ],
        RobotSafetyState.ACTIVE_AUTONOMOUS: [
            RobotSafetyState.IDLE,
            RobotSafetyState.EMERGENCY_STOP,
            RobotSafetyState.ACTIVE_SUPERVISED
        ],
        RobotSafetyState.EMERGENCY_STOP: [
            RobotSafetyState.IDLE  # Manual reset only
        ],
    }

    def validate_motion(self, motion_command: dict) -> ValidationResult:
        """Validate motion before execution."""
        checks = [
            self._check_emergency_stop(),
            self._check_battery_level(),
            self._check_temperature(),
            self._check_joint_limits(motion_command),
            self._check_collision_path(motion_command),
            self._check_geofence(motion_command),
            self._check_human_proximity(),
        ]

        failures = [c for c in checks if not c.passed]

        return ValidationResult(
            approved=len(failures) == 0,
            failures=failures
        )
```

---

## 9. Testing Strategy Summary

### 9.1 Test Categories

| Category | Coverage Target | Key Focus |
|----------|-----------------|-----------|
| **Unit** | > 85% | LLM mocking, PTY tests, security rules |
| **Integration** | > 80% | Agent loop E2E, workflow execution, plugins |
| **Security** | 100% of vectors | Prompt injection, command bypass, RBAC |
| **Performance** | Benchmarks | LLM latency, memory usage, concurrency |
| **Safety** | 100% critical paths | E-stop, motion approval, simulation |

### 9.2 Quality Gates

| Phase | Min Coverage | Security Tests | Performance Tests |
|-------|--------------|----------------|-------------------|
| 0-1 | 70% | Static analysis | - |
| 2-3 | 80% | Prompt injection, RBAC | Latency benchmarks |
| 4-5 | 85% | All security tests | Workflow performance |
| 6-9 | 90% | All + red team | Full suite |
| 10 | 95% | Penetration testing | Load testing |

---

## 10. Implementation Phases

### Phase 0: Foundations (Weeks 1-2)
- Repository setup, CI/CD
- Configuration system
- Plugin registry scaffold
- Basic logging

### Phase 1: Shell Wrapper (Weeks 2-4)
- PTY wrapper implementation
- Input routing (shell vs AI)
- Command history
- Prompt customization

### Phase 2: LLM Integration (Weeks 4-6)
- LLM client abstraction
- Provider implementations (OpenAI, Anthropic, Ollama)
- Basic agent loop (ReAct pattern)
- Tool calling format

### Phase 3: Security Baseline (Weeks 6-8)
- Risk classification
- RBAC implementation
- Human-in-the-loop approval
- Audit logging

### Phase 4: Toolsets (Weeks 8-10)
- Tool interface and registry
- Shell toolset
- Filesystem toolset
- Code toolset

### Phase 5: LangGraph Workflows (Weeks 10-12)
- Workflow graph definitions
- State persistence
- Human approval nodes
- Multi-step orchestration

### Phase 6: Memory System (Weeks 12-14)
- Session memory
- Persistent storage
- Vector embeddings for semantic search
- Memory pruning

### Phase 7: Telemetry (Weeks 14-16)
- Structured logging
- Prometheus metrics
- Health checks
- Alert integration

### Phase 8: Multi-Device Orchestration (Weeks 16-18)
- Device inventory
- SSH execution layer
- MCP server implementation
- Fleet workflows

### Phase 9: Robotics Plugin (Weeks 18-20)
- ROS2 integration
- Safety controller
- Motion approval workflow
- Fleet robotics operations

### Phase 10: Polish & Hardening (Weeks 20-22)
- UX improvements
- Performance optimization
- Security hardening
- Documentation

---

## 11. Deployment Architecture

### 11.1 Local Development

```
┌─────────────────────────────────────────┐
│              Developer Machine           │
│  ┌───────────────────────────────────┐  │
│  │           AgentSH                  │  │
│  │  ┌─────────┐  ┌─────────────────┐ │  │
│  │  │  PTY    │  │   LLM Client    │ │  │
│  │  │ Wrapper │  │ (API/Local)     │ │  │
│  │  └─────────┘  └─────────────────┘ │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │      SQLite Memory          │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 11.2 Team/Enterprise Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                        Central Server                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   AgentSH Orchestrator                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│  │
│  │  │ MCP Server  │  │ PostgreSQL  │  │  Prometheus/Grafana ││  │
│  │  │  (API)      │  │  Memory DB  │  │     Telemetry       ││  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘│  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
       ┌───────────┐   ┌───────────┐   ┌───────────┐
       │ Server 1  │   │ Server 2  │   │  Robot 1  │
       │  (SSH)    │   │  (SSH)    │   │  (ROS)    │
       └───────────┘   └───────────┘   └───────────┘
```

---

## 12. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Command Translation Accuracy** | > 95% | Correct command generated for NL request |
| **Agent Loop Latency** | < 3s typical | Time from request to first action |
| **Security Block Rate** | 100% | Dangerous commands blocked |
| **False Positive Rate** | < 5% | Safe commands incorrectly blocked |
| **Multi-Device Throughput** | 100+ devices | Concurrent operations |
| **Memory Recall Accuracy** | > 90% | Relevant memory retrieved |
| **Robot Safety Compliance** | 100% | All motions validated |
| **System Uptime** | > 99.9% | Availability |

---

## Conclusion

This solution design provides a comprehensive blueprint for implementing AgentSH. The architecture emphasizes:

1. **Modularity**: Clear separation of concerns with plugin-based extensibility
2. **Security**: Defense-in-depth with risk classification, RBAC, and human-in-the-loop
3. **Scalability**: From single-user to fleet orchestration
4. **Safety**: Specialized robotics safety controls
5. **Maintainability**: Comprehensive testing and observability

The phased implementation approach allows incremental delivery while maintaining system integrity. Each phase builds on the previous, with clear quality gates ensuring production readiness.
