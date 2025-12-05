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


class TestFleetWorkflowEdges:
    """Test fleet/multi-device workflow edge functions."""

    def test_should_continue_fleet_to_device(self) -> None:
        """Should continue to device if not all processed."""
        from agentsh.workflows.edges import should_continue_fleet

        state = {
            "devices": ["device-1", "device-2", "device-3"],
            "device_results": {},
        }

        result = should_continue_fleet(state)
        assert result == "device"

    def test_should_continue_fleet_to_aggregate(self) -> None:
        """Should go to aggregate when all devices processed."""
        from agentsh.workflows.edges import should_continue_fleet
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.success = True

        state = {
            "devices": ["device-1", "device-2"],
            "device_results": {
                "device-1": mock_result,
                "device-2": mock_result,
            },
        }

        result = should_continue_fleet(state)
        assert result == "aggregate"

    def test_should_continue_fleet_canary_failure_ends(self) -> None:
        """Should end when canary fails with rollback enabled."""
        from agentsh.workflows.edges import should_continue_fleet
        from unittest.mock import MagicMock

        failed_result = MagicMock()
        failed_result.success = False

        state = {
            "devices": ["device-1", "device-2", "device-3", "device-4"],
            "device_results": {
                "device-1": failed_result,  # Canary failed
            },
            "canary_count": 1,
            "rollback_on_failure": True,
        }

        result = should_continue_fleet(state)
        assert result == "end"

    def test_should_continue_fleet_canary_success(self) -> None:
        """Should continue to next device when canary succeeds."""
        from agentsh.workflows.edges import should_continue_fleet
        from unittest.mock import MagicMock

        success_result = MagicMock()
        success_result.success = True

        state = {
            "devices": ["device-1", "device-2", "device-3", "device-4"],
            "device_results": {
                "device-1": success_result,  # Canary succeeded
            },
            "canary_count": 1,
            "rollback_on_failure": True,
        }

        result = should_continue_fleet(state)
        assert result == "device"

    def test_should_continue_fleet_no_canary(self) -> None:
        """Should continue normally without canary configuration."""
        from agentsh.workflows.edges import should_continue_fleet
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.success = True

        state = {
            "devices": ["device-1", "device-2", "device-3"],
            "device_results": {"device-1": mock_result},
            "canary_count": 0,
        }

        result = should_continue_fleet(state)
        assert result == "device"

    def test_should_rollback_true(self) -> None:
        """Should return True when rollback is needed."""
        from agentsh.workflows.edges import should_rollback
        from unittest.mock import MagicMock

        failed_result = MagicMock()
        failed_result.success = False

        state = {
            "rollback_on_failure": True,
            "device_results": {"device-1": failed_result},
        }

        assert should_rollback(state) is True

    def test_should_rollback_false_no_failures(self) -> None:
        """Should return False when no failures."""
        from agentsh.workflows.edges import should_rollback
        from unittest.mock import MagicMock

        success_result = MagicMock()
        success_result.success = True

        state = {
            "rollback_on_failure": True,
            "device_results": {"device-1": success_result},
        }

        assert should_rollback(state) is False

    def test_should_rollback_disabled(self) -> None:
        """Should return False when rollback disabled."""
        from agentsh.workflows.edges import should_rollback
        from unittest.mock import MagicMock

        failed_result = MagicMock()
        failed_result.success = False

        state = {
            "rollback_on_failure": False,
            "device_results": {"device-1": failed_result},
        }

        assert should_rollback(state) is False

    def test_should_rollback_empty_results(self) -> None:
        """Should return False with empty results."""
        from agentsh.workflows.edges import should_rollback

        state = {
            "rollback_on_failure": True,
            "device_results": {},
        }

        assert should_rollback(state) is False
