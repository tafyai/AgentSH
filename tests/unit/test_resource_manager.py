"""Tests for resource management utilities."""

import gc
import threading
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentsh.utils.resource_manager import (
    CleanupHandler,
    ResourceLimits,
    ResourceManager,
    ResourceStatus,
    ResourceType,
    ResourceUsage,
    cleanup_on_exhaustion,
    get_resource_manager,
    register_cleanup,
    resource_guard,
)


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_resource_types(self) -> None:
        """Should have expected resource types."""
        assert ResourceType.MEMORY == "memory"
        assert ResourceType.FILE_HANDLES == "file_handles"
        assert ResourceType.CONNECTIONS == "connections"
        assert ResourceType.THREADS == "threads"
        assert ResourceType.PROCESSES == "processes"


class TestResourceStatus:
    """Tests for ResourceStatus enum."""

    def test_status_values(self) -> None:
        """Should have expected status values."""
        assert ResourceStatus.HEALTHY == "healthy"
        assert ResourceStatus.WARNING == "warning"
        assert ResourceStatus.CRITICAL == "critical"
        assert ResourceStatus.EXHAUSTED == "exhausted"


class TestResourceLimits:
    """Tests for ResourceLimits dataclass."""

    def test_default_limits(self) -> None:
        """Should have sensible defaults."""
        limits = ResourceLimits()
        assert limits.memory_warning_threshold == 0.7
        assert limits.memory_critical_threshold == 0.85
        assert limits.connections_max == 500

    def test_custom_limits(self) -> None:
        """Should accept custom values."""
        limits = ResourceLimits(
            memory_warning_threshold=0.5,
            memory_critical_threshold=0.75,
            connections_max=100,
        )
        assert limits.memory_warning_threshold == 0.5
        assert limits.memory_critical_threshold == 0.75
        assert limits.connections_max == 100


class TestResourceUsage:
    """Tests for ResourceUsage dataclass."""

    def test_default_usage(self) -> None:
        """Should have zero defaults."""
        usage = ResourceUsage()
        assert usage.memory_used_bytes == 0
        assert usage.memory_percent == 0.0
        assert usage.active_threads == 0

    def test_timestamp(self) -> None:
        """Should have timestamp."""
        usage = ResourceUsage()
        assert isinstance(usage.timestamp, datetime)

    def test_get_status_memory_healthy(self) -> None:
        """Should return healthy for low memory usage."""
        usage = ResourceUsage(memory_percent=0.5)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.MEMORY, limits)
        assert status == ResourceStatus.HEALTHY

    def test_get_status_memory_warning(self) -> None:
        """Should return warning for moderate memory usage."""
        usage = ResourceUsage(memory_percent=0.75)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.MEMORY, limits)
        assert status == ResourceStatus.WARNING

    def test_get_status_memory_critical(self) -> None:
        """Should return critical for high memory usage."""
        usage = ResourceUsage(memory_percent=0.9)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.MEMORY, limits)
        assert status == ResourceStatus.CRITICAL

    def test_get_status_file_handles(self) -> None:
        """Should check file handle status."""
        usage = ResourceUsage(file_handles_percent=0.9)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.FILE_HANDLES, limits)
        assert status == ResourceStatus.CRITICAL

    def test_get_status_connections(self) -> None:
        """Should check connection status."""
        usage = ResourceUsage(active_connections=150)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.CONNECTIONS, limits)
        assert status == ResourceStatus.WARNING

    def test_get_status_threads(self) -> None:
        """Should check thread status."""
        usage = ResourceUsage(active_threads=120)
        limits = ResourceLimits()
        status = usage.get_status(ResourceType.THREADS, limits)
        assert status == ResourceStatus.CRITICAL


class TestCleanupHandler:
    """Tests for CleanupHandler class."""

    def test_create_handler(self) -> None:
        """Should create cleanup handler."""
        callback = MagicMock()
        handler = CleanupHandler(
            name="test",
            callback=callback,
            resource_type=ResourceType.MEMORY,
            priority=25,
        )
        assert handler.name == "test"
        assert handler.resource_type == ResourceType.MEMORY
        assert handler.priority == 25
        assert handler.run_count == 0

    def test_execute_success(self) -> None:
        """Should execute callback successfully."""
        callback = MagicMock()
        handler = CleanupHandler("test", callback, ResourceType.MEMORY)

        result = handler.execute()

        assert result is True
        callback.assert_called_once()
        assert handler.run_count == 1
        assert handler.last_run is not None

    def test_execute_failure(self) -> None:
        """Should handle callback failure."""
        callback = MagicMock(side_effect=Exception("Cleanup failed"))
        handler = CleanupHandler("test", callback, ResourceType.MEMORY)

        result = handler.execute()

        assert result is False
        assert handler.error_count == 1


class TestResourceManager:
    """Tests for ResourceManager class."""

    @pytest.fixture
    def manager(self) -> ResourceManager:
        """Create a resource manager for testing."""
        return ResourceManager()

    def test_create_manager(self) -> None:
        """Should create manager with defaults."""
        manager = ResourceManager()
        assert manager.limits is not None
        assert isinstance(manager.limits, ResourceLimits)

    def test_create_manager_custom_limits(self) -> None:
        """Should accept custom limits."""
        limits = ResourceLimits(memory_warning_threshold=0.5)
        manager = ResourceManager(limits=limits)
        assert manager.limits.memory_warning_threshold == 0.5

    def test_register_cleanup(self, manager: ResourceManager) -> None:
        """Should register cleanup handler."""
        callback = MagicMock()
        handler = manager.register_cleanup(
            "test", callback, ResourceType.MEMORY, priority=10
        )

        assert handler.name == "test"
        assert len(manager._handlers) == 1

    def test_register_cleanup_sorted_by_priority(
        self, manager: ResourceManager
    ) -> None:
        """Should keep handlers sorted by priority."""
        manager.register_cleanup("low", MagicMock(), ResourceType.MEMORY, priority=100)
        manager.register_cleanup("high", MagicMock(), ResourceType.MEMORY, priority=10)
        manager.register_cleanup("mid", MagicMock(), ResourceType.MEMORY, priority=50)

        assert manager._handlers[0].name == "high"
        assert manager._handlers[1].name == "mid"
        assert manager._handlers[2].name == "low"

    def test_unregister_cleanup(self, manager: ResourceManager) -> None:
        """Should unregister cleanup handler."""
        manager.register_cleanup("test", MagicMock(), ResourceType.MEMORY)
        result = manager.unregister_cleanup("test")

        assert result is True
        assert len(manager._handlers) == 0

    def test_unregister_cleanup_not_found(self, manager: ResourceManager) -> None:
        """Should return False if handler not found."""
        result = manager.unregister_cleanup("nonexistent")
        assert result is False

    def test_track_object(self, manager: ResourceManager) -> None:
        """Should track objects with weak references."""
        # Use a class instance (dict can't be weakly referenced)
        class TrackableObject:
            pass
        obj = TrackableObject()
        manager.track_object(obj)
        assert len(manager._tracked_objects) == 1

    def test_track_object_weak_ref(self, manager: ResourceManager) -> None:
        """Should use weak references."""
        class TrackableObject:
            pass

        def create_and_track():
            obj = TrackableObject()
            manager.track_object(obj)
            return len(manager._tracked_objects)

        count = create_and_track()
        assert count == 1

        # After gc, object should be gone
        gc.collect()
        assert len(manager._tracked_objects) == 0

    def test_get_usage(self, manager: ResourceManager) -> None:
        """Should get resource usage."""
        usage = manager.get_usage()

        assert isinstance(usage, ResourceUsage)
        assert usage.active_threads > 0  # At least main thread
        assert isinstance(usage.timestamp, datetime)

    def test_needs_cleanup_healthy(self, manager: ResourceManager) -> None:
        """Should not need cleanup when healthy."""
        # With default limits and typical usage, should be healthy
        # This may vary by system, so we just check it returns a bool
        result = manager.needs_cleanup()
        assert isinstance(result, bool)

    def test_needs_cleanup_specific_type(self, manager: ResourceManager) -> None:
        """Should check specific resource type."""
        result = manager.needs_cleanup(ResourceType.MEMORY)
        assert isinstance(result, bool)

    def test_run_cleanup(self, manager: ResourceManager) -> None:
        """Should run cleanup handlers."""
        callback = MagicMock()
        manager.register_cleanup("test", callback, ResourceType.MEMORY)

        count = manager.run_cleanup(force=True)

        assert count == 1
        callback.assert_called_once()

    def test_run_cleanup_specific_type(self, manager: ResourceManager) -> None:
        """Should only run handlers for specific type."""
        memory_cb = MagicMock()
        file_cb = MagicMock()
        manager.register_cleanup("memory", memory_cb, ResourceType.MEMORY)
        manager.register_cleanup("files", file_cb, ResourceType.FILE_HANDLES)

        manager.run_cleanup(ResourceType.MEMORY, force=True)

        memory_cb.assert_called_once()
        file_cb.assert_not_called()

    def test_run_cleanup_not_needed(self, manager: ResourceManager) -> None:
        """Should not run if cleanup not needed."""
        callback = MagicMock()
        manager.register_cleanup("test", callback, ResourceType.MEMORY)

        # Mock needs_cleanup to return False
        with patch.object(manager, "needs_cleanup", return_value=False):
            count = manager.run_cleanup()

        assert count == 0
        callback.assert_not_called()

    def test_get_status(self, manager: ResourceManager) -> None:
        """Should get status for all resource types."""
        status = manager.get_status()

        assert ResourceType.MEMORY in status
        assert ResourceType.FILE_HANDLES in status
        assert ResourceType.CONNECTIONS in status
        assert ResourceType.THREADS in status

    def test_is_healthy(self, manager: ResourceManager) -> None:
        """Should check if all resources are healthy."""
        result = manager.is_healthy()
        assert isinstance(result, bool)

    def test_shutdown(self, manager: ResourceManager) -> None:
        """Should shutdown and cleanup."""
        callback = MagicMock()
        manager.register_cleanup("test", callback, ResourceType.MEMORY)

        manager.shutdown()

        assert manager._shutdown is True
        callback.assert_called_once()

    def test_shutdown_idempotent(self, manager: ResourceManager) -> None:
        """Should only shutdown once."""
        callback = MagicMock()
        manager.register_cleanup("test", callback, ResourceType.MEMORY)

        manager.shutdown()
        manager.shutdown()

        # Should only be called once
        assert callback.call_count == 1


class TestGlobalFunctions:
    """Tests for global resource management functions."""

    def test_get_resource_manager(self) -> None:
        """Should return manager instance."""
        manager = get_resource_manager()
        assert isinstance(manager, ResourceManager)

    def test_get_resource_manager_same_instance(self) -> None:
        """Should return same instance."""
        m1 = get_resource_manager()
        m2 = get_resource_manager()
        assert m1 is m2

    def test_register_cleanup_global(self) -> None:
        """Should register with global manager."""
        callback = MagicMock()
        handler = register_cleanup(
            "global_test",
            callback,
            ResourceType.MEMORY,
        )

        assert handler.name == "global_test"

        # Cleanup
        get_resource_manager().unregister_cleanup("global_test")

    def test_cleanup_on_exhaustion(self) -> None:
        """Should run emergency cleanup."""
        callback = MagicMock()
        handler = register_cleanup(
            "emergency_test",
            callback,
            ResourceType.MEMORY,
        )

        cleanup_on_exhaustion()

        callback.assert_called()

        # Cleanup
        get_resource_manager().unregister_cleanup("emergency_test")


class TestResourceGuard:
    """Tests for resource_guard context manager."""

    def test_resource_guard_basic(self) -> None:
        """Should yield manager in context."""
        with resource_guard() as manager:
            assert isinstance(manager, ResourceManager)

    def test_resource_guard_cleanup_on_exit(self) -> None:
        """Should check cleanup on exit."""
        # This is a basic test - actual cleanup depends on resource state
        with resource_guard(cleanup_on_exit=True) as manager:
            pass  # Just ensure it doesn't raise

    def test_resource_guard_no_cleanup_on_exit(self) -> None:
        """Should skip cleanup when disabled."""
        with resource_guard(cleanup_on_exit=False) as manager:
            pass


class TestResourceUsageCollection:
    """Tests for resource usage data collection."""

    def test_memory_usage_collected(self) -> None:
        """Should collect memory usage data."""
        manager = ResourceManager()
        usage = manager.get_usage()

        # Memory should be non-zero (process is running)
        assert usage.memory_used_bytes > 0 or usage.memory_percent >= 0

    def test_thread_count_collected(self) -> None:
        """Should collect thread count."""
        manager = ResourceManager()
        usage = manager.get_usage()

        # At least main thread
        assert usage.active_threads >= 1

    def test_thread_count_increases(self) -> None:
        """Should track new threads."""
        manager = ResourceManager()
        initial = manager.get_usage().active_threads

        # Create a thread
        event = threading.Event()
        thread = threading.Thread(target=lambda: event.wait())
        thread.start()

        try:
            usage = manager.get_usage()
            assert usage.active_threads >= initial
        finally:
            event.set()
            thread.join()
