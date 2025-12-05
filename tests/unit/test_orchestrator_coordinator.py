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


class TestCoordinatorRollingStrategy:
    """Tests for rolling rollout strategy."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            )
            for i in range(6)
        ]

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

    def test_orchestrate_rolling(self, sample_devices, mock_executor):
        """Should orchestrate in rolling batches."""
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(
            name="test",
            command="echo hello",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ROLLING,
        )

        assert result.strategy == RolloutStrategy.ROLLING
        # Should call execute_parallel multiple times (batches)
        assert mock_executor.execute_parallel.call_count >= 2

    def test_rolling_stops_on_failure_with_stop_policy(self, sample_devices, mock_executor):
        """Should stop rolling on failure with STOP policy."""
        # Make second batch fail
        call_count = [0]
        def failing_parallel(devices, command, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                # Second batch fails
                results = {
                    d.id: CommandResult(
                        device_id=d.id,
                        command=command,
                        exit_code=1,
                        stdout="",
                        stderr="Error",
                        duration_ms=100.0,
                        success=False,
                    ) for d in devices
                }
            else:
                results = {
                    d.id: CommandResult(
                        device_id=d.id,
                        command=command,
                        exit_code=0,
                        stdout="OK",
                        stderr="",
                        duration_ms=100.0,
                        success=True,
                    ) for d in devices
                }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=sum(1 for r in results.values() if r.success),
                failed=sum(1 for r in results.values() if not r.success),
                duration_ms=150.0,
            )

        mock_executor.execute_parallel = MagicMock(side_effect=failing_parallel)
        coordinator = Coordinator(executor=mock_executor)
        task = OrchestrationTask(name="test", command="echo hello")

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ROLLING,
            failure_policy=FailurePolicy.STOP,
        )

        # Should stop after second batch fails
        assert mock_executor.execute_parallel.call_count == 2
        assert result.failed > 0


class TestCoordinatorPrePostChecks:
    """Tests for pre-check and post-check execution."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        return Device(
            id="server-1",
            hostname="server1.local",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )

    def test_pre_check_failure_skips_command(self, sample_device):
        """Should skip main command if pre-check fails."""
        executor = MagicMock()
        executor.execute = MagicMock(
            return_value=CommandResult(
                device_id="server-1",
                command="./pre_check.sh",
                exit_code=1,
                stdout="",
                stderr="Pre-check failed",
                duration_ms=50.0,
                success=False,
            )
        )

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="test",
            command="./deploy.sh",
            pre_check="./pre_check.sh",
        )

        result = coordinator._execute_on_device(task, sample_device)

        assert result.success is False
        assert result.pre_check_result is not None
        assert result.pre_check_result.success is False
        # Main command should not be called since pre-check failed
        assert executor.execute.call_count == 1

    def test_post_check_failure_marks_task_failed(self, sample_device):
        """Should mark task failed if post-check fails."""
        call_count = [0]
        def execute_with_post_fail(device, cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Main command succeeds
                return CommandResult(
                    device_id=device.id,
                    command=cmd,
                    exit_code=0,
                    stdout="OK",
                    stderr="",
                    duration_ms=100.0,
                    success=True,
                )
            else:
                # Post-check fails
                return CommandResult(
                    device_id=device.id,
                    command=cmd,
                    exit_code=1,
                    stdout="",
                    stderr="Post-check failed",
                    duration_ms=50.0,
                    success=False,
                )

        executor = MagicMock()
        executor.execute = MagicMock(side_effect=execute_with_post_fail)

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="test",
            command="./deploy.sh",
            post_check="./post_check.sh",
        )

        result = coordinator._execute_on_device(task, sample_device)

        assert result.success is False
        assert result.result is not None
        assert result.result.success is True  # Main command succeeded
        assert result.post_check_result is not None
        assert result.post_check_result.success is False


class TestCoordinatorRollback:
    """Tests for rollback functionality."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            )
            for i in range(3)
        ]

    def test_rollback_devices(self, sample_devices):
        """Should execute rollback command on devices."""
        executor = MagicMock()
        executor.execute = MagicMock(
            return_value=CommandResult(
                device_id="test",
                command="./rollback.sh",
                exit_code=0,
                stdout="Rolled back",
                stderr="",
                duration_ms=100.0,
                success=True,
            )
        )

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            rollback_command="./rollback.sh",
        )

        device_results = {
            sample_devices[0].id: DeviceTaskResult(
                device_id=sample_devices[0].id,
                success=True,
            ),
            sample_devices[1].id: DeviceTaskResult(
                device_id=sample_devices[1].id,
                success=True,
            ),
        }

        coordinator._rollback_devices(task, sample_devices[:2], device_results)

        # Should call rollback for each device in results
        assert executor.execute.call_count == 2
        assert device_results[sample_devices[0].id].rolled_back is True
        assert device_results[sample_devices[1].id].rolled_back is True

    def test_rollback_skipped_without_command(self, sample_devices):
        """Should skip rollback if no rollback_command."""
        executor = MagicMock()
        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            rollback_command=None,  # No rollback command
        )

        device_results = {
            sample_devices[0].id: DeviceTaskResult(
                device_id=sample_devices[0].id,
                success=True,
            ),
        }

        coordinator._rollback_devices(task, sample_devices[:1], device_results)

        # Should not call executor
        assert executor.execute.call_count == 0


class TestCoordinatorCanaryFailures:
    """Tests for canary rollout failure handling."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            )
            for i in range(5)
        ]

    def test_canary_failure_stops_rollout(self, sample_devices):
        """Should stop rollout if canary fails."""
        executor = MagicMock()

        def failing_parallel(devices, command, **kwargs):
            # All canaries fail
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=1,
                    stdout="",
                    stderr="Canary failed",
                    duration_ms=100.0,
                    success=False,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=0,
                failed=len(devices),
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=failing_parallel)
        executor.execute = MagicMock()

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(name="deploy", command="./deploy.sh")

        result = coordinator.canary_rollout(
            task=task,
            devices=sample_devices,
            canary_count=2,
            canary_wait_seconds=0,
        )

        # Should only run on canaries, then stop
        assert executor.execute_parallel.call_count == 1
        assert result.failed == 2
        assert result.skipped == 3
        assert "Canary failures" in result.error

    def test_canary_failure_triggers_rollback(self, sample_devices):
        """Should rollback canaries on failure with ROLLBACK policy."""
        executor = MagicMock()

        def failing_parallel(devices, command, **kwargs):
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=1,
                    stdout="",
                    stderr="Failed",
                    duration_ms=100.0,
                    success=False,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=0,
                failed=len(devices),
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=failing_parallel)
        executor.execute = MagicMock(
            return_value=CommandResult(
                device_id="test",
                command="./rollback.sh",
                exit_code=0,
                stdout="Rolled back",
                stderr="",
                duration_ms=50.0,
                success=True,
            )
        )

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            rollback_command="./rollback.sh",
        )

        result = coordinator.canary_rollout(
            task=task,
            devices=sample_devices,
            canary_count=2,
            canary_wait_seconds=0,
            failure_policy=FailurePolicy.ROLLBACK,
        )

        # Should have called rollback for canary devices
        assert executor.execute.call_count == 2
        assert result.rolled_back == 2

    def test_canary_with_too_few_devices(self, sample_devices):
        """Should fall back to ALL_AT_ONCE if not enough devices."""
        executor = MagicMock()

        def parallel_success(devices, command, **kwargs):
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=0,
                    stdout="OK",
                    stderr="",
                    duration_ms=100.0,
                    success=True,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=len(devices),
                failed=0,
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=parallel_success)

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(name="test", command="echo hello")

        # Only 2 devices, but canary_count is 3
        result = coordinator.canary_rollout(
            task=task,
            devices=sample_devices[:2],
            canary_count=3,
        )

        # Should fall back to ALL_AT_ONCE
        assert result.strategy == RolloutStrategy.ALL_AT_ONCE


class TestCoordinatorProgressCallback:
    """Tests for progress callback functionality."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            )
            for i in range(3)
        ]

    def test_progress_callback_called(self, sample_devices):
        """Should call progress callback for each device."""
        executor = MagicMock()

        def parallel_success(devices, command, **kwargs):
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=0,
                    stdout="OK",
                    stderr="",
                    duration_ms=100.0,
                    success=True,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=len(devices),
                failed=0,
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=parallel_success)

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(name="test", command="echo hello")

        callback = MagicMock()
        coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ALL_AT_ONCE,
            progress_callback=callback,
        )

        # Callback should be called for each device
        assert callback.call_count == 3


class TestCoordinatorErrorHandling:
    """Tests for error handling in coordinator."""

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
        ]

    def test_orchestrate_handles_exception(self, sample_devices):
        """Should handle exceptions during orchestration."""
        executor = MagicMock()
        executor.execute_parallel = MagicMock(
            side_effect=RuntimeError("Connection failed")
        )

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(name="test", command="echo hello")

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ALL_AT_ONCE,
        )

        assert result.success is False
        assert result.failed == 1
        assert "Connection failed" in result.error

    def test_unsupported_strategy_raises_error(self, sample_devices):
        """Should handle unsupported strategy."""
        executor = MagicMock()
        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(name="test", command="echo hello")

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.BLUE_GREEN,  # Not implemented
        )

        assert result.success is False
        assert "not implemented" in result.error.lower()


class TestCoordinatorPostCheckInParallel:
    """Tests for post-check in parallel execution."""

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
            )
            for i in range(2)
        ]

    def test_post_check_run_after_parallel_success(self, sample_devices):
        """Should run post-check after successful parallel execution."""
        executor = MagicMock()

        def parallel_success(devices, command, **kwargs):
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=0,
                    stdout="OK",
                    stderr="",
                    duration_ms=100.0,
                    success=True,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=len(devices),
                failed=0,
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=parallel_success)
        executor.execute = MagicMock(
            return_value=CommandResult(
                device_id="test",
                command="./post_check.sh",
                exit_code=0,
                stdout="Post-check OK",
                stderr="",
                duration_ms=50.0,
                success=True,
            )
        )

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            post_check="./post_check.sh",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ALL_AT_ONCE,
        )

        # Post-check should be called for each device
        assert executor.execute.call_count == 2
        assert result.successful == 2

    def test_post_check_failure_marks_device_failed(self, sample_devices):
        """Should mark device failed if post-check fails."""
        executor = MagicMock()

        def parallel_success(devices, command, **kwargs):
            results = {
                d.id: CommandResult(
                    device_id=d.id,
                    command=command,
                    exit_code=0,
                    stdout="OK",
                    stderr="",
                    duration_ms=100.0,
                    success=True,
                ) for d in devices
            }
            return ParallelResult(
                results=results,
                total_devices=len(devices),
                successful=len(devices),
                failed=0,
                duration_ms=150.0,
            )

        executor.execute_parallel = MagicMock(side_effect=parallel_success)

        # Post-check fails for first device
        call_count = [0]
        def post_check(device, cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return CommandResult(
                    device_id=device.id,
                    command=cmd,
                    exit_code=1,
                    stdout="",
                    stderr="Post-check failed",
                    duration_ms=50.0,
                    success=False,
                )
            return CommandResult(
                device_id=device.id,
                command=cmd,
                exit_code=0,
                stdout="OK",
                stderr="",
                duration_ms=50.0,
                success=True,
            )

        executor.execute = MagicMock(side_effect=post_check)

        coordinator = Coordinator(executor=executor)
        task = OrchestrationTask(
            name="deploy",
            command="./deploy.sh",
            post_check="./post_check.sh",
        )

        result = coordinator.orchestrate(
            task=task,
            devices=sample_devices,
            strategy=RolloutStrategy.ALL_AT_ONCE,
        )

        # One device should fail due to post-check
        assert result.failed == 1
        assert result.successful == 1
