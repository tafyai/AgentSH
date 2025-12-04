"""Tests for telemetry metrics system."""

import time

import pytest

from agentsh.telemetry.metrics import (
    AgentSHMetrics,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_metrics,
    get_metrics_registry,
)


class TestCounter:
    """Tests for Counter metric."""

    def test_create_counter(self):
        """Should create counter with name and description."""
        counter = Counter("test_counter", "A test counter")
        assert counter.name == "test_counter"
        assert counter.description == "A test counter"

    def test_inc_default(self):
        """Should increment by 1 by default."""
        counter = Counter("test", "")
        counter.inc()
        assert counter.get() == 1.0

    def test_inc_custom_amount(self):
        """Should increment by specified amount."""
        counter = Counter("test", "")
        counter.inc(5.0)
        assert counter.get() == 5.0

    def test_inc_with_labels(self):
        """Should track separate values per label set."""
        counter = Counter("test", "")
        counter.inc(1.0, labels={"method": "GET"})
        counter.inc(2.0, labels={"method": "POST"})
        counter.inc(1.0, labels={"method": "GET"})

        assert counter.get(labels={"method": "GET"}) == 2.0
        assert counter.get(labels={"method": "POST"}) == 2.0

    def test_get_unlabeled(self):
        """Should return value for unlabeled counter."""
        counter = Counter("test", "")
        counter.inc(10)
        assert counter.get() == 10.0

    def test_get_all(self):
        """Should return all values with labels."""
        counter = Counter("test", "Test counter")
        counter.inc(5, labels={"a": "1"})
        counter.inc(3, labels={"a": "2"})

        data = counter.get_all()
        assert len(data) == 2

    def test_reset(self):
        """Should reset counter to zero."""
        counter = Counter("test", "")
        counter.inc(10)
        counter.reset()
        assert counter.get() == 0.0

    def test_inc_negative_raises(self):
        """Should raise error for negative increment."""
        counter = Counter("test", "")
        with pytest.raises(ValueError):
            counter.inc(-1)


class TestGauge:
    """Tests for Gauge metric."""

    def test_create_gauge(self):
        """Should create gauge with name and description."""
        gauge = Gauge("test_gauge", "A test gauge")
        assert gauge.name == "test_gauge"

    def test_set(self):
        """Should set gauge value."""
        gauge = Gauge("test", "")
        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_inc(self):
        """Should increment gauge value."""
        gauge = Gauge("test", "")
        gauge.set(10)
        gauge.inc(5)
        assert gauge.get() == 15.0

    def test_dec(self):
        """Should decrement gauge value."""
        gauge = Gauge("test", "")
        gauge.set(10)
        gauge.dec(3)
        assert gauge.get() == 7.0

    def test_set_with_labels(self):
        """Should track separate values per label set."""
        gauge = Gauge("test", "")
        gauge.set(100, labels={"host": "a"})
        gauge.set(200, labels={"host": "b"})

        assert gauge.get(labels={"host": "a"}) == 100.0
        assert gauge.get(labels={"host": "b"}) == 200.0

    def test_get_returns_zero_if_not_set(self):
        """Should return 0 for unset gauge."""
        gauge = Gauge("test", "")
        assert gauge.get() == 0.0

    def test_get_all(self):
        """Should return all values with labels."""
        gauge = Gauge("test", "Test gauge")
        gauge.set(10, labels={"x": "1"})
        gauge.set(20, labels={"x": "2"})

        data = gauge.get_all()
        assert len(data) == 2


class TestHistogram:
    """Tests for Histogram metric."""

    def test_create_histogram(self):
        """Should create histogram with name and buckets."""
        histogram = Histogram("test_histogram", "A test histogram")
        assert histogram.name == "test_histogram"
        assert len(histogram._buckets) > 0

    def test_custom_buckets(self):
        """Should use custom bucket boundaries."""
        buckets = (0.1, 0.5, 1.0, 5.0)
        histogram = Histogram("test", "", buckets=buckets)
        assert histogram._buckets == buckets

    def test_observe(self):
        """Should observe values and update buckets."""
        histogram = Histogram("test", "", buckets=(1, 5, 10))
        histogram.observe(0.5)
        histogram.observe(3)
        histogram.observe(7)
        histogram.observe(15)

        assert histogram.get_count() == 4
        assert histogram.get_sum() == 0.5 + 3 + 7 + 15

    def test_observe_with_labels(self):
        """Should track separate histograms per label set."""
        histogram = Histogram("test", "", buckets=(1, 5, 10))
        histogram.observe(2, labels={"path": "/api"})
        histogram.observe(8, labels={"path": "/api"})
        histogram.observe(1, labels={"path": "/home"})

        assert histogram.get_count(labels={"path": "/api"}) == 2
        assert histogram.get_count(labels={"path": "/home"}) == 1

    def test_time_context_manager(self):
        """Should measure time with context manager."""
        histogram = Histogram("test", "", buckets=(0.001, 0.01, 0.1, 1.0))

        with histogram.time():
            time.sleep(0.005)

        assert histogram.get_count() == 1
        assert histogram.get_sum() > 0.001  # Should be at least 5ms

    def test_bucket_boundaries(self):
        """Should correctly bucket values."""
        histogram = Histogram("test", "", buckets=(1, 5, 10))
        histogram.observe(0.5)  # <= 1
        histogram.observe(3)    # <= 5
        histogram.observe(7)    # <= 10
        histogram.observe(15)   # <= +Inf

        buckets = histogram.get_buckets()

        assert buckets[1] == 1    # <= 1
        assert buckets[5] == 2    # <= 5 (includes <= 1)
        assert buckets[10] == 3   # <= 10 (includes <= 5)


class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry (need to reset singleton)."""
        # Create a non-singleton instance for testing
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True
        return registry

    def test_counter(self, registry):
        """Should create and return counter."""
        counter = registry.counter("test_counter", "Test counter")
        assert isinstance(counter, Counter)

        # Same name should return same counter
        counter2 = registry.counter("test_counter")
        assert counter is counter2

    def test_gauge(self, registry):
        """Should create and return gauge."""
        gauge = registry.gauge("test_gauge", "Test gauge")
        assert isinstance(gauge, Gauge)

        # Same name should return same gauge
        gauge2 = registry.gauge("test_gauge")
        assert gauge is gauge2

    def test_histogram(self, registry):
        """Should create and return histogram."""
        histogram = registry.histogram("test_histogram", "Test histogram")
        assert isinstance(histogram, Histogram)

    def test_collect(self, registry):
        """Should collect all metrics."""
        registry.counter("c1", "Counter 1").inc(5)
        registry.gauge("g1", "Gauge 1").set(10)
        registry.histogram("h1", "Histogram 1").observe(0.5)

        data = registry.collect()
        assert "c1" in data["counters"]
        assert "g1" in data["gauges"]
        assert "h1" in data["histograms"]


class TestMetricsRegistrySingleton:
    """Tests for global metrics registry."""

    def test_get_metrics_registry(self):
        """Should return singleton registry."""
        reg1 = get_metrics_registry()
        reg2 = get_metrics_registry()
        assert reg1 is reg2


class TestAgentSHMetrics:
    """Tests for AgentSH-specific metrics."""

    @pytest.fixture
    def metrics(self):
        """Create fresh metrics instance."""
        # Create a non-singleton registry for testing
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True
        return AgentSHMetrics(registry)

    def test_has_expected_metrics(self, metrics):
        """Should have all expected metrics."""
        assert metrics.tool_executions_total is not None
        assert metrics.tool_duration_seconds is not None
        assert metrics.llm_requests_total is not None
        assert metrics.llm_latency_seconds is not None
        assert metrics.llm_tokens_in_total is not None
        assert metrics.llm_tokens_out_total is not None
        assert metrics.active_sessions is not None
        assert metrics.security_blocks_total is not None

    def test_record_tool_execution(self, metrics):
        """Should record tool execution metrics."""
        metrics.record_tool_execution("shell.run", 0.5, success=True)
        metrics.record_tool_execution("shell.run", 0.3, success=True)
        metrics.record_tool_execution("file.read", 0.1, success=False)

        # Check counter was incremented
        assert metrics.tool_executions_total.get(labels={"tool": "shell.run"}) == 2
        assert metrics.tool_executions_total.get(labels={"tool": "file.read"}) == 1
        assert metrics.tool_errors_total.get(labels={"tool": "file.read"}) == 1

    def test_record_llm_request(self, metrics):
        """Should record LLM request metrics."""
        metrics.record_llm_request(
            provider="anthropic",
            model="claude-3",
            tokens_in=100,
            tokens_out=500,
            latency_seconds=2.0,
            success=True,
        )

        labels = {"provider": "anthropic", "model": "claude-3"}
        assert metrics.llm_requests_total.get(labels=labels) == 1
        assert metrics.llm_tokens_in_total.get(labels=labels) == 100
        assert metrics.llm_tokens_out_total.get(labels=labels) == 500

    def test_record_workflow_execution(self, metrics):
        """Should record workflow execution."""
        metrics.record_workflow_execution(
            workflow_name="test_workflow",
            steps=5,
            duration_seconds=10.0,
            success=True,
        )

        assert metrics.workflow_executions_total.get(
            labels={"workflow": "test_workflow", "status": "success"}
        ) == 1
        assert metrics.workflow_steps_total.get(
            labels={"workflow": "test_workflow"}
        ) == 5


class TestGetMetrics:
    """Tests for global AgentSH metrics."""

    def test_get_metrics(self):
        """Should return singleton metrics instance."""
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2
