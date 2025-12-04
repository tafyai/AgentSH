"""Tests for telemetry event system."""

import asyncio
from datetime import datetime

import pytest

from agentsh.telemetry.events import (
    EventEmitter,
    EventType,
    TelemetryEvent,
    command_executed_event,
    emit_event,
    get_event_emitter,
    llm_event,
    security_event,
    tool_called_event,
    tool_completed_event,
    workflow_event,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self):
        """Should have all expected event types."""
        assert EventType.COMMAND_RECEIVED
        assert EventType.COMMAND_EXECUTED
        assert EventType.TOOL_CALLED
        assert EventType.TOOL_COMPLETED
        assert EventType.WORKFLOW_STARTED
        assert EventType.LLM_REQUEST
        assert EventType.SECURITY_ALERT

    def test_event_type_values(self):
        """Event types should have string values."""
        assert EventType.COMMAND_EXECUTED.value == "command_executed"
        assert EventType.TOOL_CALLED.value == "tool_called"


class TestTelemetryEvent:
    """Tests for TelemetryEvent dataclass."""

    def test_create_event(self):
        """Should create event with required fields."""
        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)

    def test_create_event_with_data(self):
        """Should create event with optional data."""
        event = TelemetryEvent(
            event_type=EventType.TOOL_CALLED,
            session_id="session-123",
            user_id="user-456",
            data={"tool": "shell.run"},
            metadata={"source": "test"},
        )
        assert event.session_id == "session-123"
        assert event.user_id == "user-456"
        assert event.data["tool"] == "shell.run"
        assert event.metadata["source"] == "test"

    def test_to_dict(self):
        """Should convert event to dictionary."""
        event = TelemetryEvent(
            event_type=EventType.COMMAND_EXECUTED,
            session_id="s1",
            data={"command": "ls"},
        )
        d = event.to_dict()
        assert d["event_type"] == "command_executed"
        assert d["session_id"] == "s1"
        assert d["data"]["command"] == "ls"
        assert "timestamp" in d
        assert "event_id" in d


class TestEventEmitter:
    """Tests for EventEmitter."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh event emitter."""
        emitter = EventEmitter()
        emitter.clear_handlers()  # Clear any existing handlers
        return emitter

    def test_subscribe_and_emit(self, emitter):
        """Should deliver events to subscribed handlers."""
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe(EventType.COMMAND_EXECUTED, handler)
        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        emitter.emit(event)

        assert len(received) == 1
        assert received[0] is event

    def test_subscribe_to_all_events(self, emitter):
        """Should receive all events when subscribing to None."""
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe(None, handler)

        emitter.emit(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        emitter.emit(TelemetryEvent(event_type=EventType.TOOL_CALLED))

        assert len(received) == 2

    def test_unsubscribe(self, emitter):
        """Should stop receiving events after unsubscribe."""
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe(EventType.COMMAND_EXECUTED, handler)
        emitter.emit(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        assert len(received) == 1

        emitter.unsubscribe(EventType.COMMAND_EXECUTED, handler)
        emitter.emit(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        assert len(received) == 1  # No new events

    def test_handler_exception_does_not_stop_other_handlers(self, emitter):
        """Handler exception should not prevent other handlers."""
        received = []

        def bad_handler(event):
            raise ValueError("test error")

        def good_handler(event):
            received.append(event)

        emitter.subscribe(EventType.COMMAND_EXECUTED, bad_handler)
        emitter.subscribe(EventType.COMMAND_EXECUTED, good_handler)

        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        emitter.emit(event)  # Should not raise

        assert len(received) == 1

    def test_clear_handlers(self, emitter):
        """Should remove all handlers."""
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe(EventType.COMMAND_EXECUTED, handler)
        emitter.subscribe(None, handler)
        emitter.clear_handlers()

        emitter.emit(TelemetryEvent(event_type=EventType.COMMAND_EXECUTED))
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_emit_async(self, emitter):
        """Should emit events asynchronously."""
        received = []

        async def async_handler(event):
            await asyncio.sleep(0.001)
            received.append(event)

        emitter.subscribe_async(EventType.TOOL_CALLED, async_handler)

        event = TelemetryEvent(event_type=EventType.TOOL_CALLED)
        await emitter.emit_async(event)

        assert len(received) == 1


class TestEventEmitterSingleton:
    """Tests for EventEmitter singleton behavior."""

    def test_get_event_emitter_singleton(self):
        """Should return the same instance."""
        emitter1 = get_event_emitter()
        emitter2 = get_event_emitter()
        assert emitter1 is emitter2


class TestEventFactoryFunctions:
    """Tests for event factory functions."""

    def test_emit_event(self):
        """Should create and emit event."""
        emitter = get_event_emitter()
        received = []

        def handler(event):
            received.append(event)

        emitter.subscribe(EventType.ERROR, handler)

        event = emit_event(
            EventType.ERROR,
            data={"message": "test error"},
            session_id="s1",
        )

        assert event.event_type == EventType.ERROR
        assert event.data["message"] == "test error"
        assert len(received) >= 1

        emitter.unsubscribe(EventType.ERROR, handler)

    def test_command_executed_event(self):
        """Should create command executed event."""
        event = command_executed_event(
            command="ls -la",
            exit_code=0,
            duration_ms=150,
            session_id="s1",
        )
        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.data["command"] == "ls -la"
        assert event.data["exit_code"] == 0
        assert event.data["duration_ms"] == 150

    def test_tool_called_event(self):
        """Should create tool called event."""
        event = tool_called_event(
            tool_name="shell.run",
            arguments={"command": "pwd"},
            session_id="s1",
        )
        assert event.event_type == EventType.TOOL_CALLED
        assert event.data["tool_name"] == "shell.run"
        assert event.data["arguments"]["command"] == "pwd"

    def test_tool_completed_event_success(self):
        """Should create successful tool completed event."""
        event = tool_completed_event(
            tool_name="shell.run",
            success=True,
            duration_ms=100,
            result_preview="/home/user",
        )
        assert event.event_type == EventType.TOOL_COMPLETED
        assert event.data["success"] is True

    def test_tool_completed_event_failure(self):
        """Should create failed tool event."""
        event = tool_completed_event(
            tool_name="shell.run",
            success=False,
            duration_ms=50,
        )
        assert event.event_type == EventType.TOOL_FAILED
        assert event.data["success"] is False

    def test_workflow_event(self):
        """Should create workflow event."""
        event = workflow_event(
            event_type=EventType.WORKFLOW_STARTED,
            workflow_id="wf-123",
            step=1,
            total_steps=5,
            status="running",
        )
        assert event.event_type == EventType.WORKFLOW_STARTED
        assert event.data["workflow_id"] == "wf-123"
        assert event.data["step"] == 1

    def test_llm_event(self):
        """Should create LLM event."""
        event = llm_event(
            event_type=EventType.LLM_RESPONSE,
            provider="anthropic",
            model="claude-3",
            tokens_in=100,
            tokens_out=500,
            duration_ms=2000,
        )
        assert event.event_type == EventType.LLM_RESPONSE
        assert event.data["provider"] == "anthropic"
        assert event.data["tokens_in"] == 100
        assert event.data["tokens_out"] == 500

    def test_security_event(self):
        """Should create security event."""
        event = security_event(
            event_type=EventType.SECURITY_ALERT,
            command="rm -rf /",
            risk_level="critical",
            action="blocked",
            reasons=["Dangerous command", "Affects root filesystem"],
        )
        assert event.event_type == EventType.SECURITY_ALERT
        assert event.data["risk_level"] == "critical"
        assert event.data["action"] == "blocked"
        assert len(event.data["reasons"]) == 2
