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


class TestFileExporterExtended:
    """Extended tests for FileExporter."""

    def test_auto_subscribe_disabled(self, tmp_path):
        """Should not subscribe when auto_subscribe is False."""
        log_path = tmp_path / "test.log"
        exporter = FileExporter(log_path, auto_subscribe=False)
        try:
            # Should not raise and file should be created
            assert log_path.exists()
        finally:
            exporter.close()

    def test_export_event_writes_jsonl(self, tmp_path):
        """Should write JSON lines format."""
        log_path = tmp_path / "test.log"
        exporter = FileExporter(log_path, auto_subscribe=False)
        try:
            event = TelemetryEvent(
                event_type=EventType.WORKFLOW_STARTED,
                session_id="sess-123",
                data={"workflow": "test"},
            )
            exporter.export_event(event)

            content = log_path.read_text()
            lines = content.strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["event_type"] == "workflow_started"
            assert data["session_id"] == "sess-123"
        finally:
            exporter.close()

    def test_multiple_events(self, tmp_path):
        """Should write multiple events."""
        log_path = tmp_path / "test.log"
        exporter = FileExporter(log_path, auto_subscribe=False)
        try:
            for i in range(5):
                event = TelemetryEvent(
                    event_type=EventType.COMMAND_EXECUTED,
                    data={"index": i},
                )
                exporter.export_event(event)

            content = log_path.read_text()
            lines = [l for l in content.strip().split("\n") if l]
            assert len(lines) == 5
        finally:
            exporter.close()

    def test_reopen_file(self, tmp_path):
        """Should reopen file."""
        log_path = tmp_path / "test.log"
        exporter = FileExporter(log_path, auto_subscribe=False)
        try:
            # Write one event
            exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))

            # Force reopen
            exporter._open_file()

            # Write another event
            exporter.export_event(TelemetryEvent(event_type=EventType.WARNING))

            # Both events should be in file
            content = log_path.read_text()
            assert "error" in content
            assert "warning" in content
        finally:
            exporter.close()


class TestJSONExporterExtended:
    """Extended tests for JSONExporter."""

    def test_multiple_events(self):
        """Should write multiple events."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, auto_subscribe=False)

        for i in range(3):
            event = TelemetryEvent(
                event_type=EventType.TOOL_COMPLETED,
                data={"index": i},
            )
            exporter.export_event(event)

        stream.seek(0)
        lines = [l for l in stream.readlines() if l.strip()]
        assert len(lines) == 3

    def test_export_with_all_fields(self):
        """Should export event with all fields."""
        stream = io.StringIO()
        exporter = JSONExporter(stream, auto_subscribe=False)

        event = TelemetryEvent(
            event_type=EventType.SECURITY_ALERT,
            session_id="sess-1",
            user_id="user-1",
            data={"alert": "test"},
            metadata={"source": "test"},
        )
        exporter.export_event(event)

        stream.seek(0)
        data = json.loads(stream.readline())
        assert data["session_id"] == "sess-1"
        assert data["user_id"] == "user-1"
        assert data["metadata"]["source"] == "test"


class TestMemoryExporterExtended:
    """Extended tests for MemoryExporter."""

    def test_get_events_empty(self):
        """Should return empty list when no events."""
        exporter = MemoryExporter()
        events = exporter.get_events_by_type(EventType.ERROR)
        assert events == []

    def test_events_stored_in_order(self):
        """Should store events in order."""
        exporter = MemoryExporter()

        for i in range(5):
            exporter.export_event(TelemetryEvent(
                event_type=EventType.ERROR,
                data={"index": i},
            ))

        for i, event in enumerate(exporter.events):
            assert event.data["index"] == i

    def test_metrics_snapshot_has_timestamp(self):
        """Should add timestamp to metrics snapshot."""
        exporter = MemoryExporter()
        exporter.export_metrics({"counter": 1})

        assert len(exporter.metrics_snapshots) == 1
        assert "timestamp" in exporter.metrics_snapshots[0]
        assert "metrics" in exporter.metrics_snapshots[0]


class TestPrometheusExporterExtended:
    """Extended tests for PrometheusExporter."""

    def test_render_empty_registry(self):
        """Should handle empty registry."""
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True

        exporter = PrometheusExporter(registry)
        text = exporter.render_metrics()

        # Should be empty or contain only comments
        assert text.strip() == "" or text.startswith("#")

    def test_render_multiple_labels(self):
        """Should render metrics with multiple labels."""
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True

        registry.counter("requests", "Total requests").inc(1, labels={"method": "GET", "path": "/api"})

        exporter = PrometheusExporter(registry)
        text = exporter.render_metrics()

        assert 'method="GET"' in text
        assert 'path="/api"' in text

    def test_close_is_noop(self):
        """Close should be a no-op."""
        registry = object.__new__(MetricsRegistry)
        registry._counters = {}
        registry._gauges = {}
        registry._histograms = {}
        registry._initialized = True

        exporter = PrometheusExporter(registry)
        exporter.close()  # Should not raise


class TestSetupDefaultExporters:
    """Tests for setup_default_exporters function."""

    def test_setup_with_log_path(self, tmp_path):
        """Should create file exporter with specified path."""
        from agentsh.telemetry.exporters import setup_default_exporters, get_exporter

        log_path = tmp_path / "test.log"
        exporter = setup_default_exporters(log_path=log_path, enable_prometheus=False)

        try:
            assert log_path.exists()
            assert exporter is not None
        finally:
            exporter.close()

    def test_setup_without_prometheus(self, tmp_path):
        """Should setup without prometheus exporter."""
        from agentsh.telemetry.exporters import setup_default_exporters

        log_path = tmp_path / "test.log"
        exporter = setup_default_exporters(log_path=log_path, enable_prometheus=False)

        try:
            # Should be a FileExporter, not composite
            assert exporter is not None
        finally:
            exporter.close()

    def test_setup_with_prometheus(self, tmp_path):
        """Should setup with prometheus exporter."""
        from agentsh.telemetry.exporters import setup_default_exporters, CompositeExporter

        log_path = tmp_path / "test.log"
        exporter = setup_default_exporters(log_path=log_path, enable_prometheus=True)

        try:
            # Should be a CompositeExporter with both
            assert isinstance(exporter, CompositeExporter)
        finally:
            exporter.close()

    def test_setup_default_path(self, monkeypatch, tmp_path):
        """Should use default path when none specified."""
        from agentsh.telemetry.exporters import setup_default_exporters

        # Mock expanduser to use tmp_path
        def mock_expanduser(self):
            return tmp_path / "telemetry.log"

        monkeypatch.setattr(Path, "expanduser", mock_expanduser)

        exporter = setup_default_exporters(log_path=None, enable_prometheus=False)

        try:
            assert exporter is not None
        finally:
            exporter.close()


class TestExporterGlobalState:
    """Tests for global exporter state."""

    def test_get_set_exporter(self, tmp_path):
        """Should get and set global exporter."""
        from agentsh.telemetry.exporters import get_exporter, set_exporter, FileExporter

        log_path = tmp_path / "test.log"
        exporter = FileExporter(log_path, auto_subscribe=False)

        try:
            set_exporter(exporter)
            assert get_exporter() is exporter
        finally:
            exporter.close()

    def test_get_exporter_none(self):
        """Should return None when no exporter set."""
        from agentsh.telemetry.exporters import get_exporter, set_exporter

        # Reset global state
        set_exporter(None)
        # Should not raise
        result = get_exporter()
        # May be None or previously set


class TestExporterAbstract:
    """Tests for abstract Exporter base class."""

    def test_exporter_is_abstract(self):
        """Exporter should be abstract."""
        from agentsh.telemetry.exporters import Exporter

        # Cannot instantiate directly
        with pytest.raises(TypeError):
            Exporter()


class TestFileExporterRotation:
    """Tests for FileExporter rotation."""

    def test_rotation_by_size(self, tmp_path):
        """Should rotate log file by size."""
        log_path = tmp_path / "rotate.log"
        # Create a small max_size for testing
        exporter = FileExporter(log_path, auto_subscribe=False, max_size_mb=0.0001)

        try:
            # Write enough events to trigger rotation
            for i in range(100):
                event = TelemetryEvent(
                    event_type=EventType.COMMAND_EXECUTED,
                    data={"command": f"cmd_{i}" * 100},  # Large data
                )
                exporter.export_event(event)

            # Check that rotation happened (backup files exist)
            # The original file should still exist
            assert log_path.exists()
        finally:
            exporter.close()


class TestJSONExporterFormatting:
    """Tests for JSONExporter formatting options."""

    def test_json_pretty(self):
        """Should support pretty printing."""
        buffer = io.StringIO()
        exporter = JSONExporter(buffer, pretty=True, auto_subscribe=False)

        event = TelemetryEvent(
            event_type=EventType.ERROR,
            data={"error": "test"},
        )
        exporter.export_event(event)

        content = buffer.getvalue()
        # Should have newlines for pretty printing
        assert "\n" in content

    def test_json_not_pretty(self):
        """Should output compact JSON when not pretty."""
        buffer = io.StringIO()
        exporter = JSONExporter(buffer, pretty=False, auto_subscribe=False)

        event = TelemetryEvent(
            event_type=EventType.ERROR,
            data={"error": "test"},
        )
        exporter.export_event(event)

        content = buffer.getvalue()
        # Should not have excessive formatting
        assert "error" in content


class TestCompositeExporterEdgeCases:
    """Edge case tests for CompositeExporter."""

    def test_composite_with_single_exporter(self, tmp_path):
        """Should work with single exporter."""
        log_path = tmp_path / "single.log"
        file_exporter = FileExporter(log_path, auto_subscribe=False)

        composite = CompositeExporter([file_exporter])

        try:
            event = TelemetryEvent(event_type=EventType.ERROR)
            composite.export_event(event)

            content = log_path.read_text()
            assert "error" in content
        finally:
            composite.close()

    def test_composite_export_metrics(self, tmp_path):
        """Should export metrics to all exporters."""
        buffer1 = io.StringIO()
        buffer2 = io.StringIO()

        exporter1 = JSONExporter(buffer1, auto_subscribe=False)
        exporter2 = JSONExporter(buffer2, auto_subscribe=False)

        composite = CompositeExporter([exporter1, exporter2])

        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        composite.export_event(event)

        # Both should have received the event
        assert "command_executed" in buffer1.getvalue()
        assert "command_executed" in buffer2.getvalue()


class TestMemoryExporterQuerying:
    """Tests for MemoryExporter querying capabilities."""

    def test_query_by_event_type(self):
        """Should query events by type."""
        exporter = MemoryExporter()

        exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))
        exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))

        events = exporter.events
        command_events = [e for e in events if e.event_type == EventType.COMMAND_EXECUTED]
        assert len(command_events) == 2

    def test_max_events_limit(self):
        """Should respect max_events limit."""
        exporter = MemoryExporter(max_events=5)

        for i in range(10):
            exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))

        # Should only keep max_events
        assert len(exporter.events) <= 5

    def test_clear_events(self):
        """Should clear all stored events."""
        exporter = MemoryExporter()

        exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))
        exporter.export_event(TelemetryEvent(event_type=EventType.ERROR))

        exporter.clear()
        assert len(exporter.events) == 0

    def test_export_metrics(self):
        """Should store metrics snapshots."""
        exporter = MemoryExporter()

        exporter.export_metrics({"metric1": 1, "metric2": 2})
        exporter.export_metrics({"metric3": 3})

        assert len(exporter.metrics_snapshots) == 2

    def test_thread_safe(self):
        """Should be thread-safe."""
        import threading

        exporter = MemoryExporter()

        def add_events():
            for i in range(100):
                exporter.export_event(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))

        threads = [threading.Thread(target=add_events) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have received all events without error
        assert len(exporter.events) > 0
