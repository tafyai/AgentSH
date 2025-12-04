"""Tests for telemetry exporters."""

import io
import json
import tempfile
from pathlib import Path

import pytest

from agentsh.telemetry.events import EventType, TelemetryEvent
from agentsh.telemetry.exporters import (
    CompositeExporter,
    FileExporter,
    JSONExporter,
    MemoryExporter,
    PrometheusExporter,
)
from agentsh.telemetry.metrics import MetricsRegistry


class TestFileExporter:
    """Tests for FileExporter."""

    @pytest.fixture
    def tmp_log_path(self, tmp_path):
        """Create a temporary log path."""
        return tmp_path / "telemetry.log"

    def test_create_exporter(self, tmp_log_path):
        """Should create exporter and log file."""
        exporter = FileExporter(tmp_log_path, auto_subscribe=False)
        try:
            assert tmp_log_path.exists()
        finally:
            exporter.close()

    def test_export_event(self, tmp_log_path):
        """Should export event as JSON line."""
        exporter = FileExporter(tmp_log_path, auto_subscribe=False)
        try:
            event = TelemetryEvent(
                event_type=EventType.COMMAND_EXECUTED,
                data={"command": "ls"},
            )
            exporter.export_event(event)

            # Read and verify
            content = tmp_log_path.read_text()
            line = json.loads(content.strip())
            assert line["event_type"] == "command_executed"
            assert line["data"]["command"] == "ls"
        finally:
            exporter.close()

    def test_export_metrics(self, tmp_log_path):
        """Should export metrics as JSON line."""
        exporter = FileExporter(tmp_log_path, auto_subscribe=False)
        try:
            metrics = {"counters": {"test": 1}}
            exporter.export_metrics(metrics)

            content = tmp_log_path.read_text()
            line = json.loads(content.strip())
            assert line["type"] == "metrics_snapshot"
            assert line["metrics"]["counters"]["test"] == 1
        finally:
            exporter.close()

    def test_rotation(self, tmp_log_path):
        """Should rotate files when max size exceeded."""
        # Create exporter with very small max size
        exporter = FileExporter(
            tmp_log_path,
            max_size_mb=0.0001,  # ~100 bytes
            max_files=3,
            auto_subscribe=False,
        )
        try:
            # Write enough to trigger rotation
            for i in range(10):
                event = TelemetryEvent(
                    event_type=EventType.COMMAND_EXECUTED,
                    data={"index": i, "padding": "x" * 100},
                )
                exporter.export_event(event)

            # Check for rotated files
            parent = tmp_log_path.parent
            log_files = list(parent.glob("*.log"))
            assert len(log_files) >= 1
        finally:
            exporter.close()

    def test_close(self, tmp_log_path):
        """Should close file handle."""
        exporter = FileExporter(tmp_log_path, auto_subscribe=False)
        exporter.close()
        assert exporter._file is None


class TestJSONExporter:
    """Tests for JSONExporter."""

    def test_export_event(self):
        """Should export event as JSON."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, auto_subscribe=False)

        event = TelemetryEvent(
            event_type=EventType.TOOL_CALLED,
            data={"tool": "shell.run"},
        )
        exporter.export_event(event)

        stream.seek(0)
        line = json.loads(stream.readline())
        assert line["event_type"] == "tool_called"
        assert line["data"]["tool"] == "shell.run"

    def test_export_event_pretty(self):
        """Should export pretty-printed JSON when enabled."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, pretty=True, auto_subscribe=False)

        event = TelemetryEvent(event_type=EventType.ERROR)
        exporter.export_event(event)

        stream.seek(0)
        content = stream.read()
        # Pretty print should have newlines within the JSON
        assert "\n" in content

    def test_export_metrics(self):
        """Should export metrics as JSON."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, auto_subscribe=False)

        exporter.export_metrics({"counters": {"c1": 5}})

        stream.seek(0)
        line = json.loads(stream.readline())
        assert line["type"] == "metrics"
        assert line["metrics"]["counters"]["c1"] == 5

    def test_close_does_not_close_stream(self):
        """Close should not close the underlying stream."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, auto_subscribe=False)
        exporter.close()

        # Stream should still be writable
        stream.write("test")


class TestPrometheusExporter:
    """Tests for PrometheusExporter."""

    @pytest.fixture
    def registry(self):
        """Create a metrics registry with test data."""
        # Create a non-singleton registry for testing
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True

        registry.counter("http_requests_total", "Total HTTP requests").inc(10, labels={"method": "GET"})
        registry.gauge("active_connections", "Active connections").set(5)
        registry.histogram("request_duration", "Request duration", buckets=(0.1, 0.5, 1.0)).observe(0.3)
        return registry

    def test_render_counter(self, registry):
        """Should render counter in Prometheus format."""
        exporter = PrometheusExporter(registry)
        text = exporter.render_metrics()

        assert "# HELP http_requests_total Total HTTP requests" in text
        assert "# TYPE http_requests_total counter" in text
        assert 'http_requests_total{method="GET"}' in text

    def test_render_gauge(self, registry):
        """Should render gauge in Prometheus format."""
        exporter = PrometheusExporter(registry)
        text = exporter.render_metrics()

        assert "# HELP active_connections Active connections" in text
        assert "# TYPE active_connections gauge" in text
        assert "active_connections" in text

    def test_render_histogram(self, registry):
        """Should render histogram in Prometheus format."""
        exporter = PrometheusExporter(registry)
        text = exporter.render_metrics()

        assert "# HELP request_duration Request duration" in text
        assert "# TYPE request_duration histogram" in text
        assert "request_duration_bucket" in text
        assert "request_duration_sum" in text
        assert "request_duration_count" in text

    def test_export_event_is_noop(self, registry):
        """Event export should be a no-op."""
        exporter = PrometheusExporter(registry)
        event = TelemetryEvent(event_type=EventType.ERROR)
        # Should not raise
        exporter.export_event(event)

    def test_export_metrics_is_noop(self, registry):
        """Metrics export should be a no-op (use render_metrics instead)."""
        exporter = PrometheusExporter(registry)
        # Should not raise
        exporter.export_metrics({"test": 1})


class TestMemoryExporter:
    """Tests for MemoryExporter."""

    def test_export_event(self):
        """Should store events in memory."""
        exporter = MemoryExporter()

        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        exporter.export_event(event)

        assert len(exporter.events) == 1
        assert exporter.events[0] is event

    def test_export_metrics(self):
        """Should store metrics snapshots in memory."""
        exporter = MemoryExporter()

        exporter.export_metrics({"counters": {"c1": 5}})

        assert len(exporter.metrics_snapshots) == 1
        assert exporter.metrics_snapshots[0]["metrics"]["counters"]["c1"] == 5

    def test_max_events_limit(self):
        """Should enforce max events limit."""
        exporter = MemoryExporter(max_events=5)

        for i in range(10):
            exporter.export_event(TelemetryEvent(event_type=EventType.ERROR, data={"i": i}))

        assert len(exporter.events) == 5
        # Should keep the most recent events
        assert exporter.events[0].data["i"] == 5

    def test_get_events_by_type(self):
        """Should filter events by type."""
        exporter = MemoryExporter()

        exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        exporter.export_event(TelemetryEvent(event_type=EventType.TOOL_CALLED))
        exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))

        commands = exporter.get_events_by_type(EventType.COMMAND_EXECUTED)
        assert len(commands) == 2

    def test_clear(self):
        """Should clear all stored data."""
        exporter = MemoryExporter()

        exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))
        exporter.export_metrics({"test": 1})

        exporter.clear()

        assert len(exporter.events) == 0
        assert len(exporter.metrics_snapshots) == 0

    def test_close_clears_data(self):
        """Close should clear stored data."""
        exporter = MemoryExporter()

        exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))
        exporter.close()

        assert len(exporter.events) == 0


class TestCompositeExporter:
    """Tests for CompositeExporter."""

    def test_export_event_to_all(self):
        """Should export event to all child exporters."""
        mem1 = MemoryExporter()
        mem2 = MemoryExporter()
        composite = CompositeExporter([mem1, mem2])

        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        composite.export_event(event)

        assert len(mem1.events) == 1
        assert len(mem2.events) == 1

    def test_export_metrics_to_all(self):
        """Should export metrics to all child exporters."""
        mem1 = MemoryExporter()
        mem2 = MemoryExporter()
        composite = CompositeExporter([mem1, mem2])

        composite.export_metrics({"test": 1})

        assert len(mem1.metrics_snapshots) == 1
        assert len(mem2.metrics_snapshots) == 1

    def test_add_exporter(self):
        """Should add exporters dynamically."""
        composite = CompositeExporter([])
        mem = MemoryExporter()
        composite.add_exporter(mem)

        event = TelemetryEvent(event_type=EventType.ERROR)
        composite.export_event(event)

        assert len(mem.events) == 1

    def test_remove_exporter(self):
        """Should remove exporters."""
        mem = MemoryExporter()
        composite = CompositeExporter([mem])

        assert composite.remove_exporter(mem) is True
        assert composite.remove_exporter(mem) is False  # Already removed

        composite.export_event(TelemetryEvent(event_type=EventType.ERROR))
        assert len(mem.events) == 0

    def test_exporter_error_does_not_stop_others(self):
        """Error in one exporter should not stop others."""
        class FailingExporter:
            def export_event(self, event):
                raise ValueError("test error")

            def export_metrics(self, metrics):
                raise ValueError("test error")

            def close(self):
                pass

        failing = FailingExporter()
        mem = MemoryExporter()
        composite = CompositeExporter([failing, mem])

        event = TelemetryEvent(event_type=EventType.ERROR)
        composite.export_event(event)  # Should not raise

        assert len(mem.events) == 1

    def test_close_all(self):
        """Should close all child exporters."""
        mem1 = MemoryExporter()
        mem2 = MemoryExporter()
        composite = CompositeExporter([mem1, mem2])

        mem1.export_event(TelemetryEvent(event_type=EventType.ERROR))
        mem2.export_event(TelemetryEvent(event_type=EventType.ERROR))

        composite.close()

        # MemoryExporter.close() clears events
        assert len(mem1.events) == 0
        assert len(mem2.events) == 0
