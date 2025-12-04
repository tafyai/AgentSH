"""Workflow state definitions for LangGraph."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TypedDict

from agentsh.agent.llm_client import Message, ToolCall
from agentsh.security.classifier import RiskLevel


class WorkflowStatus(Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolCallRecord:
    """Record of a tool call execution.

    Attributes:
        name: Tool name
        arguments: Tool arguments
        result: Tool result
        success: Whether execution succeeded
        duration_ms: Execution duration in milliseconds
        timestamp: When the call was made
        risk_level: Risk level of the tool
        approved: Whether it required and received approval
    """

    name: str
    arguments: dict[str, Any]
    result: str
    success: bool
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    risk_level: RiskLevel = RiskLevel.SAFE
    approved: bool = True


@dataclass
class ApprovalRequest:
    """Request for user approval.

    Attributes:
        tool_name: Tool requiring approval
        arguments: Tool arguments
        risk_level: Risk level
        reason: Why approval is needed
        command: Command string (for shell commands)
    """

    tool_name: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    reason: str
    command: Optional[str] = None


class AgentState(TypedDict, total=False):
    """State for single-agent workflow.

    This is the main state object passed between LangGraph nodes.
    All fields are optional to allow partial updates.

    Attributes:
        messages: Conversation history
        goal: The user's original request
        plan: Optional plan for multi-step tasks
        step_count: Current step number
        max_steps: Maximum allowed steps
        tools_used: Record of tool calls made
        pending_tool_calls: Tool calls waiting to be executed
        approvals_pending: Approval requests waiting
        is_terminal: Whether workflow should end
        final_result: Final response to user
        error: Error message if failed
        context: Execution context (cwd, env, etc.)
    """

    messages: list[Message]
    goal: str
    plan: Optional[str]
    step_count: int
    max_steps: int
    tools_used: list[ToolCallRecord]
    pending_tool_calls: list[ToolCall]
    approvals_pending: list[ApprovalRequest]
    is_terminal: bool
    final_result: Optional[str]
    error: Optional[str]
    context: dict[str, Any]


@dataclass
class DeviceTarget:
    """Target device for orchestration.

    Attributes:
        device_id: Unique device identifier
        hostname: Device hostname
        status: Current device status
    """

    device_id: str
    hostname: str
    status: str = "unknown"


@dataclass
class DeviceResult:
    """Result from executing on a device.

    Attributes:
        device_id: Device identifier
        success: Whether execution succeeded
        output: Command output
        error: Error message if failed
        duration_ms: Execution duration
    """

    device_id: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0


class WorkflowState(TypedDict, total=False):
    """State for multi-device workflows.

    Extends AgentState with device orchestration fields.

    Attributes:
        agent_state: Embedded single-agent state
        devices: Target devices
        device_results: Results per device
        current_device: Device currently being processed
        parallel: Whether to execute in parallel
        canary_count: Number of canary devices for rollout
        rollback_on_failure: Whether to rollback on any failure
    """

    agent_state: AgentState
    devices: list[DeviceTarget]
    device_results: dict[str, DeviceResult]
    current_device: Optional[str]
    parallel: bool
    canary_count: int
    rollback_on_failure: bool


def create_initial_state(
    goal: str,
    max_steps: int = 10,
    context: Optional[dict[str, Any]] = None,
) -> AgentState:
    """Create initial agent state.

    Args:
        goal: User's request
        max_steps: Maximum steps allowed
        context: Execution context

    Returns:
        Initial AgentState
    """
    return AgentState(
        messages=[],
        goal=goal,
        plan=None,
        step_count=0,
        max_steps=max_steps,
        tools_used=[],
        pending_tool_calls=[],
        approvals_pending=[],
        is_terminal=False,
        final_result=None,
        error=None,
        context=context or {},
    )


def create_workflow_state(
    goal: str,
    devices: list[DeviceTarget],
    max_steps: int = 10,
    parallel: bool = False,
    canary_count: int = 0,
) -> WorkflowState:
    """Create initial workflow state for multi-device operations.

    Args:
        goal: User's request
        devices: Target devices
        max_steps: Maximum steps per device
        parallel: Execute in parallel
        canary_count: Canary rollout count

    Returns:
        Initial WorkflowState
    """
    return WorkflowState(
        agent_state=create_initial_state(goal, max_steps),
        devices=devices,
        device_results={},
        current_device=None,
        parallel=parallel,
        canary_count=canary_count,
        rollback_on_failure=True,
    )
