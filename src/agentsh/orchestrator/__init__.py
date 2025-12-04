"""Multi-device orchestration for AgentSH.

This module provides fleet management capabilities including:
- Device inventory management
- SSH-based remote execution
- Orchestration patterns (parallel, canary, rolling)
- MCP server for external integration
"""

from agentsh.orchestrator.coordinator import (
    Coordinator,
    DeviceTaskResult,
    FailurePolicy,
    OrchestrationResult,
    OrchestrationTask,
    RolloutStrategy,
    get_coordinator,
    orchestrate_async,
    set_coordinator,
)
from agentsh.orchestrator.devices import (
    ConnectionConfig,
    ConnectionMethod,
    Device,
    DeviceInventory,
    DeviceStatus,
    DeviceType,
    SafetyConstraints,
    create_device,
    get_device_inventory,
    set_device_inventory,
)
from agentsh.orchestrator.ssh import (
    CommandResult,
    ParallelResult,
    SSHConnection,
    SSHConnectionPool,
    SSHCredentials,
    SSHExecutor,
    get_ssh_executor,
    set_ssh_executor,
)

__all__ = [
    # Devices
    "DeviceType",
    "DeviceStatus",
    "ConnectionMethod",
    "ConnectionConfig",
    "SafetyConstraints",
    "Device",
    "DeviceInventory",
    "create_device",
    "get_device_inventory",
    "set_device_inventory",
    # SSH
    "CommandResult",
    "SSHCredentials",
    "SSHConnection",
    "SSHConnectionPool",
    "SSHExecutor",
    "ParallelResult",
    "get_ssh_executor",
    "set_ssh_executor",
    # Coordinator
    "RolloutStrategy",
    "FailurePolicy",
    "OrchestrationTask",
    "DeviceTaskResult",
    "OrchestrationResult",
    "Coordinator",
    "get_coordinator",
    "set_coordinator",
    "orchestrate_async",
]
