"""Tests for workflow edge functions."""

import pytest

from agentsh.workflows.edges import (
    after_approval,
    after_recovery,
    after_tools,
    has_error,
    has_pending_tools,
    is_terminal,
    needs_approval,
    should_continue,
)
from agentsh.workflows.states import AgentState, ApprovalRequest, create_initial_state
from agentsh.security.classifier import RiskLevel


class TestShouldContinue:
    """Test should_continue edge function."""

    def test_routes_to_end_when_terminal(self) -> None:
        """Should route to end when terminal."""
        state = create_initial_state("test")
        state["is_terminal"] = True

        result = should_continue(state)
        assert result == "end"

    def test_routes_to_recovery_on_error(self) -> None:
        """Should route to recovery on error."""
        state = create_initial_state("test")
        state["error"] = "Something went wrong"

        result = should_continue(state)
        assert result == "recovery"

    def test_routes_to_end_at_max_steps(self) -> None:
        """Should route to end at max steps."""
        state = create_initial_state("test", max_steps=5)
        state["step_count"] = 5

        result = should_continue(state)
        assert result == "end"

    def test_routes_to_tools_with_pending_calls(self) -> None:
        """Should route to tools with pending calls."""
        from agentsh.agent.llm_client import ToolCall

        state = create_initial_state("test")
        state["pending_tool_calls"] = [
            ToolCall(id="1", name="shell.run", arguments={"command": "ls"})
        ]

        result = should_continue(state)
        assert result == "tools"

    def test_routes_to_approval_with_pending_approvals(self) -> None:
        """Should route to approval with pending approvals."""
        from agentsh.agent.llm_client import ToolCall

        state = create_initial_state("test")
        state["pending_tool_calls"] = [
            ToolCall(id="1", name="shell.run", arguments={"command": "rm -rf /"})
        ]
        state["approvals_pending"] = [
            ApprovalRequest(
                tool_name="shell.run",
                arguments={},
                risk_level=RiskLevel.HIGH,
                reason="Dangerous",
            )
        ]

        result = should_continue(state)
        assert result == "approval"

    def test_routes_to_end_with_no_calls(self) -> None:
        """Should route to end with no pending calls."""
        state = create_initial_state("test")

        result = should_continue(state)
        assert result == "end"


class TestAfterTools:
    """Test after_tools edge function."""

    def test_routes_to_agent_normally(self) -> None:
        """Should route to agent after tools."""
        state = create_initial_state("test")

        result = after_tools(state)
        assert result == "agent"

    def test_routes_to_end_when_terminal(self) -> None:
        """Should route to end when terminal."""
        state = create_initial_state("test")
        state["is_terminal"] = True

        result = after_tools(state)
        assert result == "end"

    def test_routes_to_recovery_on_error(self) -> None:
        """Should route to recovery on error."""
        state = create_initial_state("test")
        state["error"] = "Tool failed"

        result = after_tools(state)
        assert result == "recovery"


class TestAfterApproval:
    """Test after_approval edge function."""

    def test_routes_to_tools_with_approved_calls(self) -> None:
        """Should route to tools with approved calls."""
        from agentsh.agent.llm_client import ToolCall

        state = create_initial_state("test")
        state["pending_tool_calls"] = [
            ToolCall(id="1", name="shell.run", arguments={})
        ]

        result = after_approval(state)
        assert result == "tools"

    def test_routes_to_agent_when_all_blocked(self) -> None:
        """Should route to agent when all blocked."""
        state = create_initial_state("test")
        state["pending_tool_calls"] = []

        result = after_approval(state)
        assert result == "agent"

    def test_routes_to_end_when_terminal(self) -> None:
        """Should route to end when terminal."""
        state = create_initial_state("test")
        state["is_terminal"] = True

        result = after_approval(state)
        assert result == "end"


class TestAfterRecovery:
    """Test after_recovery edge function."""

    def test_routes_to_agent_for_retry(self) -> None:
        """Should route to agent for retry."""
        state = create_initial_state("test")

        result = after_recovery(state)
        assert result == "agent"

    def test_routes_to_end_when_terminal(self) -> None:
        """Should route to end when terminal."""
        state = create_initial_state("test")
        state["is_terminal"] = True

        result = after_recovery(state)
        assert result == "end"


class TestHelperFunctions:
    """Test helper edge functions."""

    def test_has_pending_tools(self) -> None:
        """Should detect pending tools."""
        from agentsh.agent.llm_client import ToolCall

        state = create_initial_state("test")
        assert has_pending_tools(state) is False

        state["pending_tool_calls"] = [
            ToolCall(id="1", name="test", arguments={})
        ]
        assert has_pending_tools(state) is True

    def test_has_error(self) -> None:
        """Should detect errors."""
        state = create_initial_state("test")
        assert has_error(state) is False

        state["error"] = "Something broke"
        assert has_error(state) is True

    def test_is_terminal(self) -> None:
        """Should detect terminal state."""
        state = create_initial_state("test", max_steps=5)
        assert is_terminal(state) is False

        state["is_terminal"] = True
        assert is_terminal(state) is True

        # Also terminal at max steps
        state["is_terminal"] = False
        state["step_count"] = 5
        assert is_terminal(state) is True

    def test_needs_approval(self) -> None:
        """Should detect pending approvals."""
        state = create_initial_state("test")
        assert needs_approval(state) is False

        state["approvals_pending"] = [
            ApprovalRequest(
                tool_name="test",
                arguments={},
                risk_level=RiskLevel.HIGH,
                reason="Test",
            )
        ]
        assert needs_approval(state) is True
