"""Tests for Ollama LLM provider."""

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
from agentsh.agent.providers.ollama import OllamaClient


class TestOllamaClientInit:
    """Tests for OllamaClient initialization."""

    def test_default_init(self) -> None:
        """Should initialize with defaults."""
        client = OllamaClient()
        assert client.model == "llama3.2"
        assert client.provider == "ollama"
        assert client._base_url == "http://localhost:11434"

    def test_custom_model(self) -> None:
        """Should accept custom model."""
        client = OllamaClient(model="mistral")
        assert client.model == "mistral"

    def test_custom_base_url(self) -> None:
        """Should accept custom base URL."""
        client = OllamaClient(base_url="http://custom:11434")
        assert client._base_url == "http://custom:11434"

    def test_strips_trailing_slash(self) -> None:
        """Should strip trailing slash from base URL."""
        client = OllamaClient(base_url="http://localhost:11434/")
        assert client._base_url == "http://localhost:11434"

    def test_env_var_base_url(self) -> None:
        """Should use OLLAMA_HOST env var."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://env-host:11434"}):
            client = OllamaClient()
            assert client._base_url == "http://env-host:11434"

    def test_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        client = OllamaClient(timeout=300.0)
        assert client._timeout == 300.0

    def test_keep_alive_setting(self) -> None:
        """Should accept keep_alive setting."""
        client = OllamaClient(keep_alive="10m")
        assert client._keep_alive == "10m"


class TestOllamaClientMessageConversion:
    """Tests for message conversion."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create client instance."""
        return OllamaClient()

    def test_convert_system_message(self, client: OllamaClient) -> None:
        """Should convert system message."""
        messages = [Message.system("You are helpful.")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "system", "content": "You are helpful."}]

    def test_convert_user_message(self, client: OllamaClient) -> None:
        """Should convert user message."""
        messages = [Message.user("Hello")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "user", "content": "Hello"}]

    def test_convert_assistant_message(self, client: OllamaClient) -> None:
        """Should convert assistant message."""
        messages = [Message.assistant("Hi there!")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "assistant", "content": "Hi there!"}]

    def test_convert_assistant_with_tool_calls(self, client: OllamaClient) -> None:
        """Should convert assistant message with tool calls."""
        tool_calls = [ToolCall(id="call_1", name="get_weather", arguments={"city": "NYC"})]
        messages = [Message.assistant("Let me check", tool_calls=tool_calls)]
        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "assistant"
        assert "tool_calls" in converted[0]
        assert converted[0]["tool_calls"][0]["function"]["name"] == "get_weather"

    def test_convert_tool_result(self, client: OllamaClient) -> None:
        """Should convert tool result message."""
        messages = [Message.tool_result("call_1", "get_weather", "Sunny, 72F")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "tool", "content": "Sunny, 72F"}]


class TestOllamaClientResponseParsing:
    """Tests for response parsing."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create client instance."""
        return OllamaClient()

    def test_parse_simple_response(self, client: OllamaClient) -> None:
        """Should parse simple text response."""
        data = {
            "message": {"content": "Hello!"},
            "done_reason": "stop",
            "model": "llama3.2",
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        response = client._parse_response(data)

        assert response.content == "Hello!"
        assert response.stop_reason == StopReason.END_TURN
        assert response.model == "llama3.2"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert not response.has_tool_calls

    def test_parse_tool_call_response(self, client: OllamaClient) -> None:
        """Should parse response with tool calls."""
        data = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "NYC"}',
                        },
                    }
                ],
            },
            "done_reason": "stop",
            "model": "llama3.2",
        }
        response = client._parse_response(data)

        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].arguments == {"city": "NYC"}
        assert response.stop_reason == StopReason.TOOL_USE

    def test_parse_max_tokens_response(self, client: OllamaClient) -> None:
        """Should detect max tokens stop reason."""
        data = {
            "message": {"content": "Truncated..."},
            "done_reason": "length",
            "model": "llama3.2",
        }
        response = client._parse_response(data)
        assert response.stop_reason == StopReason.MAX_TOKENS

    def test_parse_tool_call_with_dict_arguments(self, client: OllamaClient) -> None:
        """Should handle tool call with dict arguments."""
        data = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "search",
                            "arguments": {"query": "test"},  # Already a dict
                        },
                    }
                ],
            },
            "done_reason": "stop",
        }
        response = client._parse_response(data)
        assert response.tool_calls[0].arguments == {"query": "test"}


class TestOllamaClientInvoke:
    """Tests for invoke method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create client instance."""
        return OllamaClient()

    @pytest.mark.asyncio
    async def test_invoke_success(self, client: OllamaClient) -> None:
        """Should invoke successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Hello!"},
            "done_reason": "stop",
            "model": "llama3.2",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await client.invoke([Message.user("Hi")])

        assert response.content == "Hello!"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client: OllamaClient) -> None:
        """Should include tools in request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "I'll help."},
            "done_reason": "stop",
        }
        mock_response.raise_for_status = MagicMock()

        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get weather",
                parameters={"city": {"type": "string"}},
                required=["city"],
            )
        ]

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await client.invoke([Message.user("Weather?")], tools=tools)

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert "tools" in payload


class TestOllamaClientStream:
    """Tests for stream method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create client instance."""
        return OllamaClient()

    @pytest.mark.asyncio
    async def test_stream_yields_content(self, client: OllamaClient) -> None:
        """Should yield content chunks."""

        async def mock_aiter_lines():
            lines = [
                '{"message": {"content": "Hello"}}',
                '{"message": {"content": " world"}}',
                '{"done": true}',
            ]
            for line in lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_response

        with patch.object(client._client, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in client.stream([Message.user("Hi")]):
                chunks.append(chunk)

        assert "Hello" in chunks
        assert " world" in chunks


class TestOllamaClientUtilities:
    """Tests for utility methods."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create client instance."""
        return OllamaClient()

    @pytest.mark.asyncio
    async def test_list_models(self, client: OllamaClient) -> None:
        """Should list available models."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2"},
                {"name": "mistral"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            models = await client.list_models()

        assert "llama3.2" in models
        assert "mistral" in models

    @pytest.mark.asyncio
    async def test_list_models_error(self, client: OllamaClient) -> None:
        """Should handle error listing models."""
        import httpx

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")
            models = await client.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_is_available_true(self, client: OllamaClient) -> None:
        """Should return True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            available = await client.is_available()

        assert available is True

    @pytest.mark.asyncio
    async def test_is_available_false(self, client: OllamaClient) -> None:
        """Should return False when server is down."""
        import httpx

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection refused")
            available = await client.is_available()

        assert available is False

    @pytest.mark.asyncio
    async def test_pull_model_success(self, client: OllamaClient) -> None:
        """Should pull model successfully."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.pull_model("llama3.2")

        assert result is True

    @pytest.mark.asyncio
    async def test_pull_model_failure(self, client: OllamaClient) -> None:
        """Should handle pull failure."""
        import httpx

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPError("Not found")
            result = await client.pull_model("nonexistent")

        assert result is False

    def test_count_tokens(self, client: OllamaClient) -> None:
        """Should estimate token count."""
        text = "Hello world, this is a test."
        count = client.count_tokens(text)
        # Rough estimate: ~4 chars per token
        assert count == len(text) // 4

    @pytest.mark.asyncio
    async def test_close(self, client: OllamaClient) -> None:
        """Should close HTTP client."""
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()
