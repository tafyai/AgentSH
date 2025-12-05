"""Tests for workflow executor module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.workflows.executor import (
    SimpleWorkflowExecutor,
    WorkflowEvent,
    WorkflowExecutor,
    WorkflowResult,
)
from agentsh.workflows.states import WorkflowStatus


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create successful result."""
        result = WorkflowResult(response="Hello, world!")

        assert result.response == "Hello, world!"
        assert result.success is True
        assert result.status == WorkflowStatus.COMPLETED
        assert result.tool_calls == []
        assert result.total_steps == 0
        assert result.error is None

    def test_create_failed_result(self) -> None:
        """Should create failed result."""
        result = WorkflowResult(
            response="Error occurred",
            success=False,
            status=WorkflowStatus.FAILED,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.status == WorkflowStatus.FAILED
        assert result.error == "Something went wrong"

    def test_result_with_tool_calls(self) -> None:
        """Should include tool calls."""
        tool_record = MagicMock(name="test_tool")
        result = WorkflowResult(
            response="Done",
            tool_calls=[tool_record],
            total_steps=3,
        )

        assert len(result.tool_calls) == 1
        assert result.total_steps == 3

    def test_result_with_duration(self) -> None:
        """Should include duration."""
        result = WorkflowResult(response="Done", duration_ms=150)

        assert result.duration_ms == 150

    def test_result_with_final_state(self) -> None:
        """Should include final state."""
        final_state = {"messages": [], "is_terminal": True}
        result = WorkflowResult(response="Done", final_state=final_state)

        assert result.final_state == final_state


class TestWorkflowEvent:
    """Tests for WorkflowEvent dataclass."""

    def test_create_event(self) -> None:
        """Should create event."""
        event = WorkflowEvent(
            event_type="node_complete",
            node="agent",
            data={"message": "Processing"},
        )

        assert event.event_type == "node_complete"
        assert event.node == "agent"
        assert event.data["message"] == "Processing"

    def test_event_has_timestamp(self) -> None:
        """Should have timestamp."""
        before = datetime.now()
        event = WorkflowEvent(
            event_type="test",
            node="test",
            data={},
        )
        after = datetime.now()

        assert before <= event.timestamp <= after

    def test_event_custom_timestamp(self) -> None:
        """Should accept custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        event = WorkflowEvent(
            event_type="test",
            node="test",
            data={},
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time


class TestWorkflowExecutor:
    """Tests for WorkflowExecutor class."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["tool1", "tool2"]
        registry.get_tool.return_value = MagicMock()
        return registry

    @pytest.fixture
    def mock_security_controller(self) -> MagicMock:
        """Create mock security controller."""
        return MagicMock()

    def test_create_executor(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create executor."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert executor.llm_client == mock_llm_client
        assert executor.tool_registry == mock_tool_registry
        assert executor.max_steps == 10
        assert executor.tool_timeout == 30.0

    def test_create_executor_custom_options(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept custom options."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            max_steps=20,
            tool_timeout=60.0,
        )

        assert executor.max_steps == 20
        assert executor.tool_timeout == 60.0

    def test_create_executor_with_security(
        self,
        mock_llm_client: MagicMock,
        mock_tool_registry: MagicMock,
        mock_security_controller: MagicMock,
    ) -> None:
        """Should accept security controller."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            security_controller=mock_security_controller,
        )

        assert executor.security_controller == mock_security_controller

    def test_create_executor_with_memory(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept memory manager."""
        memory_manager = MagicMock()
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            memory_manager=memory_manager,
        )

        assert executor.memory_manager == memory_manager

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should execute workflow successfully."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        # Mock the graph's ainvoke
        mock_message = MagicMock()
        mock_message.content = "Task completed"
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "is_terminal": True,
                "final_result": "Task completed",
                "step_count": 2,
                "tools_used": [],
            }
        )

        result = await executor.execute("List files")

        assert result.success is True
        assert result.response == "Task completed"

    @pytest.mark.asyncio
    async def test_execute_failure(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle execution failure."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        # Mock the graph to raise an exception
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(side_effect=Exception("Network error"))

        result = await executor.execute("List files")

        assert result.success is False
        assert "Network error" in result.error
        assert result.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_with_context(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should pass context to workflow."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        mock_message = MagicMock()
        mock_message.content = "Done"
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "is_terminal": True,
                "final_result": "Done",
            }
        )

        context = {"cwd": "/home/user", "env": {"PATH": "/bin"}}
        result = await executor.execute("List files", context=context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_error_state(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle error in final state."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [],
                "is_terminal": True,
                "error": "Tool execution failed",
            }
        )

        result = await executor.execute("Run command")

        assert result.success is False
        assert result.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_stream_events(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should stream workflow events."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        # Mock async generator
        async def mock_astream(*args, **kwargs):
            yield {"agent": {"messages": [], "response": "thinking"}}
            yield {"tools": {"tools_used": []}}

        executor._graph = MagicMock()
        executor._graph.astream = mock_astream

        events = []
        async for event in executor.stream("Test goal"):
            events.append(event)

        # Should have start, node events, and complete
        assert len(events) >= 3
        assert events[0].event_type == "workflow_start"
        assert events[-1].event_type == "workflow_complete"

    @pytest.mark.asyncio
    async def test_stream_error(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle streaming errors."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        async def mock_astream_error(*args, **kwargs):
            yield {"agent": {"messages": []}}
            raise Exception("Stream error")

        executor._graph = MagicMock()
        executor._graph.astream = mock_astream_error

        events = []
        async for event in executor.stream("Test goal"):
            events.append(event)

        # Should have error event
        assert any(e.event_type == "workflow_error" for e in events)

    @pytest.mark.asyncio
    async def test_execute_with_callbacks(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should execute with callbacks."""
        executor = WorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        # Mock streaming and execution
        async def mock_astream(*args, **kwargs):
            yield {"agent": {"messages": []}}
            yield {"tools": {"tools_used": []}}

        mock_message = MagicMock()
        mock_message.content = "Done"
        executor._graph = MagicMock()
        executor._graph.astream = mock_astream
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "is_terminal": True,
                "final_result": "Done",
            }
        )

        tool_results = []

        def on_tool_result(name: str, result: str, success: bool) -> None:
            tool_results.append((name, result, success))

        result = await executor.execute_with_callbacks(
            "Test goal",
            on_tool_result=on_tool_result,
        )

        assert result is not None


class TestSimpleWorkflowExecutor:
    """Tests for SimpleWorkflowExecutor class."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["tool1"]
        registry.get_tool.return_value = MagicMock()
        return registry

    def test_create_simple_executor(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create simple executor."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert executor.llm_client == mock_llm_client
        assert executor.tool_registry == mock_tool_registry
        assert executor.max_steps == 10

    def test_create_simple_executor_custom_steps(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept custom max_steps."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            max_steps=5,
        )

        assert executor.max_steps == 5

    @pytest.mark.asyncio
    async def test_simple_execute_success(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should execute simple workflow."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        mock_message = MagicMock()
        mock_message.content = "Simple result"
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "final_result": "Simple result",
                "step_count": 1,
                "tools_used": [],
            }
        )

        result = await executor.execute("Simple task")

        assert result.success is True
        assert result.response == "Simple result"

    @pytest.mark.asyncio
    async def test_simple_execute_fallback_to_message(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should fallback to last message if no final_result."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        mock_message = MagicMock()
        mock_message.content = "Message content"
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "step_count": 1,
            }
        )

        result = await executor.execute("Task")

        assert result.response == "Message content"

    @pytest.mark.asyncio
    async def test_simple_execute_failure(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle simple execution failure."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(side_effect=Exception("Simple error"))

        result = await executor.execute("Task")

        assert result.success is False
        assert "Simple error" in result.error

    @pytest.mark.asyncio
    async def test_simple_execute_with_context(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should pass context to simple workflow."""
        executor = SimpleWorkflowExecutor(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        mock_message = MagicMock()
        mock_message.content = "Done"
        executor._graph = MagicMock()
        executor._graph.ainvoke = AsyncMock(
            return_value={
                "messages": [mock_message],
                "final_result": "Done",
            }
        )

        result = await executor.execute("Task", context={"cwd": "/home"})

        assert result.success is True
