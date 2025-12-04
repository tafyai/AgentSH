"""Tests for workflow state definitions."""

import pytest
from datetime import datetime

from agentsh.security.classifier import RiskLevel
from agentsh.workflows.states import (
    AgentState,
    ApprovalRequest,
    DeviceResult,
    DeviceTarget,
    ToolCallRecord,
    WorkflowState,
    WorkflowStatus,
    create_initial_state,
    create_workflow_state,
)


class TestWorkflowStatus:
    """Test WorkflowStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Should have all expected status values."""
        assert WorkflowStatus.PENDING
        assert WorkflowStatus.RUNNING
        assert WorkflowStatus.WAITING_APPROVAL
        assert WorkflowStatus.COMPLETED
        assert WorkflowStatus.FAILED
        assert WorkflowStatus.CANCELLED


class TestToolCallRecord:
    """Test ToolCallRecord dataclass."""

    def test_create_record(self) -> None:
        """Should create tool call record."""
        record = ToolCallRecord(
            name="shell.run",
            arguments={"command": "ls"},
            result="file1\nfile2",
            success=True,
            duration_ms=100,
        )

        assert record.name == "shell.run"
        assert record.arguments == {"command": "ls"}
        assert record.success is True
        assert record.duration_ms == 100
        assert record.risk_level == RiskLevel.SAFE

    def test_default_timestamp(self) -> None:
        """Should have default timestamp."""
        record = ToolCallRecord(
            name="test",
            arguments={},
            result="",
            success=True,
        )

        assert isinstance(record.timestamp, datetime)


class TestApprovalRequest:
    """Test ApprovalRequest dataclass."""

    def test_create_request(self) -> None:
        """Should create approval request."""
        request = ApprovalRequest(
            tool_name="shell.run",
            arguments={"command": "rm -rf /tmp/test"},
            risk_level=RiskLevel.HIGH,
            reason="Destructive command",
            command="rm -rf /tmp/test",
        )

        assert request.tool_name == "shell.run"
        assert request.risk_level == RiskLevel.HIGH
        assert request.command == "rm -rf /tmp/test"


class TestAgentState:
    """Test AgentState TypedDict."""

    def test_create_initial_state(self) -> None:
        """Should create initial agent state."""
        state = create_initial_state(
            goal="List all files",
            max_steps=5,
        )

        assert state["goal"] == "List all files"
        assert state["max_steps"] == 5
        assert state["step_count"] == 0
        assert state["messages"] == []
        assert state["tools_used"] == []
        assert state["is_terminal"] is False
        assert state["error"] is None

    def test_create_state_with_context(self) -> None:
        """Should include context in state."""
        context = {"cwd": "/home/user", "env": {"PATH": "/usr/bin"}}
        state = create_initial_state(
            goal="Run command",
            context=context,
        )

        assert state["context"] == context
        assert state["context"]["cwd"] == "/home/user"


class TestDeviceTarget:
    """Test DeviceTarget dataclass."""

    def test_create_device_target(self) -> None:
        """Should create device target."""
        device = DeviceTarget(
            device_id="robot-001",
            hostname="robot-001.local",
            status="online",
        )

        assert device.device_id == "robot-001"
        assert device.hostname == "robot-001.local"
        assert device.status == "online"

    def test_default_status(self) -> None:
        """Should have default status."""
        device = DeviceTarget(
            device_id="test",
            hostname="test.local",
        )

        assert device.status == "unknown"


class TestDeviceResult:
    """Test DeviceResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create successful device result."""
        result = DeviceResult(
            device_id="robot-001",
            success=True,
            output="Command executed",
            duration_ms=500,
        )

        assert result.device_id == "robot-001"
        assert result.success is True
        assert result.output == "Command executed"
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Should create failed device result."""
        result = DeviceResult(
            device_id="robot-002",
            success=False,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"


class TestWorkflowState:
    """Test WorkflowState TypedDict."""

    def test_create_workflow_state(self) -> None:
        """Should create workflow state for fleet."""
        devices = [
            DeviceTarget(device_id="robot-001", hostname="r1.local"),
            DeviceTarget(device_id="robot-002", hostname="r2.local"),
        ]

        state = create_workflow_state(
            goal="Update all robots",
            devices=devices,
            parallel=True,
            canary_count=1,
        )

        assert state["agent_state"]["goal"] == "Update all robots"
        assert len(state["devices"]) == 2
        assert state["parallel"] is True
        assert state["canary_count"] == 1
        assert state["rollback_on_failure"] is True
        assert state["device_results"] == {}
