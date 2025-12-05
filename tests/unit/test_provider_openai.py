"""Tests for OpenAI LLM provider."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.agent.llm_client import Message, StopReason, ToolCall, ToolDefinition


class TestOpenAIClientInitialization:
    """Tests for OpenAIClient initialization."""

    def test_init_with_api_key(self) -> None:
        """Should initialize with provided API key."""
        with patch("openai.AsyncOpenAI") as mock_client:
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test-key", model="gpt-4")

            assert client._api_key == "test-key"
            assert client._model == "gpt-4"
            mock_client.assert_called_once()

    def test_init_with_env_key(self) -> None:
        """Should use environment variable if no key provided."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            with patch("openai.AsyncOpenAI"):
                from agentsh.agent.providers.openai import OpenAIClient

                client = OpenAIClient()
                assert client._api_key == "env-key"

    def test_init_warns_without_key(self) -> None:
        """Should warn if no API key available."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            with patch("openai.AsyncOpenAI"):
                with patch("agentsh.agent.providers.openai.logger") as mock_logger:
                    from agentsh.agent.providers.openai import OpenAIClient

                    OpenAIClient(api_key="")
                    mock_logger.warning.assert_called()

    def test_init_with_base_url(self) -> None:
        """Should support custom base URL."""
        with patch("openai.AsyncOpenAI") as mock_client:
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(
                api_key="test",
                base_url="https://custom.api.com",
            )

            assert client._base_url == "https://custom.api.com"
            mock_client.assert_called_with(
                api_key="test",
                base_url="https://custom.api.com",
                max_retries=3,
                timeout=60.0,
            )

    def test_init_custom_settings(self) -> None:
        """Should use custom settings."""
        with patch("openai.AsyncOpenAI"):
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(
                api_key="test",
                max_retries=5,
                timeout=120.0,
            )

            assert client._max_retries == 5
            assert client._timeout == 120.0

    def test_provider_property(self) -> None:
        """Should return provider name."""
        with patch("openai.AsyncOpenAI"):
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            assert client.provider == "openai"

    def test_model_property(self) -> None:
        """Should return model name."""
        with patch("openai.AsyncOpenAI"):
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test", model="gpt-4-turbo")
            assert client.model == "gpt-4-turbo"


class TestOpenAIClientInvoke:
    """Tests for OpenAIClient invoke method."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        with patch("openai.AsyncOpenAI") as mock:
            mock_instance = MagicMock()
            mock_instance.chat = MagicMock()
            mock_instance.chat.completions = MagicMock()
            mock_instance.chat.completions.create = AsyncMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_invoke_simple_message(self, mock_openai) -> None:
        """Should invoke with simple message."""
        from agentsh.agent.providers.openai import OpenAIClient

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Hello!", tool_calls=None)
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        messages = [Message.user("Hello")]

        result = asyncio.run(client.invoke(messages))

        assert result.content == "Hello!"
        assert result.stop_reason == StopReason.END_TURN
        mock_openai.chat.completions.create.assert_called_once()

    def test_invoke_with_system_prompt(self, mock_openai) -> None:
        """Should include system message in messages."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Response", tool_calls=None)
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        messages = [
            Message.system("You are helpful"),
            Message.user("Hello"),
        ]

        asyncio.run(client.invoke(messages))

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "You are helpful"

    def test_invoke_with_tools(self, mock_openai) -> None:
        """Should pass tools to API."""
        from agentsh.agent.providers.openai import OpenAIClient

        # Create explicit mock for function
        mock_function = MagicMock()
        mock_function.name = "test_tool"
        mock_function.arguments = '{"arg": "value"}'

        mock_tc = MagicMock()
        mock_tc.id = "tool_1"
        mock_tc.type = "function"
        mock_tc.function = mock_function

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content=None, tool_calls=[mock_tc])
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
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
        assert result.tool_calls[0].arguments == {"arg": "value"}
        assert result.stop_reason == StopReason.TOOL_USE

    def test_invoke_with_invalid_tool_args(self, mock_openai) -> None:
        """Should handle invalid JSON in tool arguments."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_tc = MagicMock()
        mock_tc.id = "tool_1"
        mock_tc.type = "function"
        mock_tc.function = MagicMock(
            name="test_tool",
            arguments='invalid json',
        )

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content=None, tool_calls=[mock_tc])
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        result = asyncio.run(client.invoke([Message.user("Test")]))

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments == {}  # Empty due to parse error

    def test_invoke_with_assistant_tool_calls(self, mock_openai) -> None:
        """Should convert assistant messages with tool calls."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Done", tool_calls=None)
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        tool_call = ToolCall(id="call_1", name="test", arguments={"x": 1})
        messages = [
            Message.user("Do something"),
            Message.assistant("I'll help", [tool_call]),
            Message.tool_result("call_1", "test", "Result"),
        ]

        asyncio.run(client.invoke(messages))

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        # Check that messages were converted
        assert len(call_kwargs["messages"]) == 3

    def test_invoke_handles_api_error(self, mock_openai) -> None:
        """Should propagate API errors."""
        import openai
        from agentsh.agent.providers.openai import OpenAIClient

        mock_openai.chat.completions.create.side_effect = openai.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        client = OpenAIClient(api_key="test")

        with pytest.raises(openai.APIError):
            asyncio.run(client.invoke([Message.user("Test")]))

    def test_invoke_length_stop(self, mock_openai) -> None:
        """Should handle length stop reason."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Truncated...", tool_calls=None)
        mock_choice.finish_reason = "length"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=4096)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        result = asyncio.run(client.invoke([Message.user("Long request")]))

        assert result.stop_reason == StopReason.MAX_TOKENS

    def test_invoke_content_filter_stop(self, mock_openai) -> None:
        """Should handle content_filter stop reason."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="", tool_calls=None)
        mock_choice.finish_reason = "content_filter"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=0)
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        result = asyncio.run(client.invoke([Message.user("Problematic content")]))

        assert result.stop_reason == StopReason.STOP_SEQUENCE

    def test_invoke_no_usage(self, mock_openai) -> None:
        """Should handle response without usage info."""
        from agentsh.agent.providers.openai import OpenAIClient

        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Response", tool_calls=None)
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4"
        mock_openai.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test")
        result = asyncio.run(client.invoke([Message.user("Test")]))

        assert result.input_tokens == 0
        assert result.output_tokens == 0


class TestOpenAIClientStream:
    """Tests for OpenAIClient stream method."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        with patch("openai.AsyncOpenAI") as mock:
            mock_instance = MagicMock()
            mock_instance.chat = MagicMock()
            mock_instance.chat.completions = MagicMock()
            mock_instance.chat.completions.create = AsyncMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_stream_yields_text(self, mock_openai) -> None:
        """Should yield text chunks from stream."""
        from agentsh.agent.providers.openai import OpenAIClient

        # Mock async iterator for streaming
        async def mock_stream_iter():
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            yield chunk1

            chunk2 = MagicMock()
            chunk2.choices = [MagicMock(delta=MagicMock(content=" World"))]
            yield chunk2

        mock_stream = mock_stream_iter()
        mock_openai.chat.completions.create.return_value = mock_stream

        client = OpenAIClient(api_key="test")

        async def collect_stream():
            chunks = []
            async for chunk in client.stream([Message.user("Hi")]):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect_stream())
        assert chunks == ["Hello", " World"]

    def test_stream_skips_empty_content(self, mock_openai) -> None:
        """Should skip chunks without content."""
        from agentsh.agent.providers.openai import OpenAIClient

        async def mock_stream_iter():
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            yield chunk1

            chunk2 = MagicMock()
            chunk2.choices = [MagicMock(delta=MagicMock(content=None))]
            yield chunk2

            chunk3 = MagicMock()
            chunk3.choices = []
            yield chunk3

        mock_stream = mock_stream_iter()
        mock_openai.chat.completions.create.return_value = mock_stream

        client = OpenAIClient(api_key="test")

        async def collect_stream():
            chunks = []
            async for chunk in client.stream([Message.user("Hi")]):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect_stream())
        assert chunks == ["Hello"]


class TestOpenAIClientMessageConversion:
    """Tests for message conversion."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        with patch("openai.AsyncOpenAI") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_convert_system_message(self, mock_openai) -> None:
        """Should convert system message."""
        from agentsh.agent.providers.openai import OpenAIClient

        client = OpenAIClient(api_key="test")
        messages = [Message.system("Be helpful")]

        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "system"
        assert converted[0]["content"] == "Be helpful"

    def test_convert_user_message(self, mock_openai) -> None:
        """Should convert user message."""
        from agentsh.agent.providers.openai import OpenAIClient

        client = OpenAIClient(api_key="test")
        messages = [Message.user("Hello")]

        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "user"
        assert converted[0]["content"] == "Hello"

    def test_convert_assistant_with_tool_calls(self, mock_openai) -> None:
        """Should convert assistant message with tool calls."""
        from agentsh.agent.providers.openai import OpenAIClient

        client = OpenAIClient(api_key="test")
        tool_call = ToolCall(id="call_1", name="test", arguments={"x": 1})
        messages = [Message.assistant("Using tool", [tool_call])]

        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "assistant"
        assert converted[0]["tool_calls"][0]["id"] == "call_1"
        assert converted[0]["tool_calls"][0]["function"]["name"] == "test"
        assert json.loads(converted[0]["tool_calls"][0]["function"]["arguments"]) == {"x": 1}

    def test_convert_tool_result(self, mock_openai) -> None:
        """Should convert tool result message."""
        from agentsh.agent.providers.openai import OpenAIClient

        client = OpenAIClient(api_key="test")
        messages = [Message.tool_result("call_1", "test", "Result")]

        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "tool"
        assert converted[0]["tool_call_id"] == "call_1"
        assert converted[0]["content"] == "Result"


class TestOpenAIClientTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_estimate(self) -> None:
        """Should estimate token count."""
        with patch("openai.AsyncOpenAI"):
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")

            # ~4 chars per token
            result = client.count_tokens("Hello World")  # 11 chars
            assert result == 2  # 11 // 4 = 2

    def test_count_tokens_empty_string(self) -> None:
        """Should handle empty string."""
        with patch("openai.AsyncOpenAI"):
            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            result = client.count_tokens("")
            assert result == 0
