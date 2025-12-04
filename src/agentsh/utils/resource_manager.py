"""Resource management and cleanup utilities.

Provides mechanisms to:
- Track resource usage (memory, file handles, connections)
- Clean up resources when limits are approached
- Register cleanup handlers
- Gracefully degrade when resources are exhausted
"""

import atexit
import gc
import os
import resource
import signal
import sys
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class ResourceType(str, Enum):
    """Types of system resources."""

    MEMORY = "memory"
    FILE_HANDLES = "file_handles"
    CONNECTIONS = "connections"
    THREADS = "threads"
    PROCESSES = "processes"


class ResourceStatus(str, Enum):
    """Resource availability status."""

    HEALTHY = "healthy"  # Resources available
    WARNING = "warning"  # Resources running low
    CRITICAL = "critical"  # Resources nearly exhausted
    EXHAUSTED = "exhausted"  # Resources exhausted


@dataclass
class ResourceLimits:
    """Resource limit configuration."""

    # Memory limits (bytes)
    memory_warning_threshold: float = 0.7  # 70% of available
    memory_critical_threshold: float = 0.85  # 85% of available
    memory_max_bytes: Optional[int] = None  # Hard limit

    # File handle limits
    file_handles_warning_threshold: float = 0.7
    file_handles_critical_threshold: float = 0.85
    file_handles_max: Optional[int] = None

    # Connection limits
    connections_warning_threshold: int = 100
    connections_critical_threshold: int = 200
    connections_max: int = 500

    # Thread limits
    threads_warning_threshold: int = 50
    threads_critical_threshold: int = 100
    threads_max: int = 200


@dataclass
class ResourceUsage:
    """Current resource usage snapshot."""

    memory_used_bytes: int = 0
    memory_available_bytes: int = 0
    memory_percent: float = 0.0

    file_handles_used: int = 0
    file_handles_max: int = 0
    file_handles_percent: float = 0.0

    active_connections: int = 0
    active_threads: int = 0

    timestamp: datetime = field(default_factory=datetime.now)

    def get_status(
        self, resource_type: ResourceType, limits: ResourceLimits
    ) -> ResourceStatus:
        """Get status for a specific resource type.

        Args:
            resource_type: Type of resource to check
            limits: Resource limits configuration

        Returns:
            Current status of the resource
        """
        if resource_type == ResourceType.MEMORY:
            if self.memory_percent >= limits.memory_critical_threshold:
                return ResourceStatus.CRITICAL
            elif self.memory_percent >= limits.memory_warning_threshold:
                return ResourceStatus.WARNING
            return ResourceStatus.HEALTHY

        elif resource_type == ResourceType.FILE_HANDLES:
            if self.file_handles_percent >= limits.file_handles_critical_threshold:
                return ResourceStatus.CRITICAL
            elif self.file_handles_percent >= limits.file_handles_warning_threshold:
                return ResourceStatus.WARNING
            return ResourceStatus.HEALTHY

        elif resource_type == ResourceType.CONNECTIONS:
            if self.active_connections >= limits.connections_critical_threshold:
                return ResourceStatus.CRITICAL
            elif self.active_connections >= limits.connections_warning_threshold:
                return ResourceStatus.WARNING
            return ResourceStatus.HEALTHY

        elif resource_type == ResourceType.THREADS:
            if self.active_threads >= limits.threads_critical_threshold:
                return ResourceStatus.CRITICAL
            elif self.active_threads >= limits.threads_warning_threshold:
                return ResourceStatus.WARNING
            return ResourceStatus.HEALTHY

        return ResourceStatus.HEALTHY


class CleanupHandler:
    """Handler for resource cleanup."""

    def __init__(
        self,
        name: str,
        callback: Callable[[], None],
        resource_type: ResourceType,
        priority: int = 50,
    ) -> None:
        """Initialize cleanup handler.

        Args:
            name: Handler name for logging
            callback: Cleanup function to call
            resource_type: Type of resource this cleans
            priority: Execution priority (lower = earlier)
        """
        self.name = name
        self.callback = callback
        self.resource_type = resource_type
        self.priority = priority
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0

    def execute(self) -> bool:
        """Execute the cleanup handler.

        Returns:
            True if cleanup succeeded, False otherwise
        """
        try:
            self.callback()
            self.last_run = datetime.now()
            self.run_count += 1
            logger.debug(
                "Cleanup handler executed",
                handler=self.name,
                resource_type=self.resource_type.value,
            )
            return True
        except Exception as e:
            self.error_count += 1
            logger.error(
                "Cleanup handler failed",
                handler=self.name,
                error=str(e),
            )
            return False


class ResourceManager:
    """Central manager for system resources.

    Tracks resource usage and coordinates cleanup when limits
    are approached. Provides graceful degradation under load.

    Example:
        manager = ResourceManager()

        # Register cleanup handlers
        manager.register_cleanup(
            "cache_cleanup",
            lambda: cache.clear(),
            ResourceType.MEMORY,
        )

        # Check resources periodically
        usage = manager.get_usage()
        if manager.needs_cleanup(ResourceType.MEMORY):
            manager.run_cleanup(ResourceType.MEMORY)
    """

    def __init__(self, limits: Optional[ResourceLimits] = None) -> None:
        """Initialize resource manager.

        Args:
            limits: Resource limit configuration
        """
        self.limits = limits or ResourceLimits()
        self._handlers: list[CleanupHandler] = []
        self._tracked_objects: weakref.WeakSet[Any] = weakref.WeakSet()
        self._lock = threading.Lock()
        self._shutdown = False

        # Register atexit handler
        atexit.register(self._atexit_cleanup)

    def register_cleanup(
        self,
        name: str,
        callback: Callable[[], None],
        resource_type: ResourceType,
        priority: int = 50,
    ) -> CleanupHandler:
        """Register a cleanup handler.

        Args:
            name: Handler name
            callback: Cleanup function
            resource_type: Resource type this cleans
            priority: Execution priority (0-100, lower = earlier)

        Returns:
            Registered CleanupHandler
        """
        handler = CleanupHandler(name, callback, resource_type, priority)
        with self._lock:
            self._handlers.append(handler)
            # Keep sorted by priority
            self._handlers.sort(key=lambda h: h.priority)

        logger.debug(
            "Registered cleanup handler",
            handler=name,
            resource_type=resource_type.value,
            priority=priority,
        )
        return handler

    def unregister_cleanup(self, name: str) -> bool:
        """Unregister a cleanup handler.

        Args:
            name: Handler name to remove

        Returns:
            True if handler was removed
        """
        with self._lock:
            before = len(self._handlers)
            self._handlers = [h for h in self._handlers if h.name != name]
            return len(self._handlers) < before

    def track_object(self, obj: Any) -> None:
        """Track an object for resource management.

        Args:
            obj: Object to track (weak reference)
        """
        self._tracked_objects.add(obj)

    def get_usage(self) -> ResourceUsage:
        """Get current resource usage.

        Returns:
            Current resource usage snapshot
        """
        usage = ResourceUsage()

        # Memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            usage.memory_used_bytes = memory_info.rss
            usage.memory_available_bytes = psutil.virtual_memory().available
            total = usage.memory_used_bytes + usage.memory_available_bytes
            usage.memory_percent = usage.memory_used_bytes / total if total > 0 else 0
        except ImportError:
            # Fall back to resource module
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            usage.memory_used_bytes = rusage.ru_maxrss * 1024  # KB to bytes on macOS
            usage.memory_percent = 0.0  # Can't determine without psutil

        # File handles
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            # Count open file descriptors
            fd_count = len(os.listdir(f"/proc/{os.getpid()}/fd"))
            usage.file_handles_used = fd_count
            usage.file_handles_max = soft
            usage.file_handles_percent = fd_count / soft if soft > 0 else 0
        except (OSError, FileNotFoundError):
            # Not on Linux, try different approach
            try:
                import subprocess
                result = subprocess.run(
                    ["lsof", "-p", str(os.getpid())],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Count lines (minus header)
                lines = result.stdout.strip().split("\n")
                usage.file_handles_used = max(0, len(lines) - 1)
                soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
                usage.file_handles_max = soft
                usage.file_handles_percent = (
                    usage.file_handles_used / soft if soft > 0 else 0
                )
            except Exception:
                pass

        # Thread count
        usage.active_threads = threading.active_count()

        # Connection count (tracked objects)
        usage.active_connections = len(self._tracked_objects)

        return usage

    def needs_cleanup(self, resource_type: Optional[ResourceType] = None) -> bool:
        """Check if cleanup is needed.

        Args:
            resource_type: Specific resource to check, or None for any

        Returns:
            True if cleanup is recommended
        """
        usage = self.get_usage()

        if resource_type is None:
            # Check all resource types
            for rt in ResourceType:
                status = usage.get_status(rt, self.limits)
                if status in (ResourceStatus.WARNING, ResourceStatus.CRITICAL):
                    return True
            return False

        status = usage.get_status(resource_type, self.limits)
        return status in (ResourceStatus.WARNING, ResourceStatus.CRITICAL)

    def run_cleanup(
        self,
        resource_type: Optional[ResourceType] = None,
        force: bool = False,
    ) -> int:
        """Run cleanup handlers.

        Args:
            resource_type: Specific resource to clean, or None for all
            force: Run even if not needed

        Returns:
            Number of handlers executed
        """
        if not force and not self.needs_cleanup(resource_type):
            return 0

        count = 0
        with self._lock:
            for handler in self._handlers:
                if resource_type is None or handler.resource_type == resource_type:
                    if handler.execute():
                        count += 1

        # Force garbage collection after cleanup
        gc.collect()

        logger.info(
            "Cleanup completed",
            handlers_run=count,
            resource_type=resource_type.value if resource_type else "all",
        )
        return count

    def get_status(self) -> dict[ResourceType, ResourceStatus]:
        """Get status for all resource types.

        Returns:
            Dict mapping resource type to status
        """
        usage = self.get_usage()
        return {rt: usage.get_status(rt, self.limits) for rt in ResourceType}

    def is_healthy(self) -> bool:
        """Check if all resources are healthy.

        Returns:
            True if all resources are healthy
        """
        status = self.get_status()
        return all(s == ResourceStatus.HEALTHY for s in status.values())

    def shutdown(self) -> None:
        """Shutdown the resource manager and cleanup."""
        if self._shutdown:
            return

        self._shutdown = True
        logger.info("Resource manager shutting down")

        # Run all cleanup handlers
        self.run_cleanup(force=True)

        # Clear tracked objects
        self._tracked_objects = weakref.WeakSet()

    def _atexit_cleanup(self) -> None:
        """Cleanup handler for atexit."""
        self.shutdown()


# Global resource manager
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get or create the global resource manager.

    Returns:
        Global ResourceManager instance
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def register_cleanup(
    name: str,
    callback: Callable[[], None],
    resource_type: ResourceType = ResourceType.MEMORY,
    priority: int = 50,
) -> CleanupHandler:
    """Register a cleanup handler with the global manager.

    Args:
        name: Handler name
        callback: Cleanup function
        resource_type: Resource type
        priority: Execution priority

    Returns:
        Registered CleanupHandler
    """
    return get_resource_manager().register_cleanup(
        name, callback, resource_type, priority
    )


@contextmanager
def resource_guard(
    resource_type: ResourceType = ResourceType.MEMORY,
    cleanup_on_exit: bool = True,
):
    """Context manager that runs cleanup if resources are low.

    Args:
        resource_type: Resource type to monitor
        cleanup_on_exit: Whether to cleanup on context exit

    Yields:
        ResourceManager instance
    """
    manager = get_resource_manager()

    # Check if cleanup needed before operation
    if manager.needs_cleanup(resource_type):
        manager.run_cleanup(resource_type)

    try:
        yield manager
    finally:
        if cleanup_on_exit:
            # Check again after operation
            if manager.needs_cleanup(resource_type):
                manager.run_cleanup(resource_type)


def cleanup_on_exhaustion() -> None:
    """Emergency cleanup when resources are exhausted.

    Runs all cleanup handlers with force=True.
    """
    manager = get_resource_manager()
    logger.warning("Running emergency cleanup due to resource exhaustion")
    manager.run_cleanup(force=True)
    gc.collect()
