"""Tests for orchestration coordinator."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentsh.orchestrator.coordinator import (
    Coordinator,
    DeviceTaskResult,
    FailurePolicy,
    OrchestrationResult,
    OrchestrationTask,
    RolloutStrategy,
    get_coordinator,
    set_coordinator,
)
from agentsh.orchestrator.devices import (
    Device,
    DeviceStatus,
    DeviceType,
)
from agentsh.orchestrator.ssh import CommandResult, ParallelResult


class TestRolloutStrategy:
    """Tests for RolloutStrategy enum."""

    def test_strategy_values(self):
        """Should have expected strategy values."""
        assert RolloutStrategy.ALL_AT_ONCE.value == "all_at_once"
        assert RolloutStrategy.SERIAL.value == "serial"
        assert RolloutStrategy.CANARY.value == "canary"
        assert RolloutStrategy.ROLLING.value == "rolling"


class TestFailurePolicy:
    """Tests for FailurePolicy enum."""

    def test_policy_values(self):
        """Should have expected policy values."""
        assert FailurePolicy.CONTINUE.value == "continue"
        assert FailurePolicy.STOP.value == "stop"
        assert FailurePolicy.ROLLBACK.value == "rollback"


class TestOrchestrationTask:
    """Tests for OrchestrationTask dataclass."""

    def test_create_task_minimal(self):
        """Should create task with required fields."""
        task = OrchestrationTask(
            name="test-task",
            command="echo hello",
        )
        assert task.name == "test-task"
        assert task.command == "echo hello"
        assert task.timeout == 60.0
        assert task.environment is None

    def test_create_task_full(self):
        """Should create task with all fields."""
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            timeout=300.0,
            environment={"ENV": "production"},
            pre_check="./pre_check.sh",
            post_check="./post_check.sh",
            rollback_command="./rollback.sh",
        )
        assert task.name == "deploy"
        assert task.timeout == 300.0
        assert task.environment["ENV"] == "production"
        assert task.pre_check == "./pre_check.sh"
        assert task.post_check == "./post_check.sh"
        assert task.rollback_command == "./rollback.sh"


class TestDeviceTaskResult:
    """Tests for DeviceTaskResult dataclass."""

    def test_create_result(self):
        """Should create result with fields."""
        result = DeviceTaskResult(
            device_id="server-1",
            success=True,
        )
        assert result.device_id == "server-1"
        assert result.success is True
        assert result.result is None

    def test_create_result_with_command_result(self):
        """Should create result with command result."""
        cmd_result = CommandResult(
            device_id="server-1",
            command="echo ok",
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_ms=100.0,
            success=True,
        )
        result = DeviceTaskResult(
            device_id="server-1",
            success=True,
            result=cmd_result,
        )
        assert result.result is not None
        assert result.result.success is True

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = DeviceTaskResult(
            device_id="server-1",
            success=True,
        )
        d = result.to_dict()
        assert d["device_id"] == "server-1"
        assert d["success"] is True


class TestOrchestrationResult:
    """Tests for OrchestrationResult dataclass."""

    def test_create_result(self):
        """Should create orchestration result."""
        now = datetime.now()
        result = OrchestrationResult(
            task_name="test",
            strategy=RolloutStrategy.ALL_AT_ONCE,
            total_devices=2,
            successful=2,
            failed=0,
            skipped=0,
            rolled_back=0,
            device_results={},
            duration_ms=200.0,
            started_at=now,
            completed_at=now,
        )
        assert result.total_devices == 2
        assert result.successful == 2
        assert result.success is True

    def test_success_property(self):
        """Should compute success from failed count."""
        now = datetime.now()
        result = OrchestrationResult(
            task_name="test",
            strategy=RolloutStrategy.SERIAL,
            total_devices=3,
            successful=2,
            failed=1,
            skipped=0,
            rolled_back=0,
            device_results={},
            duration_ms=100.0,
            started_at=now,
            completed_at=now,
        )
        assert result.success is False

    def test_to_dict(self):
        """Should convert to dictionary."""
        now = datetime.now()
        result = OrchestrationResult(
            task_name="test",
            strategy=RolloutStrategy.CANARY,
            total_devices=2,
            successful=2,
            failed=0,
            skipped=0,
            rolled_back=0,
            device_results={},
            duration_ms=100.0,
            started_at=now,
            completed_at=now,
        )
        d = result.to_dict()
        assert d["task_name"] == "test"
        assert d["strategy"] == "canary"
        assert d["total_devices"] == 2


class TestCoordinator:
    """Tests for Coordinator."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id="server-1",
                hostname="server1.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            ),
            Device(
                id="server-2",
                hostname="server2.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            ),
            Device(
                id="server-3",
                hostname="server3.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            ),
        ]

    @pytest.fixture
    def coordinator(self):
        """Create a coordinator."""
        return Coordinator()

    @pytest.fixture
    def mock_executor(self):
        """Create a mock SSH executor."""
        executor = MagicMock()

        def create_result(device_id, command):
            return CommandResult(
                device_id=device_id,
                command=command,
                exit_code=0,
                stdout="Success",
                stderr="",
                duration_ms=100.0,
                success=True,
            )

        executor.execute = MagicMock(
            side_effect=lambda device, cmd, **kwargs: create_result(device.id, cmd)
        )

        def create_parallel_result(devices, command, **kwargs):
            results = {
                d.id: create_result(d.id, command) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=len(devices),
                failed=0,
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=create_parallel_result)
        return executor

    def test_create_coordinator(self, coordinator):
        """Should create coordinator."""
        assert coordinator is not None
        assert coordinator.max_concurrent == 10

    def test_create_coordinator_with_executor(self, mock_executor):
        """Should create coordinator with executor."""
        coordinator = Coordinator(executor=mock_executor)
        assert coordinator._executor is mock_executor

    def test_orchestrate_all_at_once(
        self, sample_devices, mock_executor
    ):
        """Should orchestrate to all devices at once."""
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="test",
            command="echo hello",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices[:2],
            strategy=RolloutStrategy.ALL_AT_ONCE,
        )

        assert result.strategy == RolloutStrategy.ALL_AT_ONCE
        assert mock_executor.execute_parallel.called

    def test_orchestrate_serial(
        self, sample_devices, mock_executor
    ):
        """Should orchestrate to devices serially."""
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="test",
            command="echo hello",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices[:2],
            strategy=RolloutStrategy.SERIAL,
        )

        assert result.strategy == RolloutStrategy.SERIAL
        # Serial should call execute for each device
        assert mock_executor.execute.call_count == 2

    def test_orchestrate_with_failure_continue(
        self, sample_devices, mock_executor
    ):
        """Should continue on failure with CONTINUE policy."""
        # Make first device fail
        call_count = [0]
        def failing_execute(device, cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return CommandResult(
                    device_id=device.id,
                    command=cmd,
                    exit_code=1,
                    stdout="",
                    stderr="Error",
                    duration_ms=100.0,
                    success=False,
                    error="Command failed",
                )
            return CommandResult(
                device_id=device.id,
                command=cmd,
                exit_code=0,
                stdout="OK",
                stderr="",
                duration_ms=100.0,
                success=True,
            )

        mock_executor.execute = MagicMock(side_effect=failing_execute)
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="test",
            command="echo hello",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices[:2],
            strategy=RolloutStrategy.SERIAL,
            failure_policy=FailurePolicy.CONTINUE,
        )

        # Should continue and run on second device
        assert mock_executor.execute.call_count == 2
        assert result.failed == 1
        assert result.successful == 1

    def test_orchestrate_with_failure_stop(
        self, sample_devices, mock_executor
    ):
        """Should stop on failure with STOP policy."""
        mock_executor.execute = MagicMock(
            return_value=CommandResult(
                device_id="server-1",
                command="echo hello",
                exit_code=1,
                stdout="",
                stderr="Error",
                duration_ms=100.0,
                success=False,
                error="Command failed",
            )
        )
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="test",
            command="echo hello",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices[:3],
            strategy=RolloutStrategy.SERIAL,
            failure_policy=FailurePolicy.STOP,
        )

        # Should stop after first failure
        assert mock_executor.execute.call_count == 1
        assert result.failed == 1

    def test_canary_rollout(
        self, sample_devices, mock_executor
    ):
        """Should perform canary rollout."""
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
        )

        result = coordinator.canary_rollout(
            task=task,
            devices=sample_devices,
            canary_count=1,
            canary_wait_seconds=0,  # Skip wait for testing
        )

        assert result.total_devices == 3
        assert result.strategy == RolloutStrategy.CANARY


class TestCoordinatorSingleton:
    """Tests for global coordinator."""

    def test_get_set_coordinator(self):
        """Should get and set global coordinator."""
        coord = Coordinator()
        set_coordinator(coord)
        assert get_coordinator() is coord

    def test_get_creates_default(self):
        """Should create default coordinator if not set."""
        set_coordinator(None)
        coord = get_coordinator()
        assert coord is not None
        assert isinstance(coord, Coordinator)
