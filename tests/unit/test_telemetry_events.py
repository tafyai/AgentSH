"""Tests for telemetry events module."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from agentsh.telemetry.events import (
    EventType,
    TelemetryEvent,
    EventEmitter,
    get_event_emitter,
    emit_event,
    emit_event_async,
    command_executed_event,
    tool_called_event,
    tool_completed_event,
    workflow_event,
    llm_event,
    security_event,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self) -> None:
        """Should have expected event types."""
        assert EventType.COMMAND_EXECUTED.value == "command_executed"
        assert EventType.TOOL_CALLED.value == "tool_called"
        assert EventType.WORKFLOW_STARTED.value == "workflow_started"
        assert EventType.LLM_REQUEST.value == "llm_request"
        assert EventType.SECURITY_ALERT.value == "security_alert"
        assert EventType.SESSION_STARTED.value == "session_started"


class TestTelemetryEvent:
    """Tests for TelemetryEvent dataclass."""

    def test_create_event(self) -> None:
        """Should create event with required fields."""
        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)

        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.timestamp is not None
        assert event.event_id is not None
        assert len(event.event_id) > 0

    def test_create_event_with_data(self) -> None:
        """Should create event with data."""
        event = TelemetryEvent(
            event_type=EventType.TOOL_CALLED,
            data={"tool_name": "shell.run"},
            session_id="session-123",
            user_id="user-456",
            metadata={"extra": "info"},
        )

        assert event.data["tool_name"] == "shell.run"
        assert event.session_id == "session-123"
        assert event.user_id == "user-456"
        assert event.metadata["extra"] == "info"

    def test_to_dict(self) -> None:
        """Should convert event to dictionary."""
        event = TelemetryEvent(
            event_type=EventType.ERROR,
            data={"error": "Something failed"},
            session_id="sess-1",
        )

        d = event.to_dict()

        assert d["event_type"] == "error"
        assert "timestamp" in d
        assert d["session_id"] == "sess-1"
        assert d["data"]["error"] == "Something failed"


class TestEventEmitter:
    """Tests for EventEmitter class."""

    @pytest.fixture
    def emitter(self) -> EventEmitter:
        """Create a fresh event emitter."""
        # Reset singleton for testing
        EventEmitter._instance = None
        return EventEmitter()

    def test_singleton(self) -> None:
        """Should be singleton."""
        EventEmitter._instance = None
        emitter1 = EventEmitter()
        emitter2 = EventEmitter()
        assert emitter1 is emitter2

    def test_subscribe(self, emitter: EventEmitter) -> None:
        """Should subscribe handler to event type."""
        handler = MagicMock()
        emitter.subscribe(EventType.COMMAND_EXECUTED, handler)

        assert EventType.COMMAND_EXECUTED in emitter._handlers
        assert handler in emitter._handlers[EventType.COMMAND_EXECUTED]

    def test_subscribe_global(self, emitter: EventEmitter) -> None:
        """Should subscribe global handler."""
        handler = MagicMock()
        emitter.subscribe(None, handler)

        assert handler in emitter._global_handlers

    def test_subscribe_async(self, emitter: EventEmitter) -> None:
        """Should subscribe async handler."""
        async def async_handler(event):
            pass

        emitter.subscribe_async(EventType.TOOL_CALLED, async_handler)

        assert EventType.TOOL_CALLED in emitter._async_handlers
        assert async_handler in emitter._async_handlers[EventType.TOOL_CALLED]

    def test_subscribe_async_global(self, emitter: EventEmitter) -> None:
        """Should subscribe async global handler."""
        async def async_handler(event):
            pass

        emitter.subscribe_async(None, async_handler)

        assert async_handler in emitter._async_global_handlers

    def test_unsubscribe(self, emitter: EventEmitter) -> None:
        """Should unsubscribe handler."""
        handler = MagicMock()
        emitter.subscribe(EventType.ERROR, handler)

        result = emitter.unsubscribe(EventType.ERROR, handler)

        assert result is True
        assert handler not in emitter._handlers.get(EventType.ERROR, [])

    def test_unsubscribe_global(self, emitter: EventEmitter) -> None:
        """Should unsubscribe global handler."""
        handler = MagicMock()
        emitter.subscribe(None, handler)

        result = emitter.unsubscribe(None, handler)

        assert result is True
        assert handler not in emitter._global_handlers

    def test_unsubscribe_nonexistent(self, emitter: EventEmitter) -> None:
        """Should return False for non-existent handler."""
        handler = MagicMock()
        # Add a different handler first so we have handlers for this type
        other_handler = MagicMock()
        emitter.subscribe(EventType.ERROR, other_handler)
        # Then try to unsubscribe a handler that was never subscribed
        result = emitter.unsubscribe(EventType.ERROR, handler)
        assert result is False

    def test_emit(self, emitter: EventEmitter) -> None:
        """Should emit event to subscribers."""
        handler = MagicMock()
        emitter.subscribe(EventType.COMMAND_EXECUTED, handler)

        event = TelemetryEvent(event_type=EventType.COMMAND_EXECUTED)
        emitter.emit(event)

        handler.assert_called_once_with(event)

    def test_emit_global_handlers(self, emitter: EventEmitter) -> None:
        """Should call global handlers for any event."""
        handler = MagicMock()
        emitter.subscribe(None, handler)

        event = TelemetryEvent(event_type=EventType.WORKFLOW_STARTED)
        emitter.emit(event)

        handler.assert_called_once_with(event)

    def test_emit_handler_error(self, emitter: EventEmitter) -> None:
        """Should handle errors in event handlers."""
        def bad_handler(event):
            raise RuntimeError("Handler failed")

        good_called = False

        def good_handler(event):
            nonlocal good_called
            good_called = True

        emitter.subscribe(EventType.ERROR, bad_handler)
        emitter.subscribe(EventType.ERROR, good_handler)

        event = TelemetryEvent(event_type=EventType.ERROR)
        emitter.emit(event)  # Should not raise

        # Both handlers should be called despite error in first one
        assert good_called

    @pytest.mark.asyncio
    async def test_emit_async(self, emitter: EventEmitter) -> None:
        """Should emit event asynchronously."""
        handler = MagicMock()
        async_handler_called = False

        async def async_handler(event):
            nonlocal async_handler_called
            async_handler_called = True

        emitter.subscribe(EventType.LLM_REQUEST, handler)
        emitter.subscribe_async(EventType.LLM_REQUEST, async_handler)

        event = TelemetryEvent(event_type=EventType.LLM_REQUEST)
        await emitter.emit_async(event)

        handler.assert_called_once_with(event)
        assert async_handler_called

    @pytest.mark.asyncio
    async def test_emit_async_global(self, emitter: EventEmitter) -> None:
        """Should call async global handlers."""
        called = False

        async def async_global(event):
            nonlocal called
            called = True

        emitter.subscribe_async(None, async_global)

        event = TelemetryEvent(event_type=EventType.SESSION_STARTED)
        await emitter.emit_async(event)

        assert called

    @pytest.mark.asyncio
    async def test_emit_async_error_handling(self, emitter: EventEmitter) -> None:
        """Should handle errors in async handlers."""
        async def bad_handler(event):
            raise RuntimeError("Async handler failed")

        good_called = False

        async def good_handler(event):
            nonlocal good_called
            good_called = True

        emitter.subscribe_async(EventType.ERROR, bad_handler)
        emitter.subscribe_async(EventType.ERROR, good_handler)

        event = TelemetryEvent(event_type=EventType.ERROR)
        await emitter.emit_async(event)  # Should not raise

        assert good_called

    def test_clear_handlers_specific(self, emitter: EventEmitter) -> None:
        """Should clear handlers for specific event type."""
        handler1 = MagicMock()
        handler2 = MagicMock()

        emitter.subscribe(EventType.TOOL_CALLED, handler1)
        emitter.subscribe(EventType.ERROR, handler2)

        emitter.clear_handlers(EventType.TOOL_CALLED)

        assert EventType.TOOL_CALLED not in emitter._handlers
        assert EventType.ERROR in emitter._handlers

    def test_clear_handlers_all(self, emitter: EventEmitter) -> None:
        """Should clear all handlers."""
        emitter.subscribe(EventType.TOOL_CALLED, MagicMock())
        emitter.subscribe(None, MagicMock())
        emitter.subscribe_async(EventType.ERROR, MagicMock())

        emitter.clear_handlers()

        assert len(emitter._handlers) == 0
        assert len(emitter._async_handlers) == 0
        assert len(emitter._global_handlers) == 0
        assert len(emitter._async_global_handlers) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_event_emitter(self) -> None:
        """Should return global emitter."""
        import agentsh.telemetry.events as events_module
        events_module._emitter = None

        emitter = get_event_emitter()
        assert emitter is not None
        assert isinstance(emitter, EventEmitter)

    def test_emit_event(self) -> None:
        """Should emit event using convenience function."""
        import agentsh.telemetry.events as events_module
        events_module._emitter = None

        event = emit_event(
            EventType.COMMAND_EXECUTED,
            data={"command": "ls"},
            session_id="sess-1",
            user_id="user-1",
            metadata={"extra": "data"},
        )

        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.data["command"] == "ls"
        assert event.session_id == "sess-1"

    @pytest.mark.asyncio
    async def test_emit_event_async(self) -> None:
        """Should emit event asynchronously."""
        import agentsh.telemetry.events as events_module
        events_module._emitter = None

        event = await emit_event_async(
            EventType.LLM_RESPONSE,
            data={"model": "gpt-4"},
        )

        assert event.event_type == EventType.LLM_RESPONSE
        assert event.data["model"] == "gpt-4"


class TestEventFactories:
    """Tests for event factory functions."""

    def test_command_executed_event(self) -> None:
        """Should create command executed event."""
        event = command_executed_event(
            command="ls -la",
            exit_code=0,
            duration_ms=100,
            session_id="sess-1",
            user_id="user-1",
        )

        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.data["command"] == "ls -la"
        assert event.data["exit_code"] == 0
        assert event.data["duration_ms"] == 100

    def test_tool_called_event(self) -> None:
        """Should create tool called event."""
        event = tool_called_event(
            tool_name="shell.run",
            arguments={"command": "pwd"},
        )

        assert event.event_type == EventType.TOOL_CALLED
        assert event.data["tool_name"] == "shell.run"
        assert event.data["arguments"]["command"] == "pwd"

    def test_tool_completed_event_success(self) -> None:
        """Should create tool completed event for success."""
        event = tool_completed_event(
            tool_name="fs.read",
            success=True,
            duration_ms=50,
            result_preview="file content here",
        )

        assert event.event_type == EventType.TOOL_COMPLETED
        assert event.data["success"] is True
        assert event.data["duration_ms"] == 50

    def test_tool_completed_event_failure(self) -> None:
        """Should create tool failed event for failure."""
        event = tool_completed_event(
            tool_name="shell.run",
            success=False,
            duration_ms=100,
        )

        assert event.event_type == EventType.TOOL_FAILED
        assert event.data["success"] is False

    def test_tool_completed_event_long_result(self) -> None:
        """Should truncate long result preview."""
        long_result = "x" * 500
        event = tool_completed_event(
            tool_name="test",
            success=True,
            duration_ms=10,
            result_preview=long_result,
        )

        assert len(event.data["result_preview"]) == 200

    def test_workflow_event(self) -> None:
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
        assert event.data["total_steps"] == 5

    def test_llm_event(self) -> None:
        """Should create LLM event."""
        event = llm_event(
            event_type=EventType.LLM_RESPONSE,
            provider="anthropic",
            model="claude-3",
            tokens_in=100,
            tokens_out=200,
            duration_ms=500,
        )

        assert event.event_type == EventType.LLM_RESPONSE
        assert event.data["provider"] == "anthropic"
        assert event.data["model"] == "claude-3"
        assert event.data["tokens_in"] == 100

    def test_llm_event_error(self) -> None:
        """Should create LLM error event."""
        event = llm_event(
            event_type=EventType.LLM_ERROR,
            provider="openai",
            model="gpt-4",
            error="Rate limited",
        )

        assert event.event_type == EventType.LLM_ERROR
        assert event.data["error"] == "Rate limited"

    def test_security_event(self) -> None:
        """Should create security event."""
        event = security_event(
            event_type=EventType.SECURITY_ALERT,
            command="rm -rf /",
            risk_level="CRITICAL",
            action="blocked",
            reasons=["Dangerous command", "Root directory"],
        )

        assert event.event_type == EventType.SECURITY_ALERT
        assert event.data["command"] == "rm -rf /"
        assert event.data["risk_level"] == "CRITICAL"
        assert event.data["action"] == "blocked"
        assert len(event.data["reasons"]) == 2
