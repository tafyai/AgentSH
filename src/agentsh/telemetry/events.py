"""Telemetry event system for AgentSH."""

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Types of telemetry events."""

    # Command/Tool events
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_BLOCKED = "command_blocked"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_STEP = "workflow_step"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"

    # LLM events
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_ERROR = "llm_error"

    # Session events
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"

    # Security events
    SECURITY_ALERT = "security_alert"
    SECURITY_VIOLATION = "security_violation"

    # Memory events
    MEMORY_STORED = "memory_stored"
    MEMORY_RETRIEVED = "memory_retrieved"

    # System events
    ERROR = "error"
    WARNING = "warning"
    HEALTH_CHECK = "health_check"


@dataclass
class TelemetryEvent:
    """A telemetry event.

    Attributes:
        event_type: Type of event
        timestamp: When the event occurred
        event_id: Unique event identifier
        session_id: Optional session identifier
        user_id: Optional user identifier
        data: Event-specific data
        metadata: Additional metadata
    """

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "data": self.data,
            "metadata": self.metadata,
        }


# Type alias for event handlers
EventHandler = Callable[[TelemetryEvent], None]
AsyncEventHandler = Callable[[TelemetryEvent], Any]


class EventEmitter:
    """Emits and distributes telemetry events.

    Supports both synchronous and asynchronous event handlers.

    Example:
        emitter = EventEmitter()

        def on_tool_called(event):
            print(f"Tool called: {event.data}")

        emitter.subscribe(EventType.TOOL_CALLED, on_tool_called)

        emitter.emit(TelemetryEvent(
            event_type=EventType.TOOL_CALLED,
            data={"tool_name": "shell.run", "args": {"command": "ls"}},
        ))
    """

    _instance: Optional["EventEmitter"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventEmitter":
        """Singleton pattern for global event emitter."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize event emitter."""
        if self._initialized:
            return

        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._async_handlers: dict[EventType, list[AsyncEventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._async_global_handlers: list[AsyncEventHandler] = []
        self._event_queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._processing = False
        self._initialized = True

        logger.debug("EventEmitter initialized")

    def subscribe(
        self,
        event_type: Optional[EventType],
        handler: EventHandler,
    ) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to (None for all events)
            handler: Synchronous handler function
        """
        if event_type is None:
            self._global_handlers.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

        logger.debug(
            "Handler subscribed",
            event_type=event_type.value if event_type else "all",
        )

    def subscribe_async(
        self,
        event_type: Optional[EventType],
        handler: AsyncEventHandler,
    ) -> None:
        """Subscribe to events with an async handler.

        Args:
            event_type: Type of event to subscribe to (None for all events)
            handler: Asynchronous handler function
        """
        if event_type is None:
            self._async_global_handlers.append(handler)
        else:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: Optional[EventType],
        handler: EventHandler,
    ) -> bool:
        """Unsubscribe a handler from events.

        Args:
            event_type: Type of event (None for global handlers)
            handler: Handler to remove

        Returns:
            True if handler was removed
        """
        try:
            if event_type is None:
                self._global_handlers.remove(handler)
            else:
                if event_type in self._handlers:
                    self._handlers[event_type].remove(handler)
            return True
        except ValueError:
            return False

    def emit(self, event: TelemetryEvent) -> None:
        """Emit an event synchronously.

        Args:
            event: Event to emit
        """
        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler error",
                    handler=handler.__name__,
                    error=str(e),
                )

        # Call type-specific handlers
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(
                        "Event handler error",
                        handler=handler.__name__,
                        event_type=event.event_type.value,
                        error=str(e),
                    )

    async def emit_async(self, event: TelemetryEvent) -> None:
        """Emit an event asynchronously.

        Args:
            event: Event to emit
        """
        # Emit synchronously first
        self.emit(event)

        # Call async global handlers
        for handler in self._async_global_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Async event handler error",
                    handler=handler.__name__,
                    error=str(e),
                )

        # Call async type-specific handlers
        if event.event_type in self._async_handlers:
            for handler in self._async_handlers[event.event_type]:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        "Async event handler error",
                        handler=handler.__name__,
                        event_type=event.event_type.value,
                        error=str(e),
                    )

    def clear_handlers(self, event_type: Optional[EventType] = None) -> None:
        """Clear all handlers for an event type.

        Args:
            event_type: Type to clear (None clears all handlers)
        """
        if event_type is None:
            self._handlers.clear()
            self._async_handlers.clear()
            self._global_handlers.clear()
            self._async_global_handlers.clear()
        else:
            self._handlers.pop(event_type, None)
            self._async_handlers.pop(event_type, None)


# Global event emitter instance
_emitter: Optional[EventEmitter] = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance.

    Returns:
        Global EventEmitter singleton
    """
    global _emitter
    if _emitter is None:
        _emitter = EventEmitter()
    return _emitter


def emit_event(
    event_type: EventType,
    data: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> TelemetryEvent:
    """Convenience function to emit an event.

    Args:
        event_type: Type of event
        data: Event data
        session_id: Optional session ID
        user_id: Optional user ID
        metadata: Additional metadata

    Returns:
        The emitted event
    """
    event = TelemetryEvent(
        event_type=event_type,
        data=data or {},
        session_id=session_id,
        user_id=user_id,
        metadata=metadata or {},
    )
    get_event_emitter().emit(event)
    return event


async def emit_event_async(
    event_type: EventType,
    data: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> TelemetryEvent:
    """Convenience function to emit an event asynchronously.

    Args:
        event_type: Type of event
        data: Event data
        session_id: Optional session ID
        user_id: Optional user ID
        metadata: Additional metadata

    Returns:
        The emitted event
    """
    event = TelemetryEvent(
        event_type=event_type,
        data=data or {},
        session_id=session_id,
        user_id=user_id,
        metadata=metadata or {},
    )
    await get_event_emitter().emit_async(event)
    return event


# Event factory functions for common events
def command_executed_event(
    command: str,
    exit_code: int,
    duration_ms: int,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create a command executed event."""
    return TelemetryEvent(
        event_type=EventType.COMMAND_EXECUTED,
        session_id=session_id,
        user_id=user_id,
        data={
            "command": command,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
    )


def tool_called_event(
    tool_name: str,
    arguments: dict[str, Any],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create a tool called event."""
    return TelemetryEvent(
        event_type=EventType.TOOL_CALLED,
        session_id=session_id,
        user_id=user_id,
        data={
            "tool_name": tool_name,
            "arguments": arguments,
        },
    )


def tool_completed_event(
    tool_name: str,
    success: bool,
    duration_ms: int,
    result_preview: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create a tool completed event."""
    return TelemetryEvent(
        event_type=EventType.TOOL_COMPLETED if success else EventType.TOOL_FAILED,
        session_id=session_id,
        user_id=user_id,
        data={
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "result_preview": result_preview[:200] if result_preview else None,
        },
    )


def workflow_event(
    event_type: EventType,
    workflow_id: str,
    step: Optional[int] = None,
    total_steps: Optional[int] = None,
    status: Optional[str] = None,
    session_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create a workflow event."""
    return TelemetryEvent(
        event_type=event_type,
        session_id=session_id,
        data={
            "workflow_id": workflow_id,
            "step": step,
            "total_steps": total_steps,
            "status": status,
        },
    )


def llm_event(
    event_type: EventType,
    provider: str,
    model: str,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
    session_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create an LLM event."""
    return TelemetryEvent(
        event_type=event_type,
        session_id=session_id,
        data={
            "provider": provider,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
            "error": error,
        },
    )


def security_event(
    event_type: EventType,
    command: str,
    risk_level: str,
    action: str,
    reasons: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> TelemetryEvent:
    """Create a security event."""
    return TelemetryEvent(
        event_type=event_type,
        session_id=session_id,
        user_id=user_id,
        data={
            "command": command,
            "risk_level": risk_level,
            "action": action,
            "reasons": reasons or [],
        },
    )
