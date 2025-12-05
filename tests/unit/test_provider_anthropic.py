"""Tests for Anthropic LLM provider."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.agent.llm_client import Message, StopReason, ToolCall, ToolDefinition


class TestAnthropicClientInitialization:
    """Tests for AnthropicClient initialization."""

    def test_init_with_api_key(self) -> None:
        """Should initialize with provided API key."""
        with patch("anthropic.AsyncAnthropic") as mock_client:
            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test-key", model="claude-3-opus")

            assert client._api_key == "test-key"
            assert client._model == "claude-3-opus"
            mock_client.assert_called_once()

    def test_init_with_env_key(self) -> None:
        """Should use environment variable if no key provided."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            with patch("anthropic.AsyncAnthropic"):
                from agentsh.agent.providers.anthropic import AnthropicClient

                client = AnthropicClient()
                assert client._api_key == "env-key"

    def test_init_warns_without_key(self) -> None:
        """Should warn if no API key available."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=True):
            with patch("anthropic.AsyncAnthropic"):
                with patch("agentsh.agent.providers.anthropic.logger") as mock_logger:
                    from agentsh.agent.providers.anthropic import AnthropicClient

                    AnthropicClient(api_key="")
                    mock_logger.warning.assert_called()

    def test_init_custom_settings(self) -> None:
        """Should use custom settings."""
        with patch("anthropic.AsyncAnthropic") as mock_client:
            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(
                api_key="test",
                max_retries=5,
                timeout=120.0,
            )

            assert client._max_retries == 5
            assert client._timeout == 120.0

    def test_provider_property(self) -> None:
        """Should return provider name."""
        with patch("anthropic.AsyncAnthropic"):
            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")
            assert client.provider == "anthropic"

    def test_model_property(self) -> None:
        """Should return model name."""
        with patch("anthropic.AsyncAnthropic"):
            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test", model="claude-3-haiku")
            assert client.model == "claude-3-haiku"


class TestAnthropicClientInvoke:
    """Tests for AnthropicClient invoke method."""

    @pytest.fixture
    def mock_anthropic(self):
        """Create mock Anthropic client."""
        with patch("anthropic.AsyncAnthropic") as mock:
            mock_instance = MagicMock()
            mock_instance.messages = MagicMock()
            mock_instance.messages.create = AsyncMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_invoke_simple_message(self, mock_anthropic) -> None:
        """Should invoke with simple message."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_response.model = "claude-3"
        mock_anthropic.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="test")
        messages = [Message.user("Hello")]

        result = asyncio.run(client.invoke(messages))

        assert result.content == "Hello!"
        assert result.stop_reason == StopReason.END_TURN
        mock_anthropic.messages.create.assert_called_once()

    def test_invoke_with_system_prompt(self, mock_anthropic) -> None:
        """Should handle system prompt correctly."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_response.model = "claude-3"
        mock_anthropic.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="test")
        messages = [
            Message.system("You are helpful"),
            Message.user("Hello"),
        ]

        asyncio.run(client.invoke(messages))

        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful"

    def test_invoke_with_tools(self, mock_anthropic) -> None:
        """Should pass tools to API."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        # Create a proper mock for tool_use block with explicit values
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_1"
        tool_block.name = "test_tool"
        tool_block.input = {"arg": "value"}

        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_response.model = "claude-3"
        mock_anthropic.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="test")
        tools = [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters={"arg": {"type": "string"}},
                required=["arg"],
            )
        ]

        result = asyncio.run(client.invoke([Message.user("Test")], tools=tools))

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "test_tool"
        assert result.stop_reason == StopReason.TOOL_USE

    def test_invoke_with_assistant_tool_calls(self, mock_anthropic) -> None:
        """Should convert assistant messages with tool calls."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Done")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_response.model = "claude-3"
        mock_anthropic.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="test")
        tool_call = ToolCall(id="call_1", name="test", arguments={"x": 1})
        messages = [
            Message.user("Do something"),
            Message.assistant("I'll help", [tool_call]),
            Message.tool_result("call_1", "test", "Result"),
        ]

        asyncio.run(client.invoke(messages))

        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        # Check that messages were converted
        assert len(call_kwargs["messages"]) == 3

    def test_invoke_handles_api_error(self, mock_anthropic) -> None:
        """Should propagate API errors."""
        import anthropic
        from agentsh.agent.providers.anthropic import AnthropicClient

        mock_anthropic.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        client = AnthropicClient(api_key="test")

        with pytest.raises(anthropic.APIError):
            asyncio.run(client.invoke([Message.user("Test")]))

    def test_invoke_max_tokens_stop(self, mock_anthropic) -> None:
        """Should handle max_tokens stop reason."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Truncated...")]
        mock_response.stop_reason = "max_tokens"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=4096)
        mock_response.model = "claude-3"
        mock_anthropic.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="test")
        result = asyncio.run(client.invoke([Message.user("Long request")]))

        assert result.stop_reason == StopReason.MAX_TOKENS


class TestAnthropicClientStream:
    """Tests for AnthropicClient stream method."""

    @pytest.fixture
    def mock_anthropic(self):
        """Create mock Anthropic client."""
        with patch("anthropic.AsyncAnthropic") as mock:
            mock_instance = MagicMock()
            mock_instance.messages = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_stream_yields_text(self, mock_anthropic) -> None:
        """Should yield text chunks from stream."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        # Mock async iterator
        async def mock_text_stream():
            yield "Hello"
            yield " World"

        mock_stream = MagicMock()
        mock_stream.text_stream = mock_text_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock()

        mock_anthropic.messages.stream = MagicMock(return_value=mock_stream)

        client = AnthropicClient(api_key="test")

        async def collect_stream():
            chunks = []
            async for chunk in client.stream([Message.user("Hi")]):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect_stream())
        assert chunks == ["Hello", " World"]


class TestAnthropicClientMessageConversion:
    """Tests for message conversion."""

    @pytest.fixture
    def mock_anthropic(self):
        """Create mock Anthropic client."""
        with patch("anthropic.AsyncAnthropic") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_convert_user_message(self, mock_anthropic) -> None:
        """Should convert user message."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test")
        messages = [Message.user("Hello")]

        system, converted = client._convert_messages(messages)

        assert system == ""
        assert len(converted) == 1
        assert converted[0]["role"] == "user"
        assert converted[0]["content"] == "Hello"

    def test_convert_assistant_message(self, mock_anthropic) -> None:
        """Should convert assistant message."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test")
        messages = [Message.assistant("Response")]

        system, converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "assistant"
        assert converted[0]["content"] == "Response"

    def test_convert_tool_result(self, mock_anthropic) -> None:
        """Should convert tool result to user message."""
        from agentsh.agent.providers.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test")
        messages = [Message.tool_result("call_1", "test", "Result")]

        system, converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "user"
        assert converted[0]["content"][0]["type"] == "tool_result"


class TestAnthropicClientTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_estimate(self) -> None:
        """Should estimate token count."""
        with patch("anthropic.AsyncAnthropic"):
            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")

            # ~4 chars per token
            result = client.count_tokens("Hello World")  # 11 chars
            assert result == 2  # 11 // 4 = 2
