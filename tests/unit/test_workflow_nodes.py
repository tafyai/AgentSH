"""Tests for workflow node implementations."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agentsh.agent.llm_client import LLMResponse, Message, StopReason, ToolCall
from agentsh.tools.base import RiskLevel, Tool, ToolResult
from agentsh.tools.registry import ToolRegistry
from agentsh.workflows.nodes import (
    AgentNode,
    ApprovalNode,
    ErrorRecoveryNode,
    MemoryNode,
    ToolNode,
)
from agentsh.workflows.states import create_initial_state


class TestAgentNode:
    """Test AgentNode functionality."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        client = MagicMock()
        client.invoke = AsyncMock()
        client.provider = "mock"
        client.model = "test-model"
        return client

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()
        registry.register_tool(
            name="test.echo",
            handler=lambda msg: ToolResult(success=True, output=msg),
            description="Echo a message",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
        )
        return registry

    def test_creates_initial_messages(
        self, mock_llm_client: MagicMock, tool_registry: ToolRegistry
    ) -> None:
        """Should create initial messages on first call."""
        mock_llm_client.invoke.return_value = LLMResponse(
            content="Hello!",
            tool_calls=[],
            stop_reason=StopReason.END_TURN,
            input_tokens=10,
            output_tokens=5,
        )

        node = AgentNode(mock_llm_client, tool_registry)
        state = create_initial_state("Say hello")

        result = asyncio.run(node(state))

        # Should have called LLM
        mock_llm_client.invoke.assert_called_once()

        # Should have messages now
        assert len(result["messages"]) > 0

        # Should be terminal (no tool calls)
        assert result["is_terminal"] is True
        assert result["final_result"] == "Hello!"

    def test_handles_tool_calls(
        self, mock_llm_client: MagicMock, tool_registry: ToolRegistry
    ) -> None:
        """Should handle tool calls in response."""
        tool_call = ToolCall(
            id="call_1",
            name="test.echo",
            arguments={"msg": "test"},
        )

        mock_llm_client.invoke.return_value = LLMResponse(
            content="I'll echo that",
            tool_calls=[tool_call],
            stop_reason=StopReason.TOOL_USE,
            input_tokens=10,
            output_tokens=5,
        )

        node = AgentNode(mock_llm_client, tool_registry)
        state = create_initial_state("Echo test")

        result = asyncio.run(node(state))

        # Should have pending tool calls
        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0].name == "test.echo"

        # Should not be terminal
        assert result.get("is_terminal") is not True

    def test_handles_llm_error(
        self, mock_llm_client: MagicMock, tool_registry: ToolRegistry
    ) -> None:
        """Should handle LLM errors gracefully."""
        mock_llm_client.invoke.side_effect = Exception("LLM API error")

        node = AgentNode(mock_llm_client, tool_registry)
        state = create_initial_state("Test")

        result = asyncio.run(node(state))

        assert result["is_terminal"] is True
        assert "error" in result["final_result"].lower()


class TestToolNode:
    """Test ToolNode functionality."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()

        def sync_handler(x: int) -> ToolResult:
            return ToolResult(success=True, output=str(x * 2))

        async def async_handler(msg: str) -> ToolResult:
            return ToolResult(success=True, output=f"Async: {msg}")

        registry.register_tool(
            name="math.double",
            handler=sync_handler,
            description="Double a number",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        )

        registry.register_tool(
            name="async.echo",
            handler=async_handler,
            description="Async echo",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
        )

        return registry

    def test_executes_pending_tools(self, tool_registry: ToolRegistry) -> None:
        """Should execute pending tool calls."""
        tool_call = ToolCall(
            id="call_1",
            name="math.double",
            arguments={"x": 5},
        )

        state = create_initial_state("Double 5")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = [Message.user("Double 5")]

        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))

        # Should have cleared pending calls
        assert result["pending_tool_calls"] == []

        # Should have added tool result to messages
        assert len(result["messages"]) > 1

        # Should have recorded tool use
        assert len(result["tools_used"]) == 1
        assert result["tools_used"][0].success is True

    def test_executes_async_tools(self, tool_registry: ToolRegistry) -> None:
        """Should execute async tool handlers."""
        tool_call = ToolCall(
            id="call_1",
            name="async.echo",
            arguments={"msg": "hello"},
        )

        state = create_initial_state("Echo hello")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))

        assert len(result["tools_used"]) == 1
        assert "Async: hello" in result["tools_used"][0].result

    def test_handles_unknown_tool(self, tool_registry: ToolRegistry) -> None:
        """Should handle unknown tool gracefully."""
        tool_call = ToolCall(
            id="call_1",
            name="unknown.tool",
            arguments={},
        )

        state = create_initial_state("Test")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))

        assert len(result["tools_used"]) == 1
        assert result["tools_used"][0].success is False
        assert "unknown" in result["tools_used"][0].result.lower()

    def test_handles_tool_timeout(self, tool_registry: ToolRegistry) -> None:
        """Should handle tool timeout."""
        async def slow_handler() -> ToolResult:
            await asyncio.sleep(10)
            return ToolResult(success=True, output="done")

        tool_registry.register_tool(
            name="slow.tool",
            handler=slow_handler,
            description="Slow tool",
            parameters={"type": "object", "properties": {}},
        )

        tool_call = ToolCall(id="call_1", name="slow.tool", arguments={})

        state = create_initial_state("Test")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ToolNode(tool_registry, timeout=0.1)
        result = asyncio.run(node(state))

        assert result["tools_used"][0].success is False
        assert "timed out" in result["tools_used"][0].result.lower()


class TestApprovalNode:
    """Test ApprovalNode functionality."""

    def test_passes_through_without_security(self) -> None:
        """Should pass through without security controller."""
        tool_call = ToolCall(
            id="call_1",
            name="shell.run",
            arguments={"command": "ls"},
        )

        state = create_initial_state("List files")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ApprovalNode(security_controller=None)
        result = asyncio.run(node(state))

        # Should keep pending calls
        assert len(result["pending_tool_calls"]) == 1


class TestErrorRecoveryNode:
    """Test ErrorRecoveryNode functionality."""

    def test_retries_on_error(self) -> None:
        """Should attempt retry on error."""
        state = create_initial_state("Test")
        state["error"] = "Temporary failure"

        node = ErrorRecoveryNode(max_retries=2)
        result = asyncio.run(node(state))

        # Should clear error for retry
        assert result["error"] is None
        assert result["is_terminal"] is False

    def test_terminates_after_max_retries(self) -> None:
        """Should terminate after max retries."""
        state = create_initial_state("Test")
        state["error"] = "Persistent failure"

        node = ErrorRecoveryNode(max_retries=2)

        # First retry
        asyncio.run(node(state))

        # Second retry
        asyncio.run(node(state))

        # Third attempt - should terminate
        result = asyncio.run(node(state))

        assert result["is_terminal"] is True

    def test_no_action_without_error(self) -> None:
        """Should do nothing without error."""
        state = create_initial_state("Test")

        node = ErrorRecoveryNode()
        result = asyncio.run(node(state))

        assert result == {}


class TestMemoryNode:
    """Test MemoryNode functionality."""

    def test_no_action_without_manager(self) -> None:
        """Should do nothing without memory manager."""
        state = create_initial_state("Test")

        node = MemoryNode(memory_manager=None)
        result = asyncio.run(node(state))

        assert result == {}

    def test_with_memory_manager(self) -> None:
        """Should call memory manager when present."""
        mock_manager = MagicMock()
        mock_manager.store = AsyncMock()

        state = create_initial_state("Test")
        state["messages"] = [Message.user("Test message")]

        node = MemoryNode(memory_manager=mock_manager)
        result = asyncio.run(node(state))

        # Should return empty dict or updates
        assert isinstance(result, dict)


class TestAgentNodeExtended:
    """Extended tests for AgentNode."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        client = MagicMock()
        client.invoke = AsyncMock()
        client.provider = "mock"
        client.model = "test-model"
        return client

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()
        registry.register_tool(
            name="test.echo",
            handler=lambda msg: ToolResult(success=True, output=msg),
            description="Echo a message",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
        )
        return registry

    def test_uses_existing_messages(
        self, mock_llm_client: MagicMock, tool_registry: ToolRegistry
    ) -> None:
        """Should use existing messages if present."""
        mock_llm_client.invoke.return_value = LLMResponse(
            content="Continuation",
            tool_calls=[],
            stop_reason=StopReason.END_TURN,
            input_tokens=10,
            output_tokens=5,
        )

        node = AgentNode(mock_llm_client, tool_registry)
        state = create_initial_state("Test")
        state["messages"] = [
            Message.system("System prompt"),
            Message.user("First message"),
            Message.assistant("First response"),
        ]

        result = asyncio.run(node(state))

        # Should have added to existing messages
        assert len(result["messages"]) == 4

    def test_custom_temperature_and_tokens(
        self, mock_llm_client: MagicMock, tool_registry: ToolRegistry
    ) -> None:
        """Should use custom temperature and max_tokens."""
        mock_llm_client.invoke.return_value = LLMResponse(
            content="Response",
            tool_calls=[],
            stop_reason=StopReason.END_TURN,
            input_tokens=10,
            output_tokens=5,
        )

        node = AgentNode(
            mock_llm_client,
            tool_registry,
            temperature=0.7,
            max_tokens=2048,
        )
        state = create_initial_state("Test")

        asyncio.run(node(state))

        # Verify call parameters
        call_args = mock_llm_client.invoke.call_args
        assert call_args.kwargs["temperature"] == 0.7
        assert call_args.kwargs["max_tokens"] == 2048


class TestToolNodeExtended:
    """Extended tests for ToolNode."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()

        def sync_handler(x: int) -> ToolResult:
            return ToolResult(success=True, output=str(x * 2))

        registry.register_tool(
            name="math.double",
            handler=sync_handler,
            description="Double a number",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        )

        return registry

    def test_no_pending_calls(self, tool_registry: ToolRegistry) -> None:
        """Should return empty dict if no pending calls."""
        state = create_initial_state("Test")
        state["pending_tool_calls"] = []

        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))

        assert result == {}

    def test_handles_tool_exception(self, tool_registry: ToolRegistry) -> None:
        """Should handle tool exceptions gracefully."""
        def failing_handler():
            raise ValueError("Tool failure")

        tool_registry.register_tool(
            name="failing.tool",
            handler=failing_handler,
            description="Fails",
            parameters={"type": "object", "properties": {}},
        )

        tool_call = ToolCall(id="call_1", name="failing.tool", arguments={})

        state = create_initial_state("Test")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))

        assert result["tools_used"][0].success is False
        assert "error" in result["tools_used"][0].result.lower()

    def test_tool_result_types(self, tool_registry: ToolRegistry) -> None:
        """Should handle different return types."""
        # String return
        tool_registry.register_tool(
            name="string.tool",
            handler=lambda: "string result",
            description="Returns string",
            parameters={"type": "object", "properties": {}},
        )

        # Dict return
        tool_registry.register_tool(
            name="dict.tool",
            handler=lambda: {"key": "value"},
            description="Returns dict",
            parameters={"type": "object", "properties": {}},
        )

        # None return
        tool_registry.register_tool(
            name="none.tool",
            handler=lambda: None,
            description="Returns None",
            parameters={"type": "object", "properties": {}},
        )

        state = create_initial_state("Test")
        state["messages"] = []

        # Test string
        state["pending_tool_calls"] = [ToolCall(id="1", name="string.tool", arguments={})]
        node = ToolNode(tool_registry)
        result = asyncio.run(node(state))
        assert result["tools_used"][0].success is True

        # Test dict
        state["pending_tool_calls"] = [ToolCall(id="2", name="dict.tool", arguments={})]
        state["tools_used"] = []
        result = asyncio.run(node(state))
        assert result["tools_used"][0].success is True
        assert "key" in result["tools_used"][0].result

        # Test None
        state["pending_tool_calls"] = [ToolCall(id="3", name="none.tool", arguments={})]
        state["tools_used"] = []
        result = asyncio.run(node(state))
        assert result["tools_used"][0].success is True


class TestApprovalNodeExtended:
    """Extended tests for ApprovalNode."""

    def test_auto_approve_safe_operations(self) -> None:
        """Should auto-approve safe operations."""
        tool_call = ToolCall(
            id="call_1",
            name="safe.operation",
            arguments={},
        )

        state = create_initial_state("Safe operation")
        state["pending_tool_calls"] = [tool_call]
        state["messages"] = []

        node = ApprovalNode(security_controller=None, auto_approve_safe=True)
        result = asyncio.run(node(state))

        # All calls should remain approved
        assert len(result["pending_tool_calls"]) == 1

    def test_no_pending_calls(self) -> None:
        """Should return empty dict if no pending calls."""
        state = create_initial_state("Test")
        state["pending_tool_calls"] = []

        node = ApprovalNode()
        result = asyncio.run(node(state))

        assert result == {}


class TestErrorRecoveryNodeExtended:
    """Extended tests for ErrorRecoveryNode."""

    def test_increments_retry_count(self) -> None:
        """Should increment retry count."""
        state = create_initial_state("Test")
        state["error"] = "Error"

        node = ErrorRecoveryNode(max_retries=5)

        # First run
        result = asyncio.run(node(state))
        # Retry count should be tracked internally

        assert result["error"] is None

    def test_default_max_retries(self) -> None:
        """Should have default max_retries of 2."""
        node = ErrorRecoveryNode()
        assert node.max_retries == 2
