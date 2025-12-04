"""Telemetry and monitoring for AgentSH.

This module provides comprehensive telemetry capabilities including:
- Structured logging with context binding
- Event-driven telemetry with pub/sub pattern
- Prometheus-style metrics (counters, gauges, histograms)
- Multiple export backends (file, JSON, Prometheus)
- Health checking for system components
"""

from agentsh.telemetry.events import (
    EventEmitter,
    EventType,
    TelemetryEvent,
    command_executed_event,
    emit_event,
    emit_event_async,
    get_event_emitter,
    llm_event,
    security_event,
    tool_called_event,
    tool_completed_event,
    workflow_event,
)
from agentsh.telemetry.exporters import (
    CompositeExporter,
    Exporter,
    FileExporter,
    JSONExporter,
    MemoryExporter,
    PrometheusExporter,
    get_exporter,
    set_exporter,
    setup_default_exporters,
)
from agentsh.telemetry.health import (
    HealthChecker,
    HealthResult,
    HealthStatus,
    OverallHealth,
    check_health,
    check_health_async,
    get_health_checker,
)
from agentsh.telemetry.logger import (
    LoggerMixin,
    bind_context,
    get_logger,
    setup_logging,
)
from agentsh.telemetry.metrics import (
    AgentSHMetrics,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_metrics,
    get_metrics_registry,
)

__all__ = [
    # Logger
    "setup_logging",
    "get_logger",
    "bind_context",
    "LoggerMixin",
    # Events
    "EventType",
    "TelemetryEvent",
    "EventEmitter",
    "get_event_emitter",
    "emit_event",
    "emit_event_async",
    "command_executed_event",
    "tool_called_event",
    "tool_completed_event",
    "workflow_event",
    "llm_event",
    "security_event",
    # Metrics
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "get_metrics_registry",
    "AgentSHMetrics",
    "get_metrics",
    # Exporters
    "Exporter",
    "FileExporter",
    "JSONExporter",
    "PrometheusExporter",
    "MemoryExporter",
    "CompositeExporter",
    "get_exporter",
    "set_exporter",
    "setup_default_exporters",
    # Health
    "HealthStatus",
    "HealthResult",
    "OverallHealth",
    "HealthChecker",
    "get_health_checker",
    "check_health",
    "check_health_async",
]
