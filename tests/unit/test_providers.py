"""Tests for LLM provider implementations."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.agent.llm_client import (
    Message,
    MessageRole,
    StopReason,
    ToolCall,
    ToolDefinition,
)


class TestAnthropicClient:
    """Tests for AnthropicClient."""

    def test_init_with_api_key(self) -> None:
        """Should initialize with explicit API key."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test-key", model="claude-3-sonnet")

            assert client.provider == "anthropic"
            assert client.model == "claude-3-sonnet"

    def test_init_from_env_var(self) -> None:
        """Should use environment variable for API key."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
                from agentsh.agent.providers.anthropic import AnthropicClient

                client = AnthropicClient()

                assert client._api_key == "env-key"

    def test_init_no_api_key_warning(self) -> None:
        """Should warn when no API key provided."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            with patch.dict(os.environ, {}, clear=True):
                # Remove ANTHROPIC_API_KEY if it exists
                env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
                with patch.dict(os.environ, env_without_key, clear=True):
                    from agentsh.agent.providers.anthropic import AnthropicClient

                    client = AnthropicClient(api_key=None)
                    # Should have empty string
                    assert client._api_key == ""

    def test_provider_property(self) -> None:
        """Should return 'anthropic' as provider."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")
            assert client.provider == "anthropic"

    def test_model_property(self) -> None:
        """Should return model name."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test", model="claude-3-opus")
            assert client.model == "claude-3-opus"

    def test_default_model(self) -> None:
        """Should use default model."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")
            assert "claude" in client.model.lower()

    @pytest.mark.asyncio
    async def test_invoke_simple_message(self) -> None:
        """Should invoke with simple message."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(type="text", text="Hello!")]
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")
            messages = [Message.user("Hi")]

            response = await client.invoke(messages)

            assert response.content == "Hello!"
            assert response.input_tokens == 10
            assert response.output_tokens == 5

    @pytest.mark.asyncio
    async def test_invoke_with_tools(self) -> None:
        """Should invoke with tool definitions."""
        with patch("agentsh.agent.providers.anthropic.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()

            # Create a proper mock for the tool use content block
            tool_content = MagicMock()
            tool_content.type = "tool_use"
            tool_content.id = "call_1"
            tool_content.name = "test_tool"
            tool_content.input = {"arg": "value"}

            mock_response.content = [tool_content]
            mock_response.stop_reason = "tool_use"
            mock_usage = MagicMock()
            mock_usage.input_tokens = 20
            mock_usage.output_tokens = 10
            mock_response.usage = mock_usage
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from agentsh.agent.providers.anthropic import AnthropicClient

            client = AnthropicClient(api_key="test")
            messages = [Message.user("Use the tool")]
            tools = [
                ToolDefinition(
                    name="test_tool",
                    description="A test tool",
                    parameters={"arg": {"type": "string"}},
                )
            ]

            response = await client.invoke(messages, tools=tools)

            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "test_tool"


class TestOpenAIClient:
    """Tests for OpenAIClient."""

    def test_init_with_api_key(self) -> None:
        """Should initialize with explicit API key."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test-key", model="gpt-4")

            assert client.provider == "openai"
            assert client.model == "gpt-4"

    def test_init_from_env_var(self) -> None:
        """Should use environment variable for API key."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()

            with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
                from agentsh.agent.providers.openai import OpenAIClient

                client = OpenAIClient()

                assert client._api_key == "env-key"

    def test_provider_property(self) -> None:
        """Should return 'openai' as provider."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            assert client.provider == "openai"

    def test_model_property(self) -> None:
        """Should return model name."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test", model="gpt-4-turbo")
            assert client.model == "gpt-4-turbo"

    def test_default_model(self) -> None:
        """Should use default model."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            assert "gpt" in client.model.lower()

    @pytest.mark.asyncio
    async def test_invoke_simple_message(self) -> None:
        """Should invoke with simple message."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_client = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "Hello from GPT!"
            mock_choice.message.tool_calls = None
            mock_choice.finish_reason = "stop"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            messages = [Message.user("Hi")]

            response = await client.invoke(messages)

            assert response.content == "Hello from GPT!"
            assert response.input_tokens == 10
            assert response.output_tokens == 5

    @pytest.mark.asyncio
    async def test_invoke_with_tools(self) -> None:
        """Should invoke with tool definitions."""
        with patch("agentsh.agent.providers.openai.openai") as mock_openai:
            mock_client = MagicMock()
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_1"
            mock_tool_call.function.name = "test_tool"
            mock_tool_call.function.arguments = '{"arg": "value"}'

            mock_choice = MagicMock()
            mock_choice.message.content = None
            mock_choice.message.tool_calls = [mock_tool_call]
            mock_choice.finish_reason = "tool_calls"

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(prompt_tokens=20, completion_tokens=10)

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client

            from agentsh.agent.providers.openai import OpenAIClient

            client = OpenAIClient(api_key="test")
            messages = [Message.user("Use the tool")]
            tools = [
                ToolDefinition(
                    name="test_tool",
                    description="A test tool",
                    parameters={"arg": {"type": "string"}},
                )
            ]

            response = await client.invoke(messages, tools=tools)

            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "test_tool"


class TestProvidersInit:
    """Tests for providers __init__.py."""

    def test_imports(self) -> None:
        """Should export provider classes."""
        from agentsh.agent.providers import AnthropicClient, OpenAIClient

        assert AnthropicClient is not None
        assert OpenAIClient is not None
