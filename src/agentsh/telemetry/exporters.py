"""Telemetry exporters for AgentSH.

Provides various backends for exporting telemetry data including
file-based logging, JSON output, and Prometheus format.
"""

import json
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TextIO

from agentsh.telemetry.events import EventType, TelemetryEvent, get_event_emitter
from agentsh.telemetry.logger import get_logger
from agentsh.telemetry.metrics import MetricsRegistry, get_metrics_registry

logger = get_logger(__name__)


class Exporter(ABC):
    """Abstract base class for telemetry exporters."""

    @abstractmethod
    def export_event(self, event: TelemetryEvent) -> None:
        """Export a single event.

        Args:
            event: Event to export
        """
        pass

    @abstractmethod
    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics snapshot.

        Args:
            metrics: Metrics data from registry.collect()
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the exporter and release resources."""
        pass


class FileExporter(Exporter):
    """Exports telemetry to log files.

    Writes events as JSON lines to a file with automatic rotation.

    Example:
        exporter = FileExporter(Path("~/.agentsh/telemetry.log"))
        exporter.export_event(event)
    """

    def __init__(
        self,
        log_path: Path,
        max_size_mb: float = 10.0,
        max_files: int = 5,
        auto_subscribe: bool = True,
    ) -> None:
        """Initialize file exporter.

        Args:
            log_path: Path to log file
            max_size_mb: Maximum file size before rotation
            max_files: Maximum number of rotated files to keep
            auto_subscribe: Automatically subscribe to events
        """
        self.log_path = Path(log_path).expanduser()
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.max_files = max_files
        self._file: Optional[TextIO] = None
        self._lock = threading.Lock()

        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file
        self._open_file()

        # Subscribe to events
        if auto_subscribe:
            get_event_emitter().subscribe(None, self.export_event)

        logger.info("FileExporter initialized", path=str(self.log_path))

    def _open_file(self) -> None:
        """Open or reopen the log file."""
        if self._file:
            self._file.close()
        self._file = open(self.log_path, "a", encoding="utf-8")

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.log_path.exists():
            return

        if self.log_path.stat().st_size < self.max_size_bytes:
            return

        # Close current file
        if self._file:
            self._file.close()

        # Rotate existing files
        for i in range(self.max_files - 1, 0, -1):
            old_path = self.log_path.with_suffix(f".{i}.log")
            new_path = self.log_path.with_suffix(f".{i + 1}.log")
            if old_path.exists():
                if i + 1 >= self.max_files:
                    old_path.unlink()
                else:
                    old_path.rename(new_path)

        # Rename current to .1
        if self.log_path.exists():
            self.log_path.rename(self.log_path.with_suffix(".1.log"))

        # Open new file
        self._open_file()

        logger.debug("Log file rotated", path=str(self.log_path))

    def export_event(self, event: TelemetryEvent) -> None:
        """Export an event to the log file.

        Args:
            event: Event to export
        """
        with self._lock:
            self._rotate_if_needed()

            if self._file:
                line = json.dumps(event.to_dict(), default=str)
                self._file.write(line + "\n")
                self._file.flush()

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics snapshot to the log file.

        Args:
            metrics: Metrics data
        """
        with self._lock:
            self._rotate_if_needed()

            if self._file:
                record = {
                    "type": "metrics_snapshot",
                    "timestamp": datetime.now().isoformat(),
                    "metrics": metrics,
                }
                line = json.dumps(record, default=str)
                self._file.write(line + "\n")
                self._file.flush()

    def close(self) -> None:
        """Close the file exporter."""
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class JSONExporter(Exporter):
    """Exports telemetry as JSON to stdout or a stream.

    Useful for piping to other tools or debugging.

    Example:
        exporter = JSONExporter(sys.stdout)
        exporter.export_event(event)
    """

    def __init__(
        self,
        stream: TextIO,
        pretty: bool = False,
        auto_subscribe: bool = False,
    ) -> None:
        """Initialize JSON exporter.

        Args:
            stream: Output stream (e.g., sys.stdout)
            pretty: Whether to pretty-print JSON
            auto_subscribe: Automatically subscribe to events
        """
        self.stream = stream
        self.pretty = pretty
        self._lock = threading.Lock()

        if auto_subscribe:
            get_event_emitter().subscribe(None, self.export_event)

    def export_event(self, event: TelemetryEvent) -> None:
        """Export an event as JSON.

        Args:
            event: Event to export
        """
        with self._lock:
            if self.pretty:
                json.dump(event.to_dict(), self.stream, indent=2, default=str)
                self.stream.write("\n")
            else:
                self.stream.write(json.dumps(event.to_dict(), default=str) + "\n")
            self.stream.flush()

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics as JSON.

        Args:
            metrics: Metrics data
        """
        with self._lock:
            record = {
                "type": "metrics",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
            }
            if self.pretty:
                json.dump(record, self.stream, indent=2, default=str)
                self.stream.write("\n")
            else:
                self.stream.write(json.dumps(record, default=str) + "\n")
            self.stream.flush()

    def close(self) -> None:
        """Close the JSON exporter (does not close the stream)."""
        pass


class PrometheusExporter(Exporter):
    """Exports metrics in Prometheus text format.

    Can be used to expose metrics via HTTP for Prometheus scraping.

    Example:
        exporter = PrometheusExporter()
        text = exporter.render_metrics()
        # Serve `text` at /metrics endpoint
    """

    def __init__(self, registry: Optional[MetricsRegistry] = None) -> None:
        """Initialize Prometheus exporter.

        Args:
            registry: Metrics registry (uses global if not provided)
        """
        self.registry = registry or get_metrics_registry()

    def export_event(self, event: TelemetryEvent) -> None:
        """Export an event (no-op for Prometheus).

        Prometheus is pull-based, so events are not exported directly.

        Args:
            event: Event (ignored)
        """
        pass

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics (no-op for Prometheus).

        Use render_metrics() instead for Prometheus format.

        Args:
            metrics: Metrics data (ignored)
        """
        pass

    def render_metrics(self) -> str:
        """Render metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics text
        """
        lines: list[str] = []
        metrics = self.registry.collect()

        # Counters
        for name, data in metrics["counters"].items():
            if data["description"]:
                lines.append(f"# HELP {name} {data['description']}")
            lines.append(f"# TYPE {name} counter")
            for labels, value in data["values"]:
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Gauges
        for name, data in metrics["gauges"].items():
            if data["description"]:
                lines.append(f"# HELP {name} {data['description']}")
            lines.append(f"# TYPE {name} gauge")
            for labels, value in data["values"]:
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Histograms
        for name, data in metrics["histograms"].items():
            if data["description"]:
                lines.append(f"# HELP {name} {data['description']}")
            lines.append(f"# TYPE {name} histogram")

            for value_data in data["values"]:
                labels = value_data["labels"]
                base_label_str = self._format_labels(labels)

                # Bucket lines
                for le, count in sorted(value_data["buckets"].items()):
                    le_str = "+Inf" if le == float("inf") else str(le)
                    bucket_labels = {**labels, "le": le_str}
                    label_str = self._format_labels(bucket_labels)
                    lines.append(f"{name}_bucket{label_str} {count}")

                # Sum and count
                lines.append(f"{name}_sum{base_label_str} {value_data['sum']}")
                lines.append(f"{name}_count{base_label_str} {value_data['count']}")

        return "\n".join(lines) + "\n"

    def _format_labels(self, labels: dict[str, str]) -> str:
        """Format labels for Prometheus.

        Args:
            labels: Label dict

        Returns:
            Formatted label string like {key="value",key2="value2"}
        """
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"

    def close(self) -> None:
        """Close the Prometheus exporter."""
        pass


class MemoryExporter(Exporter):
    """Exports telemetry to memory for testing.

    Example:
        exporter = MemoryExporter()
        exporter.export_event(event)
        assert len(exporter.events) == 1
    """

    def __init__(self, max_events: int = 1000) -> None:
        """Initialize memory exporter.

        Args:
            max_events: Maximum events to keep in memory
        """
        self.max_events = max_events
        self.events: list[TelemetryEvent] = []
        self.metrics_snapshots: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def export_event(self, event: TelemetryEvent) -> None:
        """Export an event to memory.

        Args:
            event: Event to store
        """
        with self._lock:
            self.events.append(event)
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics to memory.

        Args:
            metrics: Metrics data
        """
        with self._lock:
            self.metrics_snapshots.append({
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
            })

    def get_events_by_type(self, event_type: EventType) -> list[TelemetryEvent]:
        """Get events of a specific type.

        Args:
            event_type: Type to filter by

        Returns:
            List of matching events
        """
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear all stored events and metrics."""
        with self._lock:
            self.events.clear()
            self.metrics_snapshots.clear()

    def close(self) -> None:
        """Close the memory exporter."""
        self.clear()


class CompositeExporter(Exporter):
    """Combines multiple exporters into one.

    Example:
        composite = CompositeExporter([
            FileExporter(Path("telemetry.log")),
            PrometheusExporter(),
        ])
        composite.export_event(event)  # Exports to all
    """

    def __init__(self, exporters: list[Exporter]) -> None:
        """Initialize composite exporter.

        Args:
            exporters: List of exporters to combine
        """
        self.exporters = exporters

    def add_exporter(self, exporter: Exporter) -> None:
        """Add an exporter.

        Args:
            exporter: Exporter to add
        """
        self.exporters.append(exporter)

    def remove_exporter(self, exporter: Exporter) -> bool:
        """Remove an exporter.

        Args:
            exporter: Exporter to remove

        Returns:
            True if removed
        """
        try:
            self.exporters.remove(exporter)
            return True
        except ValueError:
            return False

    def export_event(self, event: TelemetryEvent) -> None:
        """Export an event to all exporters.

        Args:
            event: Event to export
        """
        for exporter in self.exporters:
            try:
                exporter.export_event(event)
            except Exception as e:
                logger.error(
                    "Exporter error",
                    exporter=type(exporter).__name__,
                    error=str(e),
                )

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        """Export metrics to all exporters.

        Args:
            metrics: Metrics data
        """
        for exporter in self.exporters:
            try:
                exporter.export_metrics(metrics)
            except Exception as e:
                logger.error(
                    "Exporter error",
                    exporter=type(exporter).__name__,
                    error=str(e),
                )

    def close(self) -> None:
        """Close all exporters."""
        for exporter in self.exporters:
            try:
                exporter.close()
            except Exception as e:
                logger.error(
                    "Error closing exporter",
                    exporter=type(exporter).__name__,
                    error=str(e),
                )


# Global exporter instance
_exporter: Optional[Exporter] = None


def get_exporter() -> Optional[Exporter]:
    """Get the global exporter instance.

    Returns:
        Global exporter or None if not configured
    """
    return _exporter


def set_exporter(exporter: Exporter) -> None:
    """Set the global exporter instance.

    Args:
        exporter: Exporter to use globally
    """
    global _exporter
    _exporter = exporter


def setup_default_exporters(
    log_path: Optional[Path] = None,
    enable_prometheus: bool = False,
) -> Exporter:
    """Set up default exporters for AgentSH.

    Args:
        log_path: Optional path for file logging
        enable_prometheus: Whether to enable Prometheus exporter

    Returns:
        Configured exporter (composite if multiple)
    """
    exporters: list[Exporter] = []

    if log_path:
        exporters.append(FileExporter(log_path, auto_subscribe=False))

    if enable_prometheus:
        exporters.append(PrometheusExporter())

    if not exporters:
        # Default to file exporter in ~/.agentsh
        default_path = Path("~/.agentsh/telemetry.log").expanduser()
        exporters.append(FileExporter(default_path, auto_subscribe=False))

    if len(exporters) == 1:
        exporter = exporters[0]
    else:
        exporter = CompositeExporter(exporters)

    # Subscribe to events
    get_event_emitter().subscribe(None, exporter.export_event)

    set_exporter(exporter)
    return exporter
