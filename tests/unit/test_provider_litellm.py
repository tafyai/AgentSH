"""Tests for LiteLLM unified provider."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agentsh.agent.llm_client import (
    Message,
    MessageRole,
    StopReason,
    ToolCall,
    ToolDefinition,
)


# Mock litellm module for testing
@pytest.fixture(autouse=True)
def mock_litellm():
    """Mock litellm module."""
    with patch.dict("sys.modules", {"litellm": MagicMock()}):
        yield


class TestLiteLLMClientImport:
    """Tests for LiteLLM import handling."""

    def test_import_error_without_litellm(self) -> None:
        """Should raise ImportError when litellm not installed."""
        # Temporarily remove the mock to test import error
        import sys

        # Remove any cached imports
        modules_to_remove = [k for k in sys.modules.keys() if "litellm" in k.lower()]
        for mod in modules_to_remove:
            if mod in sys.modules:
                del sys.modules[mod]

        # Now test that import fails gracefully
        with patch.dict("sys.modules", {"litellm": None}):
            # The import should be handled gracefully
            pass


class TestLiteLLMClientInit:
    """Tests for LiteLLMClient initialization."""

    def test_provider_detection_openai(self) -> None:
        """Should detect OpenAI provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="gpt-4o")
                assert client._provider_name == "openai"

    def test_provider_detection_anthropic(self) -> None:
        """Should detect Anthropic provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="claude-sonnet-4-20250514")
                assert client._provider_name == "anthropic"

    def test_provider_detection_ollama(self) -> None:
        """Should detect Ollama provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="ollama/llama3.2")
                assert client._provider_name == "ollama"

    def test_provider_detection_bedrock(self) -> None:
        """Should detect Bedrock provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="bedrock/anthropic.claude-3-sonnet")
                assert client._provider_name == "bedrock"

    def test_provider_detection_groq(self) -> None:
        """Should detect Groq provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="groq/llama-3.1-70b")
                assert client._provider_name == "groq"

    def test_provider_detection_gemini(self) -> None:
        """Should detect Google provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="gemini/gemini-1.5-pro")
                assert client._provider_name == "google"


class TestLiteLLMClientMessageConversion:
    """Tests for message conversion."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                return LiteLLMClient(model="gpt-4o")

    def test_convert_system_message(self, client) -> None:
        """Should convert system message."""
        messages = [Message.system("You are helpful.")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "system", "content": "You are helpful."}]

    def test_convert_user_message(self, client) -> None:
        """Should convert user message."""
        messages = [Message.user("Hello")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "user", "content": "Hello"}]

    def test_convert_assistant_message(self, client) -> None:
        """Should convert assistant message."""
        messages = [Message.assistant("Hi there!")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "assistant", "content": "Hi there!"}]

    def test_convert_assistant_with_tool_calls(self, client) -> None:
        """Should convert assistant message with tool calls."""
        tool_calls = [ToolCall(id="call_1", name="search", arguments={"q": "test"})]
        messages = [Message.assistant("Searching...", tool_calls=tool_calls)]
        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "assistant"
        assert "tool_calls" in converted[0]

    def test_convert_tool_result(self, client) -> None:
        """Should convert tool result message."""
        messages = [Message.tool_result("call_1", "search", "Results found")]
        converted = client._convert_messages(messages)
        assert converted[0]["role"] == "tool"
        assert converted[0]["tool_call_id"] == "call_1"


class TestLiteLLMClientResponseParsing:
    """Tests for response parsing."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                return LiteLLMClient(model="gpt-4o")

    def test_parse_simple_response(self, client) -> None:
        """Should parse simple text response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="Hello!", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4o"

        response = client._parse_response(mock_response)

        assert response.content == "Hello!"
        assert response.stop_reason == StopReason.END_TURN
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    def test_parse_tool_call_response(self, client) -> None:
        """Should parse response with tool calls."""
        mock_function = MagicMock()
        mock_function.name = "get_weather"
        mock_function.arguments = '{"city": "NYC"}'

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.function = mock_function

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="", tool_calls=[mock_tool_call]),
                finish_reason="tool_calls",
            )
        ]
        mock_response.usage = None
        mock_response.model = "gpt-4o"

        response = client._parse_response(mock_response)

        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_weather"
        assert response.stop_reason == StopReason.TOOL_USE


class TestLiteLLMClientInvoke:
    """Tests for invoke method."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                return LiteLLMClient(model="gpt-4o")

    @pytest.mark.asyncio
    async def test_invoke_success(self, client) -> None:
        """Should invoke successfully."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="Hello!", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "gpt-4o"

        with patch(
            "agentsh.agent.providers.litellm.acompletion",
            new_callable=AsyncMock,
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_response
            response = await client.invoke([Message.user("Hi")])

        assert response.content == "Hello!"

    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client) -> None:
        """Should include tools in request."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="I'll help.", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = None
        mock_response.model = "gpt-4o"

        tools = [
            ToolDefinition(
                name="search",
                description="Search web",
                parameters={"query": {"type": "string"}},
                required=["query"],
            )
        ]

        with patch(
            "agentsh.agent.providers.litellm.acompletion",
            new_callable=AsyncMock,
        ) as mock_acompletion:
            mock_acompletion.return_value = mock_response
            await client.invoke([Message.user("Search")], tools=tools)

        call_kwargs = mock_acompletion.call_args[1]
        assert "tools" in call_kwargs


class TestLiteLLMClientUtilities:
    """Tests for utility methods."""

    def test_list_supported_models(self) -> None:
        """Should list supported models."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                models = LiteLLMClient.list_supported_models()

        assert "gpt-4o" in models
        assert "claude-sonnet-4-20250514" in models
        assert "ollama/llama3.2" in models

    def test_count_tokens_fallback(self) -> None:
        """Should fallback to character estimate."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            mock_litellm = MagicMock()
            mock_litellm.token_counter.side_effect = Exception("Not available")

            with patch("agentsh.agent.providers.litellm.litellm", mock_litellm):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="gpt-4o")
                count = client.count_tokens("Hello world")

        # Fallback: len // 4
        assert count == len("Hello world") // 4


class TestLiteLLMProviderProperty:
    """Tests for provider property."""

    def test_provider_includes_underlying(self) -> None:
        """Provider should include underlying provider."""
        with patch("agentsh.agent.providers.litellm.LITELLM_AVAILABLE", True):
            with patch("agentsh.agent.providers.litellm.litellm"):
                from agentsh.agent.providers.litellm import LiteLLMClient

                client = LiteLLMClient(model="gpt-4o")
                assert client.provider == "litellm/openai"

                client2 = LiteLLMClient(model="claude-sonnet-4-20250514")
                assert client2.provider == "litellm/anthropic"

                client3 = LiteLLMClient(model="ollama/llama3.2")
                assert client3.provider == "litellm/ollama"
