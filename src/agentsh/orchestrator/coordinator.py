"""Orchestration coordinator for fleet-wide operations.

Provides high-level orchestration patterns including parallel execution,
canary rollouts, and failure handling across device fleets.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.orchestrator.devices import Device, DeviceInventory, DeviceStatus, get_device_inventory
from agentsh.orchestrator.ssh import CommandResult, ParallelResult, SSHExecutor, get_ssh_executor
from agentsh.telemetry.events import EventType, emit_event
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class RolloutStrategy(str, Enum):
    """Strategies for rolling out operations to fleet."""

    ALL_AT_ONCE = "all_at_once"
    SERIAL = "serial"
    CANARY = "canary"
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"


class FailurePolicy(str, Enum):
    """Policies for handling failures during orchestration."""

    CONTINUE = "continue"  # Continue on failure
    STOP = "stop"  # Stop on first failure
    ROLLBACK = "rollback"  # Rollback on failure


@dataclass
class OrchestrationTask:
    """A task to execute on a fleet of devices.

    Attributes:
        name: Task name
        command: Command to execute
        timeout: Command timeout per device
        environment: Environment variables to set
        pre_check: Optional pre-execution check command
        post_check: Optional post-execution verification command
        rollback_command: Command to run on failure/rollback
    """

    name: str
    command: str
    timeout: float = 60.0
    environment: Optional[dict[str, str]] = None
    pre_check: Optional[str] = None
    post_check: Optional[str] = None
    rollback_command: Optional[str] = None


@dataclass
class DeviceTaskResult:
    """Result of a task on a single device.

    Attributes:
        device_id: Device identifier
        success: Whether task succeeded
        result: Command result
        pre_check_result: Pre-check result if run
        post_check_result: Post-check result if run
        rolled_back: Whether rollback was executed
        rollback_result: Rollback result if executed
    """

    device_id: str
    success: bool
    result: Optional[CommandResult] = None
    pre_check_result: Optional[CommandResult] = None
    post_check_result: Optional[CommandResult] = None
    rolled_back: bool = False
    rollback_result: Optional[CommandResult] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "success": self.success,
            "result": self.result.to_dict() if self.result else None,
            "pre_check_result": self.pre_check_result.to_dict() if self.pre_check_result else None,
            "post_check_result": self.post_check_result.to_dict() if self.post_check_result else None,
            "rolled_back": self.rolled_back,
            "rollback_result": self.rollback_result.to_dict() if self.rollback_result else None,
        }


@dataclass
class OrchestrationResult:
    """Result of an orchestration operation.

    Attributes:
        task_name: Name of the task
        strategy: Rollout strategy used
        total_devices: Number of devices targeted
        successful: Number of successful executions
        failed: Number of failed executions
        skipped: Number of skipped devices
        rolled_back: Number of devices rolled back
        device_results: Results per device
        duration_ms: Total duration in milliseconds
        started_at: When orchestration started
        completed_at: When orchestration completed
        error: Overall error message if applicable
    """

    task_name: str
    strategy: RolloutStrategy
    total_devices: int
    successful: int
    failed: int
    skipped: int
    rolled_back: int
    device_results: dict[str, DeviceTaskResult]
    duration_ms: float
    started_at: datetime
    completed_at: datetime
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if orchestration was successful."""
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_name": self.task_name,
            "strategy": self.strategy.value,
            "total_devices": self.total_devices,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "rolled_back": self.rolled_back,
            "device_results": {k: v.to_dict() for k, v in self.device_results.items()},
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "error": self.error,
        }


class Coordinator:
    """Coordinates fleet-wide operations.

    Provides orchestration patterns for executing tasks across
    multiple devices with various rollout strategies.

    Example:
        coordinator = Coordinator()

        # Execute on all devices at once
        result = coordinator.orchestrate(
            task=OrchestrationTask(name="update", command="apt update"),
            devices=devices,
            strategy=RolloutStrategy.ALL_AT_ONCE,
        )

        # Canary rollout
        result = coordinator.canary_rollout(
            task=OrchestrationTask(name="deploy", command="deploy.sh"),
            devices=devices,
            canary_count=2,
        )
    """

    def __init__(
        self,
        executor: Optional[SSHExecutor] = None,
        inventory: Optional[DeviceInventory] = None,
        max_concurrent: int = 10,
    ) -> None:
        """Initialize coordinator.

        Args:
            executor: SSH executor (uses global if not provided)
            inventory: Device inventory (uses global if not provided)
            max_concurrent: Maximum concurrent executions
        """
        self._executor = executor
        self._inventory = inventory
        self.max_concurrent = max_concurrent

        logger.debug("Coordinator initialized", max_concurrent=max_concurrent)

    @property
    def executor(self) -> SSHExecutor:
        """Get SSH executor."""
        return self._executor or get_ssh_executor()

    @property
    def inventory(self) -> DeviceInventory:
        """Get device inventory."""
        return self._inventory or get_device_inventory()

    def orchestrate(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        strategy: RolloutStrategy = RolloutStrategy.ALL_AT_ONCE,
        failure_policy: FailurePolicy = FailurePolicy.CONTINUE,
        progress_callback: Optional[Callable[[str, DeviceTaskResult], None]] = None,
    ) -> OrchestrationResult:
        """Execute a task across multiple devices.

        Args:
            task: Task to execute
            devices: Target devices
            strategy: Rollout strategy
            failure_policy: How to handle failures
            progress_callback: Called after each device completes

        Returns:
            OrchestrationResult with all device results
        """
        started_at = datetime.now()
        start_time = time.perf_counter()

        emit_event(
            EventType.WORKFLOW_STARTED,
            data={
                "task_name": task.name,
                "strategy": strategy.value,
                "device_count": len(devices),
            },
        )

        logger.info(
            "Starting orchestration",
            task=task.name,
            strategy=strategy.value,
            devices=len(devices),
        )

        try:
            if strategy == RolloutStrategy.ALL_AT_ONCE:
                device_results = self._execute_all_at_once(
                    task, devices, failure_policy, progress_callback
                )
            elif strategy == RolloutStrategy.SERIAL:
                device_results = self._execute_serial(
                    task, devices, failure_policy, progress_callback
                )
            elif strategy == RolloutStrategy.ROLLING:
                device_results = self._execute_rolling(
                    task, devices, failure_policy, progress_callback
                )
            else:
                raise ValueError(f"Strategy {strategy} not implemented")

        except Exception as e:
            logger.error("Orchestration failed", task=task.name, error=str(e))
            return OrchestrationResult(
                task_name=task.name,
                strategy=strategy,
                total_devices=len(devices),
                successful=0,
                failed=len(devices),
                skipped=0,
                rolled_back=0,
                device_results={},
                duration_ms=(time.perf_counter() - start_time) * 1000,
                started_at=started_at,
                completed_at=datetime.now(),
                error=str(e),
            )

        successful = sum(1 for r in device_results.values() if r.success)
        failed = sum(1 for r in device_results.values() if not r.success)
        skipped = len(devices) - len(device_results)
        rolled_back = sum(1 for r in device_results.values() if r.rolled_back)

        duration_ms = (time.perf_counter() - start_time) * 1000

        emit_event(
            EventType.WORKFLOW_COMPLETED,
            data={
                "task_name": task.name,
                "successful": successful,
                "failed": failed,
                "duration_ms": duration_ms,
            },
        )

        logger.info(
            "Orchestration completed",
            task=task.name,
            successful=successful,
            failed=failed,
            duration_ms=duration_ms,
        )

        return OrchestrationResult(
            task_name=task.name,
            strategy=strategy,
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            skipped=skipped,
            rolled_back=rolled_back,
            device_results=device_results,
            duration_ms=duration_ms,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    def canary_rollout(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        canary_count: int = 1,
        canary_wait_seconds: float = 30.0,
        failure_policy: FailurePolicy = FailurePolicy.STOP,
        progress_callback: Optional[Callable[[str, DeviceTaskResult], None]] = None,
    ) -> OrchestrationResult:
        """Execute task with canary rollout strategy.

        First executes on a small subset (canaries), then proceeds
        to the rest if canaries succeed.

        Args:
            task: Task to execute
            devices: Target devices
            canary_count: Number of canary devices
            canary_wait_seconds: Time to wait after canary before proceeding
            failure_policy: How to handle failures
            progress_callback: Called after each device completes

        Returns:
            OrchestrationResult with all device results
        """
        started_at = datetime.now()
        start_time = time.perf_counter()

        if len(devices) <= canary_count:
            # Not enough devices for canary, just do all
            return self.orchestrate(
                task, devices, RolloutStrategy.ALL_AT_ONCE, failure_policy, progress_callback
            )

        emit_event(
            EventType.WORKFLOW_STARTED,
            data={
                "task_name": task.name,
                "strategy": "canary",
                "device_count": len(devices),
                "canary_count": canary_count,
            },
        )

        logger.info(
            "Starting canary rollout",
            task=task.name,
            devices=len(devices),
            canary_count=canary_count,
        )

        # Split into canary and rest
        canary_devices = devices[:canary_count]
        remaining_devices = devices[canary_count:]
        device_results: dict[str, DeviceTaskResult] = {}

        # Execute on canaries first
        logger.info("Executing on canary devices", count=len(canary_devices))
        canary_results = self._execute_all_at_once(
            task, canary_devices, failure_policy, progress_callback
        )
        device_results.update(canary_results)

        # Check canary success
        canary_failures = sum(1 for r in canary_results.values() if not r.success)
        if canary_failures > 0:
            logger.warning(
                "Canary failures detected, stopping rollout",
                failures=canary_failures,
            )

            if failure_policy == FailurePolicy.ROLLBACK:
                self._rollback_devices(task, canary_devices, device_results)

            return OrchestrationResult(
                task_name=task.name,
                strategy=RolloutStrategy.CANARY,
                total_devices=len(devices),
                successful=canary_count - canary_failures,
                failed=canary_failures,
                skipped=len(remaining_devices),
                rolled_back=sum(1 for r in device_results.values() if r.rolled_back),
                device_results=device_results,
                duration_ms=(time.perf_counter() - start_time) * 1000,
                started_at=started_at,
                completed_at=datetime.now(),
                error="Canary failures, rollout stopped",
            )

        # Wait before proceeding
        logger.info("Canary successful, waiting before proceeding", wait_seconds=canary_wait_seconds)
        time.sleep(canary_wait_seconds)

        # Execute on remaining devices
        logger.info("Executing on remaining devices", count=len(remaining_devices))
        remaining_results = self._execute_all_at_once(
            task, remaining_devices, failure_policy, progress_callback
        )
        device_results.update(remaining_results)

        successful = sum(1 for r in device_results.values() if r.success)
        failed = sum(1 for r in device_results.values() if not r.success)
        rolled_back = sum(1 for r in device_results.values() if r.rolled_back)

        duration_ms = (time.perf_counter() - start_time) * 1000

        emit_event(
            EventType.WORKFLOW_COMPLETED,
            data={
                "task_name": task.name,
                "strategy": "canary",
                "successful": successful,
                "failed": failed,
                "duration_ms": duration_ms,
            },
        )

        return OrchestrationResult(
            task_name=task.name,
            strategy=RolloutStrategy.CANARY,
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            skipped=0,
            rolled_back=rolled_back,
            device_results=device_results,
            duration_ms=duration_ms,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    def _execute_all_at_once(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        failure_policy: FailurePolicy,
        progress_callback: Optional[Callable[[str, DeviceTaskResult], None]],
    ) -> dict[str, DeviceTaskResult]:
        """Execute on all devices concurrently."""
        results = self.executor.execute_parallel(
            devices,
            task.command,
            timeout=task.timeout,
            max_concurrent=self.max_concurrent,
            environment=task.environment,
        )

        device_results: dict[str, DeviceTaskResult] = {}
        for device_id, result in results.results.items():
            task_result = DeviceTaskResult(
                device_id=device_id,
                success=result.success,
                result=result,
            )

            # Run post-check if configured and command succeeded
            if result.success and task.post_check:
                device = next((d for d in devices if d.id == device_id), None)
                if device:
                    post_result = self.executor.execute(device, task.post_check, timeout=30)
                    task_result.post_check_result = post_result
                    if not post_result.success:
                        task_result.success = False

            device_results[device_id] = task_result

            if progress_callback:
                progress_callback(device_id, task_result)

        return device_results

    def _execute_serial(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        failure_policy: FailurePolicy,
        progress_callback: Optional[Callable[[str, DeviceTaskResult], None]],
    ) -> dict[str, DeviceTaskResult]:
        """Execute on devices one at a time."""
        device_results: dict[str, DeviceTaskResult] = {}

        for device in devices:
            task_result = self._execute_on_device(task, device)
            device_results[device.id] = task_result

            if progress_callback:
                progress_callback(device.id, task_result)

            if not task_result.success and failure_policy == FailurePolicy.STOP:
                logger.warning("Stopping due to failure", device_id=device.id)
                break

        return device_results

    def _execute_rolling(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        failure_policy: FailurePolicy,
        progress_callback: Optional[Callable[[str, DeviceTaskResult], None]],
        batch_size: int = 3,
    ) -> dict[str, DeviceTaskResult]:
        """Execute in rolling batches."""
        device_results: dict[str, DeviceTaskResult] = {}

        for i in range(0, len(devices), batch_size):
            batch = devices[i : i + batch_size]
            batch_results = self._execute_all_at_once(
                task, batch, failure_policy, progress_callback
            )
            device_results.update(batch_results)

            # Check for failures
            batch_failures = sum(1 for r in batch_results.values() if not r.success)
            if batch_failures > 0 and failure_policy == FailurePolicy.STOP:
                logger.warning("Stopping due to batch failures", failures=batch_failures)
                break

        return device_results

    def _execute_on_device(
        self,
        task: OrchestrationTask,
        device: Device,
    ) -> DeviceTaskResult:
        """Execute task on a single device with pre/post checks."""
        task_result = DeviceTaskResult(device_id=device.id, success=False)

        # Pre-check if configured
        if task.pre_check:
            pre_result = self.executor.execute(device, task.pre_check, timeout=30)
            task_result.pre_check_result = pre_result
            if not pre_result.success:
                logger.warning("Pre-check failed", device_id=device.id)
                return task_result

        # Execute main command
        result = self.executor.execute(
            device,
            task.command,
            timeout=task.timeout,
            environment=task.environment,
        )
        task_result.result = result
        task_result.success = result.success

        # Post-check if configured and command succeeded
        if result.success and task.post_check:
            post_result = self.executor.execute(device, task.post_check, timeout=30)
            task_result.post_check_result = post_result
            if not post_result.success:
                task_result.success = False
                logger.warning("Post-check failed", device_id=device.id)

        return task_result

    def _rollback_devices(
        self,
        task: OrchestrationTask,
        devices: list[Device],
        device_results: dict[str, DeviceTaskResult],
    ) -> None:
        """Execute rollback command on devices."""
        if not task.rollback_command:
            return

        logger.info("Executing rollback", devices=len(devices))

        for device in devices:
            if device.id not in device_results:
                continue

            result = self.executor.execute(device, task.rollback_command, timeout=task.timeout)
            device_results[device.id].rolled_back = True
            device_results[device.id].rollback_result = result


async def orchestrate_async(
    task: OrchestrationTask,
    devices: list[Device],
    strategy: RolloutStrategy = RolloutStrategy.ALL_AT_ONCE,
    failure_policy: FailurePolicy = FailurePolicy.CONTINUE,
    max_concurrent: int = 10,
) -> OrchestrationResult:
    """Async convenience function for orchestration.

    Args:
        task: Task to execute
        devices: Target devices
        strategy: Rollout strategy
        failure_policy: How to handle failures
        max_concurrent: Maximum concurrent executions

    Returns:
        OrchestrationResult
    """
    coordinator = Coordinator(max_concurrent=max_concurrent)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: coordinator.orchestrate(task, devices, strategy, failure_policy),
    )


# Global coordinator instance
_coordinator: Optional[Coordinator] = None


def get_coordinator() -> Coordinator:
    """Get the global coordinator.

    Returns:
        Global Coordinator singleton
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = Coordinator()
    return _coordinator


def set_coordinator(coordinator: Coordinator) -> None:
    """Set the global coordinator.

    Args:
        coordinator: Coordinator to use globally
    """
    global _coordinator
    _coordinator = coordinator
