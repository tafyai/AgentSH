"""Tests for LLM client abstraction module."""

import pytest
from typing import AsyncIterator, Optional

from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    MessageRole,
    StopReason,
    ToolCall,
    ToolDefinition,
)


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_role_values(self) -> None:
        """Should have expected role values."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self) -> None:
        """Should create tool call."""
        tc = ToolCall(
            id="call_123",
            name="run_command",
            arguments={"command": "ls -la"},
        )

        assert tc.id == "call_123"
        assert tc.name == "run_command"
        assert tc.arguments["command"] == "ls -la"


class TestMessage:
    """Tests for Message dataclass."""

    def test_create_message(self) -> None:
        """Should create message."""
        msg = Message(
            role=MessageRole.USER,
            content="Hello",
        )

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id is None

    def test_system_factory(self) -> None:
        """Should create system message."""
        msg = Message.system("You are a helpful assistant.")

        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant."

    def test_user_factory(self) -> None:
        """Should create user message."""
        msg = Message.user("Hello!")

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"

    def test_assistant_factory(self) -> None:
        """Should create assistant message."""
        msg = Message.assistant("Hi there!")

        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there!"

    def test_assistant_with_tool_calls(self) -> None:
        """Should create assistant message with tool calls."""
        tc = ToolCall(id="call_1", name="ls", arguments={})
        msg = Message.assistant("Let me check.", tool_calls=[tc])

        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "ls"

    def test_tool_result_factory(self) -> None:
        """Should create tool result message."""
        msg = Message.tool_result(
            tool_call_id="call_1",
            name="ls",
            content="file1.txt\nfile2.txt",
        )

        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_1"
        assert msg.name == "ls"
        assert msg.content == "file1.txt\nfile2.txt"

    def test_to_dict(self) -> None:
        """Should convert to dict."""
        msg = Message.user("Hello")
        d = msg.to_dict()

        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_to_dict_with_tool_calls(self) -> None:
        """Should include tool calls in dict."""
        tc = ToolCall(id="call_1", name="ls", arguments={"path": "."})
        msg = Message.assistant("Checking", tool_calls=[tc])
        d = msg.to_dict()

        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["name"] == "ls"

    def test_to_dict_with_tool_call_id(self) -> None:
        """Should include tool_call_id in dict."""
        msg = Message.tool_result("call_1", "ls", "output")
        d = msg.to_dict()

        assert d["tool_call_id"] == "call_1"
        assert d["name"] == "ls"


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    @pytest.fixture
    def tool_def(self) -> ToolDefinition:
        """Create sample tool definition."""
        return ToolDefinition(
            name="run_command",
            description="Run a shell command",
            parameters={
                "command": {"type": "string", "description": "The command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
            },
            required=["command"],
        )

    def test_create_tool_definition(self, tool_def: ToolDefinition) -> None:
        """Should create tool definition."""
        assert tool_def.name == "run_command"
        assert tool_def.description == "Run a shell command"
        assert "command" in tool_def.parameters
        assert "command" in tool_def.required

    def test_to_openai_format(self, tool_def: ToolDefinition) -> None:
        """Should convert to OpenAI format."""
        fmt = tool_def.to_openai_format()

        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "run_command"
        assert fmt["function"]["description"] == "Run a shell command"
        assert fmt["function"]["parameters"]["type"] == "object"
        assert "command" in fmt["function"]["parameters"]["properties"]
        assert "command" in fmt["function"]["parameters"]["required"]

    def test_to_anthropic_format(self, tool_def: ToolDefinition) -> None:
        """Should convert to Anthropic format."""
        fmt = tool_def.to_anthropic_format()

        assert fmt["name"] == "run_command"
        assert fmt["description"] == "Run a shell command"
        assert fmt["input_schema"]["type"] == "object"
        assert "command" in fmt["input_schema"]["properties"]
        assert "command" in fmt["input_schema"]["required"]


class TestStopReason:
    """Tests for StopReason enum."""

    def test_stop_reason_values(self) -> None:
        """Should have expected values."""
        assert StopReason.END_TURN.value == "end_turn"
        assert StopReason.TOOL_USE.value == "tool_use"
        assert StopReason.MAX_TOKENS.value == "max_tokens"
        assert StopReason.STOP_SEQUENCE.value == "stop_sequence"
        assert StopReason.ERROR.value == "error"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_response(self) -> None:
        """Should create response."""
        resp = LLMResponse(content="Hello!")

        assert resp.content == "Hello!"
        assert resp.tool_calls == []
        assert resp.stop_reason == StopReason.END_TURN
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0

    def test_response_with_token_counts(self) -> None:
        """Should track token counts."""
        resp = LLMResponse(
            content="Response",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-20250514",
        )

        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.total_tokens == 150
        assert resp.model == "claude-sonnet-4-20250514"

    def test_response_with_tool_calls(self) -> None:
        """Should have tool calls."""
        tc = ToolCall(id="call_1", name="ls", arguments={})
        resp = LLMResponse(
            content="Let me check",
            tool_calls=[tc],
            stop_reason=StopReason.TOOL_USE,
        )

        assert resp.has_tool_calls is True
        assert resp.stop_reason == StopReason.TOOL_USE

    def test_response_without_tool_calls(self) -> None:
        """Should not have tool calls."""
        resp = LLMResponse(content="Done!")

        assert resp.has_tool_calls is False

    def test_total_tokens(self) -> None:
        """Should calculate total tokens."""
        resp = LLMResponse(
            content="Test",
            input_tokens=100,
            output_tokens=25,
        )

        assert resp.total_tokens == 125


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self, response: str = "Mock response") -> None:
        self._response = response
        self._model = "mock-model"

    @property
    def provider(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return self._model

    async def invoke(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return LLMResponse(
            content=self._response,
            input_tokens=len(str(messages)) // 4,
            output_tokens=len(self._response) // 4,
            model=self._model,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        for word in self._response.split():
            yield word + " "


class TestLLMClient:
    """Tests for LLMClient abstract class."""

    @pytest.fixture
    def client(self) -> MockLLMClient:
        """Create mock client."""
        return MockLLMClient()

    def test_provider_property(self, client: MockLLMClient) -> None:
        """Should return provider name."""
        assert client.provider == "mock"

    def test_model_property(self, client: MockLLMClient) -> None:
        """Should return model name."""
        assert client.model == "mock-model"

    @pytest.mark.asyncio
    async def test_invoke(self, client: MockLLMClient) -> None:
        """Should invoke and return response."""
        messages = [Message.user("Hello")]
        response = await client.invoke(messages)

        assert response.content == "Mock response"
        assert response.model == "mock-model"

    @pytest.mark.asyncio
    async def test_stream(self, client: MockLLMClient) -> None:
        """Should stream response."""
        messages = [Message.user("Hello")]
        chunks = []
        async for chunk in client.stream(messages):
            chunks.append(chunk)

        result = "".join(chunks)
        assert "Mock" in result
        assert "response" in result

    def test_count_tokens(self, client: MockLLMClient) -> None:
        """Should estimate token count."""
        text = "Hello, this is a test message"
        count = client.count_tokens(text)

        # Default implementation: ~4 chars per token
        assert count > 0
        assert count < len(text)

    def test_count_tokens_empty(self, client: MockLLMClient) -> None:
        """Should handle empty text."""
        count = client.count_tokens("")
        assert count == 0


class TestMessageConversation:
    """Tests for message conversation flows."""

    def test_simple_conversation(self) -> None:
        """Should build simple conversation."""
        messages = [
            Message.system("You are helpful."),
            Message.user("Hello!"),
            Message.assistant("Hi there!"),
            Message.user("What's 2+2?"),
            Message.assistant("4"),
        ]

        assert len(messages) == 5
        assert messages[0].role == MessageRole.SYSTEM
        assert messages[-1].content == "4"

    def test_tool_use_conversation(self) -> None:
        """Should build tool use conversation."""
        tc = ToolCall(id="call_1", name="calculator", arguments={"expr": "2+2"})

        messages = [
            Message.user("What's 2+2?"),
            Message.assistant("Let me calculate.", tool_calls=[tc]),
            Message.tool_result("call_1", "calculator", "4"),
            Message.assistant("2+2 equals 4."),
        ]

        assert len(messages) == 4
        assert messages[1].has_tool_calls if hasattr(messages[1], 'has_tool_calls') else len(messages[1].tool_calls) > 0
        assert messages[2].role == MessageRole.TOOL


class TestToolDefinitionEdgeCases:
    """Tests for edge cases in tool definitions."""

    def test_empty_parameters(self) -> None:
        """Should handle empty parameters."""
        tool = ToolDefinition(
            name="get_time",
            description="Get current time",
            parameters={},
            required=[],
        )

        openai = tool.to_openai_format()
        assert openai["function"]["parameters"]["properties"] == {}

    def test_complex_parameters(self) -> None:
        """Should handle complex parameters."""
        tool = ToolDefinition(
            name="search",
            description="Search for files",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "recursive": {"type": "boolean"},
                        "max_depth": {"type": "integer"},
                    },
                },
            },
            required=["query"],
        )

        anthropic = tool.to_anthropic_format()
        assert "options" in anthropic["input_schema"]["properties"]
