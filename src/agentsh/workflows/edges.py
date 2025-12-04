"""LangGraph edge functions for routing between nodes."""

from typing import Literal

from agentsh.telemetry.logger import get_logger
from agentsh.workflows.states import AgentState

logger = get_logger(__name__)


# Type alias for routing decisions
RouteDecision = Literal["agent", "tools", "approval", "recovery", "end"]


def should_continue(state: AgentState) -> RouteDecision:
    """Determine the next node after agent node.

    Routes to:
    - "tools" if there are pending tool calls (no approval needed)
    - "approval" if there are high-risk tool calls
    - "end" if workflow is terminal or max steps exceeded
    - "recovery" if there's an error

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # Check for terminal state
    if state.get("is_terminal", False):
        logger.debug("Routing to end: terminal state")
        return "end"

    # Check for errors
    if state.get("error"):
        logger.debug("Routing to recovery: error detected")
        return "recovery"

    # Check max steps
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    if step_count >= max_steps:
        logger.debug("Routing to end: max steps reached")
        return "end"

    # Check for pending tool calls
    pending_calls = state.get("pending_tool_calls", [])
    if pending_calls:
        # Check if any need approval
        approvals = state.get("approvals_pending", [])
        if approvals:
            logger.debug("Routing to approval: pending approvals")
            return "approval"
        else:
            logger.debug("Routing to tools: pending tool calls")
            return "tools"

    # No tool calls - end
    logger.debug("Routing to end: no pending calls")
    return "end"


def after_tools(state: AgentState) -> RouteDecision:
    """Determine the next node after tool execution.

    Routes to:
    - "agent" to continue the loop
    - "end" if terminal
    - "recovery" if error

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    if state.get("is_terminal", False):
        return "end"

    if state.get("error"):
        return "recovery"

    # Continue to agent for next iteration
    return "agent"


def after_approval(state: AgentState) -> RouteDecision:
    """Determine the next node after approval.

    Routes to:
    - "tools" if there are approved tool calls
    - "agent" if all were blocked (let agent retry)
    - "end" if terminal

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    if state.get("is_terminal", False):
        return "end"

    pending_calls = state.get("pending_tool_calls", [])
    if pending_calls:
        return "tools"

    # All blocked - go back to agent
    return "agent"


def after_recovery(state: AgentState) -> RouteDecision:
    """Determine the next node after error recovery.

    Routes to:
    - "agent" to retry
    - "end" if recovery failed

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    if state.get("is_terminal", False):
        return "end"

    # Retry
    return "agent"


def has_pending_tools(state: AgentState) -> bool:
    """Check if there are pending tool calls.

    Args:
        state: Current workflow state

    Returns:
        True if there are pending tool calls
    """
    return bool(state.get("pending_tool_calls", []))


def has_error(state: AgentState) -> bool:
    """Check if there's an error in state.

    Args:
        state: Current workflow state

    Returns:
        True if there's an error
    """
    return bool(state.get("error"))


def is_terminal(state: AgentState) -> bool:
    """Check if workflow should terminate.

    Args:
        state: Current workflow state

    Returns:
        True if workflow should end
    """
    if state.get("is_terminal", False):
        return True

    if state.get("step_count", 0) >= state.get("max_steps", 10):
        return True

    return False


def needs_approval(state: AgentState) -> bool:
    """Check if any pending operations need approval.

    Args:
        state: Current workflow state

    Returns:
        True if approval is needed
    """
    return bool(state.get("approvals_pending", []))


# Multi-device workflow edges

def should_continue_fleet(state: dict) -> Literal["device", "aggregate", "end"]:
    """Determine next node for fleet workflow.

    Args:
        state: Workflow state with device info

    Returns:
        Next node name
    """
    devices = state.get("devices", [])
    device_results = state.get("device_results", {})

    # Check if all devices processed
    if len(device_results) >= len(devices):
        return "aggregate"

    # Check for canary failures
    canary_count = state.get("canary_count", 0)
    if canary_count > 0 and len(device_results) == canary_count:
        # Check if canary succeeded
        canary_failed = any(
            not r.success
            for r in list(device_results.values())[:canary_count]
        )
        if canary_failed and state.get("rollback_on_failure", True):
            return "end"

    return "device"


def should_rollback(state: dict) -> bool:
    """Check if rollback is needed.

    Args:
        state: Workflow state

    Returns:
        True if rollback should happen
    """
    if not state.get("rollback_on_failure", True):
        return False

    device_results = state.get("device_results", {})
    return any(not r.success for r in device_results.values())
