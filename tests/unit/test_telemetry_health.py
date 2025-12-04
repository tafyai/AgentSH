"""Tests for telemetry health checks."""

import asyncio

import pytest

from agentsh.telemetry.health import (
    HealthChecker,
    HealthResult,
    HealthStatus,
    OverallHealth,
    check_health,
    get_health_checker,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Should have expected status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthResult:
    """Tests for HealthResult dataclass."""

    def test_create_result(self):
        """Should create result with required fields."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
        )
        assert result.healthy is True
        assert result.status == HealthStatus.HEALTHY
        assert result.timestamp is not None

    def test_create_result_with_details(self):
        """Should create result with optional fields."""
        result = HealthResult(
            healthy=False,
            status=HealthStatus.UNHEALTHY,
            message="Database connection failed",
            details={"error": "timeout"},
            latency_ms=150.5,
        )
        assert result.message == "Database connection failed"
        assert result.details["error"] == "timeout"
        assert result.latency_ms == 150.5

    def test_to_dict(self):
        """Should convert result to dictionary."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
            message="OK",
            details={"version": "1.0"},
            latency_ms=10.0,
        )
        d = result.to_dict()
        assert d["healthy"] is True
        assert d["status"] == "healthy"
        assert d["message"] == "OK"
        assert d["details"]["version"] == "1.0"
        assert d["latency_ms"] == 10.0
        assert "timestamp" in d


class TestOverallHealth:
    """Tests for OverallHealth dataclass."""

    def test_create_overall_health(self):
        """Should create overall health status."""
        components = {
            "config": HealthResult(healthy=True, status=HealthStatus.HEALTHY),
            "db": HealthResult(healthy=True, status=HealthStatus.HEALTHY),
        }
        health = OverallHealth(
            status=HealthStatus.HEALTHY,
            healthy=True,
            components=components,
        )
        assert health.healthy is True
        assert len(health.components) == 2

    def test_to_dict(self):
        """Should convert to dictionary."""
        components = {
            "config": HealthResult(healthy=True, status=HealthStatus.HEALTHY),
        }
        health = OverallHealth(
            status=HealthStatus.HEALTHY,
            healthy=True,
            components=components,
        )
        d = health.to_dict()
        assert d["status"] == "healthy"
        assert d["healthy"] is True
        assert "config" in d["components"]


class TestHealthChecker:
    """Tests for HealthChecker."""

    @pytest.fixture
    def checker(self):
        """Create a health checker."""
        return HealthChecker()

    def test_default_checks_registered(self, checker):
        """Should have default checks registered."""
        assert "config" in checker._checks
        assert "shell" in checker._checks
        assert "llm" in checker._checks
        assert "memory" in checker._checks

    def test_register_check(self, checker):
        """Should register custom check."""
        def custom_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_check("custom", custom_check)
        assert "custom" in checker._checks

    def test_register_critical_check(self, checker):
        """Should mark check as critical."""
        def critical_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_check("critical_db", critical_check, critical=True)
        assert "critical_db" in checker._critical_components

    def test_unregister_check(self, checker):
        """Should unregister check."""
        def temp_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_check("temp", temp_check)
        assert checker.unregister_check("temp") is True
        assert checker.unregister_check("temp") is False  # Already removed
        assert "temp" not in checker._checks

    def test_check_single(self, checker):
        """Should run single check."""
        def always_healthy():
            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="All good",
            )

        checker.register_check("test", always_healthy)
        result = checker.check("test")

        assert result.healthy is True
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None

    def test_check_unknown_component(self, checker):
        """Should return unknown for unregistered component."""
        result = checker.check("nonexistent")
        assert result.healthy is False
        assert result.status == HealthStatus.UNKNOWN

    def test_check_exception_handling(self, checker):
        """Should handle exceptions in check."""
        def failing_check():
            raise ValueError("Check failed!")

        checker.register_check("failing", failing_check)
        result = checker.check("failing")

        assert result.healthy is False
        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed!" in result.message

    def test_check_all(self, checker):
        """Should run all checks."""
        def healthy_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_check("test1", healthy_check)
        checker.register_check("test2", healthy_check)

        health = checker.check_all()
        assert isinstance(health, OverallHealth)
        assert "test1" in health.components
        assert "test2" in health.components

    def test_aggregate_all_healthy(self, checker):
        """Should be healthy when all components healthy."""
        def healthy():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        # Clear default checks and add our own
        checker._checks.clear()
        checker.register_check("a", healthy)
        checker.register_check("b", healthy)

        health = checker.check_all()
        assert health.status == HealthStatus.HEALTHY
        assert health.healthy is True

    def test_aggregate_critical_unhealthy(self, checker):
        """Should be unhealthy when critical component unhealthy."""
        def healthy():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        def unhealthy():
            return HealthResult(healthy=False, status=HealthStatus.UNHEALTHY)

        checker._checks.clear()
        checker._critical_components.clear()
        checker.register_check("non_critical", unhealthy)
        checker.register_check("critical", unhealthy, critical=True)

        health = checker.check_all()
        assert health.status == HealthStatus.UNHEALTHY
        assert health.healthy is False

    def test_aggregate_non_critical_unhealthy(self, checker):
        """Should be degraded when non-critical component unhealthy."""
        def healthy():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        def unhealthy():
            return HealthResult(healthy=False, status=HealthStatus.UNHEALTHY)

        checker._checks.clear()
        checker._critical_components.clear()
        checker.register_check("ok", healthy)
        checker.register_check("not_ok", unhealthy)

        health = checker.check_all()
        assert health.status == HealthStatus.DEGRADED
        assert health.healthy is True  # Still healthy overall

    def test_aggregate_degraded(self, checker):
        """Should be degraded when any component degraded."""
        def healthy():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        def degraded():
            return HealthResult(healthy=True, status=HealthStatus.DEGRADED)

        checker._checks.clear()
        checker._critical_components.clear()
        checker.register_check("ok", healthy)
        checker.register_check("slow", degraded)

        health = checker.check_all()
        assert health.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_async(self, checker):
        """Should run async check."""
        async def async_check():
            await asyncio.sleep(0.001)
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_async_check("async_test", async_check)
        result = await checker.check_async("async_test")

        assert result.healthy is True
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_check_all_async(self, checker):
        """Should run all checks asynchronously."""
        async def async_check():
            await asyncio.sleep(0.001)
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_async_check("async1", async_check)
        checker.register_async_check("async2", async_check)

        health = await checker.check_all_async()
        assert "async1" in health.components
        assert "async2" in health.components


class TestHealthCheckerSingleton:
    """Tests for global health checker."""

    def test_get_health_checker_singleton(self):
        """Should return singleton instance."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_check_health(self):
        """Should return overall health status."""
        health = check_health()
        assert isinstance(health, OverallHealth)
        assert health.status in list(HealthStatus)


class TestDefaultChecks:
    """Tests for default health check implementations."""

    @pytest.fixture
    def checker(self):
        """Create a fresh health checker."""
        return HealthChecker()

    def test_config_check(self, checker):
        """Config check should handle module not available."""
        result = checker.check("config")
        # Should not raise, status depends on config availability
        assert result.status in list(HealthStatus)

    def test_shell_check(self, checker):
        """Shell check should handle module not available."""
        result = checker.check("shell")
        # Should not raise
        assert result.status in list(HealthStatus)

    def test_llm_check(self, checker):
        """LLM check should handle module not available."""
        result = checker.check("llm")
        # Should not raise
        assert result.status in list(HealthStatus)

    def test_memory_check(self, checker):
        """Memory check should handle module not available."""
        result = checker.check("memory")
        # Should not raise
        assert result.status in list(HealthStatus)
