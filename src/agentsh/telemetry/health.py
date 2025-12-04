"""Health checks for AgentSH components.

Provides comprehensive health checking for all system components
including shell, LLM connections, memory stores, and configuration.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthResult:
    """Result of a health check.

    Attributes:
        healthy: Whether the component is healthy
        status: Overall health status
        message: Human-readable status message
        details: Additional details about the check
        latency_ms: Time taken to perform the check
        timestamp: When the check was performed
    """

    healthy: bool
    status: HealthStatus
    message: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "healthy": self.healthy,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OverallHealth:
    """Overall system health status.

    Attributes:
        status: Aggregated health status
        healthy: Whether all critical components are healthy
        components: Individual component health results
        timestamp: When the check was performed
    """

    status: HealthStatus
    healthy: bool
    components: dict[str, HealthResult]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "healthy": self.healthy,
            "components": {
                name: result.to_dict()
                for name, result in self.components.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }


# Type alias for health check functions
HealthCheckFunc = Callable[[], HealthResult]
AsyncHealthCheckFunc = Callable[[], "asyncio.Future[HealthResult]"]


class HealthChecker:
    """Performs health checks on AgentSH components.

    Example:
        checker = HealthChecker()
        checker.register_check("database", lambda: check_db_connection())

        # Run all checks
        health = checker.check_all()
        if not health.healthy:
            print(f"System unhealthy: {health.status}")

        # Run single check
        result = checker.check("config")
    """

    def __init__(self) -> None:
        """Initialize health checker."""
        self._checks: dict[str, HealthCheckFunc] = {}
        self._async_checks: dict[str, AsyncHealthCheckFunc] = {}
        self._critical_components: set[str] = {"config"}

        # Register default checks
        self._register_default_checks()

        logger.debug("HealthChecker initialized")

    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self._checks["config"] = self._check_config
        self._checks["shell"] = self._check_shell
        self._checks["llm"] = self._check_llm
        self._checks["memory"] = self._check_memory

    def register_check(
        self,
        name: str,
        check_func: HealthCheckFunc,
        critical: bool = False,
    ) -> None:
        """Register a health check.

        Args:
            name: Name of the component
            check_func: Function that performs the check
            critical: Whether this component is critical for system health
        """
        self._checks[name] = check_func
        if critical:
            self._critical_components.add(name)
        logger.debug("Health check registered", component=name, critical=critical)

    def register_async_check(
        self,
        name: str,
        check_func: AsyncHealthCheckFunc,
        critical: bool = False,
    ) -> None:
        """Register an async health check.

        Args:
            name: Name of the component
            check_func: Async function that performs the check
            critical: Whether this component is critical
        """
        self._async_checks[name] = check_func
        if critical:
            self._critical_components.add(name)
        logger.debug("Async health check registered", component=name)

    def unregister_check(self, name: str) -> bool:
        """Unregister a health check.

        Args:
            name: Name of the component

        Returns:
            True if check was removed
        """
        removed = False
        if name in self._checks:
            del self._checks[name]
            removed = True
        if name in self._async_checks:
            del self._async_checks[name]
            removed = True
        self._critical_components.discard(name)
        return removed

    def check(self, name: str) -> HealthResult:
        """Run a single health check.

        Args:
            name: Name of the component to check

        Returns:
            Health result for the component
        """
        if name not in self._checks:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNKNOWN,
                message=f"No health check registered for '{name}'",
            )

        start = time.perf_counter()
        try:
            result = self._checks[name]()
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as e:
            logger.error("Health check failed", component=name, error=str(e))
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    def check_all(self) -> OverallHealth:
        """Run all registered health checks.

        Returns:
            Overall health status with individual component results
        """
        components: dict[str, HealthResult] = {}

        for name in self._checks:
            components[name] = self.check(name)

        # Determine overall status
        status, healthy = self._aggregate_status(components)

        logger.info(
            "Health check completed",
            status=status.value,
            healthy=healthy,
            components=len(components),
        )

        return OverallHealth(
            status=status,
            healthy=healthy,
            components=components,
        )

    async def check_async(self, name: str) -> HealthResult:
        """Run a single async health check.

        Args:
            name: Name of the component

        Returns:
            Health result
        """
        if name in self._async_checks:
            start = time.perf_counter()
            try:
                result = await self._async_checks[name]()
                result.latency_ms = (time.perf_counter() - start) * 1000
                return result
            except Exception as e:
                return HealthResult(
                    healthy=False,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Async check failed: {e}",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
        elif name in self._checks:
            return self.check(name)
        else:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNKNOWN,
                message=f"No health check registered for '{name}'",
            )

    async def check_all_async(self) -> OverallHealth:
        """Run all health checks asynchronously.

        Returns:
            Overall health status
        """
        components: dict[str, HealthResult] = {}

        # Run sync checks
        for name in self._checks:
            if name not in self._async_checks:
                components[name] = self.check(name)

        # Run async checks concurrently
        if self._async_checks:
            tasks = {
                name: asyncio.create_task(func())
                for name, func in self._async_checks.items()
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for name, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    components[name] = HealthResult(
                        healthy=False,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Async check failed: {result}",
                    )
                else:
                    components[name] = result

        status, healthy = self._aggregate_status(components)

        return OverallHealth(
            status=status,
            healthy=healthy,
            components=components,
        )

    def _aggregate_status(
        self,
        components: dict[str, HealthResult],
    ) -> tuple[HealthStatus, bool]:
        """Aggregate component statuses into overall status.

        Args:
            components: Individual component results

        Returns:
            Tuple of (overall_status, is_healthy)
        """
        critical_healthy = True
        all_healthy = True
        any_degraded = False

        for name, result in components.items():
            if not result.healthy:
                all_healthy = False
                if name in self._critical_components:
                    critical_healthy = False
            if result.status == HealthStatus.DEGRADED:
                any_degraded = True

        if not critical_healthy:
            return HealthStatus.UNHEALTHY, False
        elif not all_healthy or any_degraded:
            return HealthStatus.DEGRADED, True
        else:
            return HealthStatus.HEALTHY, True

    # Default check implementations

    def _check_config(self) -> HealthResult:
        """Check if configuration is valid."""
        try:
            from agentsh.config.loader import load_config

            config = load_config()
            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="Configuration loaded successfully",
                details={"config_source": "file"},
            )
        except ImportError:
            return HealthResult(
                healthy=True,
                status=HealthStatus.UNKNOWN,
                message="Config module not available",
            )
        except Exception as e:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration error: {e}",
            )

    def _check_shell(self) -> HealthResult:
        """Check if shell/PTY is healthy."""
        try:
            from agentsh.shell.manager import get_shell_manager

            manager = get_shell_manager()
            if manager is None:
                return HealthResult(
                    healthy=True,
                    status=HealthStatus.UNKNOWN,
                    message="Shell manager not initialized",
                )

            # Check if shell is alive
            if hasattr(manager, "is_alive") and callable(manager.is_alive):
                alive = manager.is_alive()
                return HealthResult(
                    healthy=alive,
                    status=HealthStatus.HEALTHY if alive else HealthStatus.UNHEALTHY,
                    message="Shell is alive" if alive else "Shell is not responding",
                )

            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="Shell manager available",
            )
        except ImportError:
            return HealthResult(
                healthy=True,
                status=HealthStatus.UNKNOWN,
                message="Shell module not available",
            )
        except Exception as e:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Shell check failed: {e}",
            )

    def _check_llm(self) -> HealthResult:
        """Check if LLM connection is healthy."""
        try:
            from agentsh.llm.client import get_llm_client

            client = get_llm_client()
            if client is None:
                return HealthResult(
                    healthy=True,
                    status=HealthStatus.UNKNOWN,
                    message="LLM client not configured",
                )

            # Check if client has health check method
            if hasattr(client, "health_check"):
                is_healthy = client.health_check()
                return HealthResult(
                    healthy=is_healthy,
                    status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
                    message="LLM API reachable" if is_healthy else "LLM API not reachable",
                )

            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="LLM client configured",
            )
        except ImportError:
            return HealthResult(
                healthy=True,
                status=HealthStatus.UNKNOWN,
                message="LLM module not available",
            )
        except Exception as e:
            return HealthResult(
                healthy=False,
                status=HealthStatus.DEGRADED,
                message=f"LLM check failed: {e}",
            )

    def _check_memory(self) -> HealthResult:
        """Check if memory store is healthy."""
        try:
            from agentsh.memory.manager import get_memory_manager

            manager = get_memory_manager()
            if manager is None:
                return HealthResult(
                    healthy=True,
                    status=HealthStatus.UNKNOWN,
                    message="Memory manager not initialized",
                )

            # Check if store is accessible
            if hasattr(manager, "store"):
                store = manager.store
                # Try a simple operation to verify store is working
                if hasattr(store, "list"):
                    try:
                        # Just check if list() works, don't care about results
                        store.list(limit=1)
                        return HealthResult(
                            healthy=True,
                            status=HealthStatus.HEALTHY,
                            message="Memory store accessible",
                            details={"store_type": type(store).__name__},
                        )
                    except Exception as e:
                        return HealthResult(
                            healthy=False,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Memory store error: {e}",
                        )

            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="Memory manager available",
            )
        except ImportError:
            return HealthResult(
                healthy=True,
                status=HealthStatus.UNKNOWN,
                message="Memory module not available",
            )
        except Exception as e:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {e}",
            )


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance.

    Returns:
        Global HealthChecker singleton
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def check_health() -> OverallHealth:
    """Convenience function to check system health.

    Returns:
        Overall health status
    """
    return get_health_checker().check_all()


async def check_health_async() -> OverallHealth:
    """Convenience function to check system health asynchronously.

    Returns:
        Overall health status
    """
    return await get_health_checker().check_all_async()
