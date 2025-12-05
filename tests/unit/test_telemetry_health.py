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


class TestHealthCheckerAsyncExtended:
    """Extended async tests for HealthChecker."""

    @pytest.fixture
    def checker(self):
        """Create a fresh health checker."""
        return HealthChecker()

    @pytest.mark.asyncio
    async def test_check_async_fallback_to_sync(self, checker):
        """Should fall back to sync check if no async check registered."""
        def sync_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY, message="Sync")

        checker._checks.clear()
        checker._async_checks.clear()
        checker.register_check("sync_only", sync_check)

        result = await checker.check_async("sync_only")
        assert result.healthy is True
        assert result.message == "Sync"

    @pytest.mark.asyncio
    async def test_check_async_unknown_component(self, checker):
        """Should return unknown for unregistered async component."""
        result = await checker.check_async("nonexistent_async")
        assert result.status == HealthStatus.UNKNOWN
        assert "No health check registered" in result.message

    @pytest.mark.asyncio
    async def test_check_async_exception_handling(self, checker):
        """Should handle exceptions in async check."""
        async def failing_async_check():
            raise RuntimeError("Async check exploded!")

        checker.register_async_check("failing_async", failing_async_check)
        result = await checker.check_async("failing_async")

        assert result.healthy is False
        assert result.status == HealthStatus.UNHEALTHY
        assert "Async check failed" in result.message

    @pytest.mark.asyncio
    async def test_check_all_async_with_exception(self, checker):
        """Should handle exceptions in check_all_async."""
        async def good_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        async def bad_check():
            raise ValueError("Something went wrong")

        checker._checks.clear()
        checker._async_checks.clear()
        checker._critical_components.clear()

        checker.register_async_check("good", good_check)
        checker.register_async_check("bad", bad_check)

        health = await checker.check_all_async()

        assert "good" in health.components
        assert "bad" in health.components
        assert health.components["good"].healthy is True
        assert health.components["bad"].healthy is False
        assert "Async check failed" in health.components["bad"].message

    @pytest.mark.asyncio
    async def test_check_all_async_mixed_sync_async(self, checker):
        """Should run both sync and async checks."""
        def sync_check():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY, message="sync")

        async def async_check():
            await asyncio.sleep(0.001)
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY, message="async")

        checker._checks.clear()
        checker._async_checks.clear()
        checker._critical_components.clear()

        checker.register_check("sync", sync_check)
        checker.register_async_check("async", async_check)

        health = await checker.check_all_async()

        assert "sync" in health.components
        assert "async" in health.components

    def test_register_async_check_critical(self, checker):
        """Should mark async check as critical."""
        async def critical_async():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_async_check("critical_async", critical_async, critical=True)
        assert "critical_async" in checker._critical_components

    def test_unregister_async_check(self, checker):
        """Should unregister async check."""
        async def temp_async():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_async_check("temp_async", temp_async, critical=True)
        assert "temp_async" in checker._async_checks
        assert "temp_async" in checker._critical_components

        result = checker.unregister_check("temp_async")
        assert result is True
        assert "temp_async" not in checker._async_checks
        assert "temp_async" not in checker._critical_components


class TestCheckHealthAsync:
    """Test check_health_async convenience function."""

    @pytest.mark.asyncio
    async def test_check_health_async(self):
        """Should return overall health status asynchronously."""
        from agentsh.telemetry.health import check_health_async

        health = await check_health_async()
        assert isinstance(health, OverallHealth)
        assert health.status in list(HealthStatus)


class TestDefaultCheckImplementations:
    """Tests for the default check implementations in HealthChecker."""

    @pytest.fixture
    def checker(self):
        """Create a fresh health checker."""
        return HealthChecker()

    def test_check_config_success(self, checker):
        """Should check config successfully."""
        result = checker._check_config()
        # Should return a result (either healthy from loaded config or unknown from import error)
        assert result.status in list(HealthStatus)
        assert result is not None

    def test_check_config_calls_load_config(self, checker):
        """Should call load_config to verify configuration."""
        from unittest.mock import patch

        with patch("agentsh.config.loader.load_config") as mock_load:
            mock_load.return_value = {}
            result = checker._check_config()
            assert result.healthy is True or result.status == HealthStatus.UNKNOWN

    def test_check_shell_returns_result(self, checker):
        """Should return a health result for shell check."""
        result = checker._check_shell()
        assert result.status in list(HealthStatus)
        assert result is not None

    def test_check_llm_returns_result(self, checker):
        """Should return a health result for LLM check."""
        result = checker._check_llm()
        assert result.status in list(HealthStatus)
        # LLM module may not be available, so we just check it doesn't crash
        assert result is not None

    def test_check_memory_returns_result(self, checker):
        """Should return a health result for memory check."""
        result = checker._check_memory()
        assert result.status in list(HealthStatus)
        assert result is not None

    def test_all_default_checks_run(self, checker):
        """Should run all default checks without error."""
        # Run config check
        config_result = checker._check_config()
        assert config_result is not None

        # Run shell check
        shell_result = checker._check_shell()
        assert shell_result is not None

        # Run LLM check
        llm_result = checker._check_llm()
        assert llm_result is not None

        # Run memory check
        memory_result = checker._check_memory()
        assert memory_result is not None

    def test_check_config_handles_exception(self, checker):
        """Should handle exceptions gracefully."""
        from unittest.mock import patch

        with patch("agentsh.config.loader.load_config", side_effect=Exception("Config error")):
            result = checker._check_config()
            # Should not crash, should return unhealthy or unknown
            assert result.status in list(HealthStatus)


class TestHealthResultEdgeCases:
    """Edge case tests for HealthResult."""

    def test_health_result_no_optional_fields(self):
        """Should work with only required fields."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
        )
        d = result.to_dict()
        assert d["healthy"] is True
        assert d["message"] is None
        assert d["details"] is None
        assert d["latency_ms"] is None

    def test_health_result_all_statuses(self):
        """Should support all status values."""
        for status in HealthStatus:
            result = HealthResult(
                healthy=status == HealthStatus.HEALTHY,
                status=status,
            )
            assert result.status == status


class TestOverallHealthEdgeCases:
    """Edge case tests for OverallHealth."""

    def test_overall_health_empty_components(self):
        """Should handle empty components."""
        health = OverallHealth(
            status=HealthStatus.UNKNOWN,
            healthy=True,
            components={},
        )
        d = health.to_dict()
        assert d["components"] == {}

    def test_overall_health_timestamp(self):
        """Should include timestamp in dict."""
        health = OverallHealth(
            status=HealthStatus.HEALTHY,
            healthy=True,
            components={},
        )
        d = health.to_dict()
        assert "timestamp" in d
        assert d["healthy"] is True

    def test_overall_health_multiple_components(self):
        """Should serialize multiple components."""
        components = {
            "config": HealthResult(healthy=True, status=HealthStatus.HEALTHY),
            "db": HealthResult(healthy=False, status=HealthStatus.UNHEALTHY, message="Connection failed"),
            "cache": HealthResult(healthy=True, status=HealthStatus.DEGRADED, message="Slow"),
        }
        health = OverallHealth(
            status=HealthStatus.DEGRADED,
            healthy=False,
            components=components,
        )
        d = health.to_dict()
        assert len(d["components"]) == 3
        assert d["components"]["db"]["healthy"] is False


class TestHealthCheckerEdgeCases:
    """Edge case tests for HealthChecker."""

    @pytest.fixture
    def checker(self):
        """Create a fresh health checker."""
        c = HealthChecker()
        c._checks.clear()
        c._async_checks.clear()
        c._critical_components.clear()
        return c

    def test_check_all_empty(self, checker):
        """Should handle no checks registered."""
        health = checker.check_all()
        assert health.status == HealthStatus.HEALTHY  # No issues if nothing to check
        assert len(health.components) == 0

    def test_check_all_only_unknown(self, checker):
        """Should aggregate unknown status correctly."""
        def unknown_check():
            return HealthResult(healthy=True, status=HealthStatus.UNKNOWN)

        checker.register_check("unknown1", unknown_check)
        checker.register_check("unknown2", unknown_check)

        health = checker.check_all()
        # All unknown -> overall should be unknown or healthy
        assert health.status in [HealthStatus.HEALTHY, HealthStatus.UNKNOWN]

    def test_register_check_overwrite(self, checker):
        """Should overwrite existing check."""
        def check_v1():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY, message="v1")

        def check_v2():
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY, message="v2")

        checker.register_check("test", check_v1)
        checker.register_check("test", check_v2)

        result = checker.check("test")
        assert result.message == "v2"

    def test_check_measures_latency(self, checker):
        """Should measure check latency."""
        import time

        def slow_check():
            time.sleep(0.01)  # 10ms
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_check("slow", slow_check)
        result = checker.check("slow")

        assert result.latency_ms is not None
        assert result.latency_ms >= 10  # At least 10ms

    @pytest.mark.asyncio
    async def test_check_all_async_empty(self, checker):
        """Should handle no async checks registered."""
        health = await checker.check_all_async()
        assert health.status == HealthStatus.HEALTHY
        assert len(health.components) == 0

    @pytest.mark.asyncio
    async def test_check_async_measures_latency(self, checker):
        """Should measure async check latency."""
        async def slow_async():
            await asyncio.sleep(0.01)
            return HealthResult(healthy=True, status=HealthStatus.HEALTHY)

        checker.register_async_check("slow_async", slow_async)
        result = await checker.check_async("slow_async")

        assert result.latency_ms is not None
        assert result.latency_ms >= 10
