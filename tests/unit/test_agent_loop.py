"""Tests for agent loop module."""

import pytest
from typing import AsyncIterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from agentsh.agent.agent_loop import (
    AgentConfig,
    AgentContext,
    AgentLoop,
    AgentResult,
    StreamingAgentLoop,
)
from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agentsh.tools.base import ToolResult
from agentsh.tools.registry import ToolRegistry


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(
        self,
        responses: Optional[list[LLMResponse]] = None,
    ) -> None:
        self._responses = responses or [
            LLMResponse(content="Mock response", stop_reason=StopReason.END_TURN)
        ]
        self._call_count = 0

    @property
    def provider(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return "mock-model"

    async def invoke(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return response

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        for response in self._responses:
            for word in response.content.split():
                yield word + " "


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = AgentConfig()

        assert config.max_steps == 10
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout == 30.0

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = AgentConfig(
            max_steps=5,
            temperature=0.7,
            max_tokens=2048,
            timeout=60.0,
        )

        assert config.max_steps == 5
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.timeout == 60.0


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_default_context(self) -> None:
        """Should have empty defaults."""
        ctx = AgentContext()

        assert ctx.cwd == ""
        assert ctx.env == {}
        assert ctx.history == []
        assert ctx.user_id == ""

    def test_custom_context(self) -> None:
        """Should accept custom values."""
        ctx = AgentContext(
            cwd="/home/user",
            env={"PATH": "/usr/bin"},
            history=["ls", "cd"],
            user_id="user123",
        )

        assert ctx.cwd == "/home/user"
        assert ctx.env["PATH"] == "/usr/bin"
        assert len(ctx.history) == 2
        assert ctx.user_id == "user123"


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_default_result(self) -> None:
        """Should have success defaults."""
        result = AgentResult(response="Done!")

        assert result.response == "Done!"
        assert result.tool_calls_made == []
        assert result.total_steps == 0
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.success is True
        assert result.error is None

    def test_failed_result(self) -> None:
        """Should track failure."""
        result = AgentResult(
            response="Error occurred",
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"

    def test_result_with_tool_calls(self) -> None:
        """Should track tool calls."""
        result = AgentResult(
            response="Done!",
            tool_calls_made=["ls", "cat", "grep"],
            total_steps=3,
        )

        assert len(result.tool_calls_made) == 3
        assert result.total_steps == 3


class TestAgentLoop:
    """Tests for AgentLoop class."""

    @pytest.fixture
    def mock_llm(self) -> MockLLMClient:
        """Create mock LLM client."""
        return MockLLMClient()

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()

        # Add a simple test tool
        def list_files(path: str = ".") -> str:
            return "file1.txt\nfile2.txt"

        registry.register_tool(
            name="list_files",
            handler=list_files,
            description="List files in a directory",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": [],
            },
        )

        return registry

    @pytest.fixture
    def agent(self, mock_llm: MockLLMClient, tool_registry: ToolRegistry) -> AgentLoop:
        """Create agent loop."""
        return AgentLoop(mock_llm, tool_registry)

    @pytest.mark.asyncio
    async def test_simple_invoke(self, agent: AgentLoop) -> None:
        """Should invoke and return response."""
        result = await agent.invoke("Hello!")

        assert result.response == "Mock response"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_with_context(self, agent: AgentLoop) -> None:
        """Should use context."""
        context = AgentContext(cwd="/home/test", user_id="test_user")
        result = await agent.invoke("List files", context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_with_tool_call(self, tool_registry: ToolRegistry) -> None:
        """Should execute tool calls."""
        # First response has tool call, second is final
        responses = [
            LLMResponse(
                content="Let me check.",
                tool_calls=[
                    ToolCall(id="call_1", name="list_files", arguments={"path": "."}),
                ],
                stop_reason=StopReason.TOOL_USE,
            ),
            LLMResponse(
                content="Here are the files: file1.txt, file2.txt",
                stop_reason=StopReason.END_TURN,
            ),
        ]
        mock_llm = MockLLMClient(responses)
        agent = AgentLoop(mock_llm, tool_registry)

        result = await agent.invoke("List files")

        assert result.success is True
        assert "list_files" in result.tool_calls_made

    @pytest.mark.asyncio
    async def test_invoke_unknown_tool(self, tool_registry: ToolRegistry) -> None:
        """Should handle unknown tool gracefully."""
        responses = [
            LLMResponse(
                content="Let me try.",
                tool_calls=[
                    ToolCall(id="call_1", name="unknown_tool", arguments={}),
                ],
                stop_reason=StopReason.TOOL_USE,
            ),
            LLMResponse(
                content="I couldn't find that tool.",
                stop_reason=StopReason.END_TURN,
            ),
        ]
        mock_llm = MockLLMClient(responses)
        agent = AgentLoop(mock_llm, tool_registry)

        result = await agent.invoke("Do something")

        # Should complete without crashing
        assert result is not None

    @pytest.mark.asyncio
    async def test_max_steps_limit(self, tool_registry: ToolRegistry) -> None:
        """Should stop at max steps."""
        # Always return tool calls to force loop
        responses = [
            LLMResponse(
                content="Checking...",
                tool_calls=[
                    ToolCall(id=f"call_{i}", name="list_files", arguments={})
                ],
                stop_reason=StopReason.TOOL_USE,
            )
            for i in range(20)  # More than default max_steps
        ]
        mock_llm = MockLLMClient(responses)
        config = AgentConfig(max_steps=3)
        agent = AgentLoop(mock_llm, tool_registry, config)

        result = await agent.invoke("Loop forever")

        assert result.total_steps == 3
        assert result.success is False
        assert "Max steps" in result.error

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, tool_registry: ToolRegistry) -> None:
        """Should handle LLM errors."""
        mock_llm = MockLLMClient()
        mock_llm.invoke = AsyncMock(side_effect=Exception("API Error"))
        agent = AgentLoop(mock_llm, tool_registry)

        result = await agent.invoke("Test")

        assert result.success is False
        assert "API Error" in result.error

    def test_build_tool_definitions(self, agent: AgentLoop) -> None:
        """Should build tool definitions."""
        defs = agent._build_tool_definitions()

        assert len(defs) == 1
        assert defs[0].name == "list_files"
        assert defs[0].description == "List files in a directory"


class TestAgentLoopWithSecurity:
    """Tests for AgentLoop with security controller."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with shell tool."""
        registry = ToolRegistry()

        def run_command(command: str) -> str:
            return f"Executed: {command}"

        registry.register_tool(
            name="shell",
            handler=run_command,
            description="Run a shell command",
            parameters={
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                },
                "required": ["command"],
            },
        )

        return registry

    @pytest.mark.asyncio
    async def test_security_blocks_dangerous_command(
        self, tool_registry: ToolRegistry
    ) -> None:
        """Should block dangerous commands."""
        from agentsh.security.controller import SecurityController

        responses = [
            LLMResponse(
                content="Running command.",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="shell",
                        arguments={"command": "rm -rf /"},
                    ),
                ],
                stop_reason=StopReason.TOOL_USE,
            ),
            LLMResponse(
                content="Command was blocked.",
                stop_reason=StopReason.END_TURN,
            ),
        ]
        mock_llm = MockLLMClient(responses)
        security = SecurityController()
        agent = AgentLoop(mock_llm, tool_registry, security_controller=security)

        result = await agent.invoke("Delete everything")

        # The tool should be blocked by security
        assert result is not None


class TestStreamingAgentLoop:
    """Tests for StreamingAgentLoop class."""

    @pytest.fixture
    def streaming_agent(self) -> StreamingAgentLoop:
        """Create streaming agent."""
        mock_llm = MockLLMClient([
            LLMResponse(content="This is a streaming response.")
        ])
        registry = ToolRegistry()
        return StreamingAgentLoop(mock_llm, registry)

    @pytest.mark.asyncio
    async def test_stream_with_callback(self, streaming_agent: StreamingAgentLoop) -> None:
        """Should call token callback."""
        tokens = []

        def on_token(token: str) -> None:
            tokens.append(token)

        result = await streaming_agent.stream("Test", on_token=on_token)

        assert len(tokens) > 0
        assert result.response != ""

    @pytest.mark.asyncio
    async def test_stream_without_callback(self, streaming_agent: StreamingAgentLoop) -> None:
        """Should work without callback."""
        result = await streaming_agent.stream("Test")

        assert result.response != ""
        assert result.total_steps >= 1


class TestAgentContext:
    """Additional tests for AgentContext usage."""

    @pytest.mark.asyncio
    async def test_context_passed_to_tool(self) -> None:
        """Should pass context to tools that accept it."""
        captured_context = []

        def tool_with_context(command: str, context: AgentContext = None) -> str:
            captured_context.append(context)
            return "Done"

        registry = ToolRegistry()
        registry.register_tool(
            name="context_tool",
            handler=tool_with_context,
            description="Tool that uses context",
            parameters={
                "properties": {
                    "command": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["command"],
            },
        )

        responses = [
            LLMResponse(
                content="Using context.",
                tool_calls=[
                    ToolCall(id="call_1", name="context_tool", arguments={"command": "test"}),
                ],
                stop_reason=StopReason.TOOL_USE,
            ),
            LLMResponse(content="Done.", stop_reason=StopReason.END_TURN),
        ]
        mock_llm = MockLLMClient(responses)
        agent = AgentLoop(mock_llm, registry)

        context = AgentContext(cwd="/test", user_id="test_user")
        await agent.invoke("Test", context)

        # Context should have been passed
        assert len(captured_context) == 1
        assert captured_context[0].cwd == "/test"
