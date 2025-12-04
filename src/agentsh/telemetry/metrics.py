"""Metrics collection for AgentSH.

Provides counters, histograms, and gauges for monitoring
application performance and behavior.
"""

import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generator, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricValue:
    """A metric value with timestamp."""

    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class HistogramBucket:
    """A histogram bucket."""

    le: float  # Less than or equal to
    count: int = 0


class Counter:
    """A counter metric that only increases.

    Example:
        counter = Counter("tool_executions_total", "Total tool executions")
        counter.inc()
        counter.inc(labels={"tool": "shell.run"})
    """

    def __init__(self, name: str, description: str = "") -> None:
        """Initialize counter.

        Args:
            name: Metric name
            description: Metric description
        """
        self.name = name
        self.description = description
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment the counter.

        Args:
            amount: Amount to increment by (must be positive)
            labels: Optional labels for this increment
        """
        if amount < 0:
            raise ValueError("Counter can only be incremented")

        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[label_key] += amount

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        """Get the current counter value.

        Args:
            labels: Optional labels to filter by

        Returns:
            Current counter value
        """
        label_key = tuple(sorted((labels or {}).items()))
        return self._values.get(label_key, 0.0)

    def get_all(self) -> list[tuple[dict[str, str], float]]:
        """Get all counter values with their labels.

        Returns:
            List of (labels, value) tuples
        """
        return [(dict(k), v) for k, v in self._values.items()]

    def reset(self) -> None:
        """Reset counter to zero."""
        with self._lock:
            self._values.clear()


class Gauge:
    """A gauge metric that can increase or decrease.

    Example:
        gauge = Gauge("active_sessions", "Number of active sessions")
        gauge.set(5)
        gauge.inc()
        gauge.dec()
    """

    def __init__(self, name: str, description: str = "") -> None:
        """Initialize gauge.

        Args:
            name: Metric name
            description: Metric description
        """
        self.name = name
        self.description = description
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Set the gauge value.

        Args:
            value: Value to set
            labels: Optional labels
        """
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[label_key] = value

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment the gauge.

        Args:
            amount: Amount to increment by
            labels: Optional labels
        """
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[label_key] += amount

    def dec(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Decrement the gauge.

        Args:
            amount: Amount to decrement by
            labels: Optional labels
        """
        label_key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[label_key] -= amount

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        """Get the current gauge value.

        Args:
            labels: Optional labels to filter by

        Returns:
            Current gauge value
        """
        label_key = tuple(sorted((labels or {}).items()))
        return self._values.get(label_key, 0.0)

    def get_all(self) -> list[tuple[dict[str, str], float]]:
        """Get all gauge values with their labels.

        Returns:
            List of (labels, value) tuples
        """
        return [(dict(k), v) for k, v in self._values.items()]


class Histogram:
    """A histogram metric for measuring distributions.

    Example:
        histogram = Histogram(
            "tool_duration_seconds",
            "Tool execution duration",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
        )
        histogram.observe(0.25)
    """

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple[float, ...]] = None,
    ) -> None:
        """Initialize histogram.

        Args:
            name: Metric name
            description: Metric description
            buckets: Bucket boundaries (defaults to DEFAULT_BUCKETS)
        """
        self.name = name
        self.description = description
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: dict[tuple, dict[float, int]] = {}
        self._sums: dict[tuple, float] = defaultdict(float)
        self._totals: dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Record an observation.

        Args:
            value: Value to record
            labels: Optional labels
        """
        label_key = tuple(sorted((labels or {}).items()))

        with self._lock:
            # Initialize buckets for this label combination
            if label_key not in self._counts:
                self._counts[label_key] = {b: 0 for b in self._buckets}
                self._counts[label_key][float("inf")] = 0

            # Update buckets
            for bucket in self._buckets:
                if value <= bucket:
                    self._counts[label_key][bucket] += 1

            # Always update +Inf bucket
            self._counts[label_key][float("inf")] += 1

            # Update sum and total
            self._sums[label_key] += value
            self._totals[label_key] += 1

    @contextmanager
    def time(
        self, labels: Optional[dict[str, str]] = None
    ) -> Generator[None, None, None]:
        """Context manager to time a block of code.

        Args:
            labels: Optional labels

        Example:
            with histogram.time():
                do_something()
        """
        start = time.time()
        try:
            yield
        finally:
            self.observe(time.time() - start, labels)

    def get_buckets(
        self, labels: Optional[dict[str, str]] = None
    ) -> dict[float, int]:
        """Get bucket counts.

        Args:
            labels: Optional labels to filter by

        Returns:
            Dict of bucket boundary to count
        """
        label_key = tuple(sorted((labels or {}).items()))
        return self._counts.get(label_key, {})

    def get_sum(self, labels: Optional[dict[str, str]] = None) -> float:
        """Get sum of all observations.

        Args:
            labels: Optional labels to filter by

        Returns:
            Sum of all values
        """
        label_key = tuple(sorted((labels or {}).items()))
        return self._sums.get(label_key, 0.0)

    def get_count(self, labels: Optional[dict[str, str]] = None) -> int:
        """Get total count of observations.

        Args:
            labels: Optional labels to filter by

        Returns:
            Total count
        """
        label_key = tuple(sorted((labels or {}).items()))
        return self._totals.get(label_key, 0)


class MetricsRegistry:
    """Central registry for all metrics.

    Example:
        registry = MetricsRegistry()
        counter = registry.counter("requests_total", "Total requests")
        counter.inc()

        # Get all metrics
        for metric in registry.collect():
            print(metric)
    """

    _instance: Optional["MetricsRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsRegistry":
        """Singleton pattern for global registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize metrics registry."""
        if self._initialized:
            return

        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._initialized = True

        logger.debug("MetricsRegistry initialized")

    def counter(self, name: str, description: str = "") -> Counter:
        """Get or create a counter.

        Args:
            name: Metric name
            description: Metric description

        Returns:
            Counter instance
        """
        if name not in self._counters:
            self._counters[name] = Counter(name, description)
        return self._counters[name]

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Get or create a gauge.

        Args:
            name: Metric name
            description: Metric description

        Returns:
            Gauge instance
        """
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description)
        return self._gauges[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple[float, ...]] = None,
    ) -> Histogram:
        """Get or create a histogram.

        Args:
            name: Metric name
            description: Metric description
            buckets: Optional bucket boundaries

        Returns:
            Histogram instance
        """
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, description, buckets)
        return self._histograms[name]

    def collect(self) -> dict[str, Any]:
        """Collect all metrics.

        Returns:
            Dict of all metric values
        """
        result: dict[str, Any] = {
            "counters": {},
            "gauges": {},
            "histograms": {},
        }

        for name, counter in self._counters.items():
            result["counters"][name] = {
                "description": counter.description,
                "values": counter.get_all(),
            }

        for name, gauge in self._gauges.items():
            result["gauges"][name] = {
                "description": gauge.description,
                "values": gauge.get_all(),
            }

        for name, histogram in self._histograms.items():
            result["histograms"][name] = {
                "description": histogram.description,
                "buckets": histogram._buckets,
                "values": [
                    {
                        "labels": dict(label_key),
                        "buckets": histogram._counts.get(label_key, {}),
                        "sum": histogram._sums.get(label_key, 0),
                        "count": histogram._totals.get(label_key, 0),
                    }
                    for label_key in histogram._counts.keys()
                ],
            }

        return result

    def reset_all(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        self._gauges.clear()
        self._histograms.clear()


# Global registry instance
_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry.

    Returns:
        Global MetricsRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


# Pre-defined metrics for AgentSH
class AgentSHMetrics:
    """Pre-defined metrics for AgentSH components."""

    def __init__(self, registry: Optional[MetricsRegistry] = None) -> None:
        """Initialize AgentSH metrics.

        Args:
            registry: Optional metrics registry (uses global if not provided)
        """
        self.registry = registry or get_metrics_registry()

        # Tool metrics
        self.tool_executions_total = self.registry.counter(
            "agentsh_tool_executions_total",
            "Total number of tool executions",
        )
        self.tool_duration_seconds = self.registry.histogram(
            "agentsh_tool_duration_seconds",
            "Tool execution duration in seconds",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
        )
        self.tool_errors_total = self.registry.counter(
            "agentsh_tool_errors_total",
            "Total number of tool execution errors",
        )

        # LLM metrics
        self.llm_requests_total = self.registry.counter(
            "agentsh_llm_requests_total",
            "Total number of LLM requests",
        )
        self.llm_tokens_in_total = self.registry.counter(
            "agentsh_llm_tokens_in_total",
            "Total input tokens to LLM",
        )
        self.llm_tokens_out_total = self.registry.counter(
            "agentsh_llm_tokens_out_total",
            "Total output tokens from LLM",
        )
        self.llm_latency_seconds = self.registry.histogram(
            "agentsh_llm_latency_seconds",
            "LLM request latency in seconds",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )
        self.llm_errors_total = self.registry.counter(
            "agentsh_llm_errors_total",
            "Total number of LLM errors",
        )

        # Workflow metrics
        self.workflow_executions_total = self.registry.counter(
            "agentsh_workflow_executions_total",
            "Total number of workflow executions",
        )
        self.workflow_steps_total = self.registry.counter(
            "agentsh_workflow_steps_total",
            "Total number of workflow steps executed",
        )
        self.workflow_duration_seconds = self.registry.histogram(
            "agentsh_workflow_duration_seconds",
            "Workflow execution duration in seconds",
            buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
        )

        # Approval metrics
        self.approvals_requested_total = self.registry.counter(
            "agentsh_approvals_requested_total",
            "Total number of approval requests",
        )
        self.approvals_granted_total = self.registry.counter(
            "agentsh_approvals_granted_total",
            "Total number of approvals granted",
        )
        self.approvals_denied_total = self.registry.counter(
            "agentsh_approvals_denied_total",
            "Total number of approvals denied",
        )

        # Session metrics
        self.active_sessions = self.registry.gauge(
            "agentsh_active_sessions",
            "Number of active sessions",
        )
        self.sessions_total = self.registry.counter(
            "agentsh_sessions_total",
            "Total number of sessions created",
        )

        # Memory metrics
        self.memory_operations_total = self.registry.counter(
            "agentsh_memory_operations_total",
            "Total number of memory operations",
        )
        self.memory_records_total = self.registry.gauge(
            "agentsh_memory_records_total",
            "Total number of memory records",
        )

        # Security metrics
        self.security_blocks_total = self.registry.counter(
            "agentsh_security_blocks_total",
            "Total number of security blocks",
        )
        self.security_alerts_total = self.registry.counter(
            "agentsh_security_alerts_total",
            "Total number of security alerts",
        )

        # Error metrics
        self.errors_total = self.registry.counter(
            "agentsh_errors_total",
            "Total number of errors",
        )

    def record_tool_execution(
        self,
        tool_name: str,
        duration_seconds: float,
        success: bool,
    ) -> None:
        """Record a tool execution.

        Args:
            tool_name: Name of the tool
            duration_seconds: Execution duration
            success: Whether execution succeeded
        """
        labels = {"tool": tool_name}
        self.tool_executions_total.inc(labels=labels)
        self.tool_duration_seconds.observe(duration_seconds, labels=labels)
        if not success:
            self.tool_errors_total.inc(labels=labels)

    def record_llm_request(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_seconds: float,
        success: bool,
    ) -> None:
        """Record an LLM request.

        Args:
            provider: LLM provider name
            model: Model name
            tokens_in: Input tokens
            tokens_out: Output tokens
            latency_seconds: Request latency
            success: Whether request succeeded
        """
        labels = {"provider": provider, "model": model}
        self.llm_requests_total.inc(labels=labels)
        self.llm_tokens_in_total.inc(tokens_in, labels=labels)
        self.llm_tokens_out_total.inc(tokens_out, labels=labels)
        self.llm_latency_seconds.observe(latency_seconds, labels=labels)
        if not success:
            self.llm_errors_total.inc(labels=labels)

    def record_workflow_execution(
        self,
        workflow_name: str,
        steps: int,
        duration_seconds: float,
        success: bool,
    ) -> None:
        """Record a workflow execution.

        Args:
            workflow_name: Name of the workflow
            steps: Number of steps executed
            duration_seconds: Total duration
            success: Whether workflow succeeded
        """
        labels = {"workflow": workflow_name, "status": "success" if success else "failed"}
        self.workflow_executions_total.inc(labels=labels)
        self.workflow_steps_total.inc(steps, labels={"workflow": workflow_name})
        self.workflow_duration_seconds.observe(duration_seconds, labels=labels)


# Global metrics instance
_metrics: Optional[AgentSHMetrics] = None


def get_metrics() -> AgentSHMetrics:
    """Get the global AgentSH metrics instance.

    Returns:
        Global AgentSHMetrics singleton
    """
    global _metrics
    if _metrics is None:
        _metrics = AgentSHMetrics()
    return _metrics
