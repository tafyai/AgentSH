"""Tests for OpenRouter LLM provider."""

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
from agentsh.agent.providers.openrouter import OpenRouterClient


class TestOpenRouterClientInit:
    """Tests for OpenRouterClient initialization."""

    def test_default_init(self) -> None:
        """Should initialize with defaults."""
        client = OpenRouterClient(api_key="test-key")
        assert client.model == "anthropic/claude-3.5-sonnet"
        assert client.provider == "openrouter"

    def test_custom_model(self) -> None:
        """Should accept custom model."""
        client = OpenRouterClient(api_key="test-key", model="openai/gpt-4o")
        assert client.model == "openai/gpt-4o"

    def test_model_shortcut(self) -> None:
        """Should expand model shortcuts."""
        client = OpenRouterClient(api_key="test-key", model="gpt-4o")
        assert client.model == "openai/gpt-4o"

    def test_model_shortcut_claude(self) -> None:
        """Should expand Claude shortcut."""
        client = OpenRouterClient(api_key="test-key", model="claude-3.5-sonnet")
        assert client.model == "anthropic/claude-3.5-sonnet"

    def test_env_var_api_key(self) -> None:
        """Should use OPENROUTER_API_KEY env var."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            client = OpenRouterClient()
            assert client._api_key == "env-key"

    def test_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        client = OpenRouterClient(api_key="test-key", timeout=300.0)
        assert client._timeout == 300.0

    def test_site_info(self) -> None:
        """Should accept site info for rankings."""
        client = OpenRouterClient(
            api_key="test-key",
            site_url="https://myapp.com",
            site_name="MyApp",
        )
        assert client._site_url == "https://myapp.com"
        assert client._site_name == "MyApp"


class TestOpenRouterClientMessageConversion:
    """Tests for message conversion."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create client instance."""
        return OpenRouterClient(api_key="test-key")

    def test_convert_system_message(self, client: OpenRouterClient) -> None:
        """Should convert system message."""
        messages = [Message.system("You are helpful.")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "system", "content": "You are helpful."}]

    def test_convert_user_message(self, client: OpenRouterClient) -> None:
        """Should convert user message."""
        messages = [Message.user("Hello")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "user", "content": "Hello"}]

    def test_convert_assistant_message(self, client: OpenRouterClient) -> None:
        """Should convert assistant message."""
        messages = [Message.assistant("Hi there!")]
        converted = client._convert_messages(messages)
        assert converted == [{"role": "assistant", "content": "Hi there!"}]

    def test_convert_assistant_with_tool_calls(self, client: OpenRouterClient) -> None:
        """Should convert assistant message with tool calls."""
        tool_calls = [ToolCall(id="call_1", name="search", arguments={"q": "test"})]
        messages = [Message.assistant("Searching...", tool_calls=tool_calls)]
        converted = client._convert_messages(messages)

        assert len(converted) == 1
        assert converted[0]["role"] == "assistant"
        assert "tool_calls" in converted[0]
        assert converted[0]["tool_calls"][0]["function"]["name"] == "search"

    def test_convert_tool_result(self, client: OpenRouterClient) -> None:
        """Should convert tool result message."""
        messages = [Message.tool_result("call_1", "search", "Results found")]
        converted = client._convert_messages(messages)
        assert converted[0]["role"] == "tool"
        assert converted[0]["tool_call_id"] == "call_1"
        assert converted[0]["content"] == "Results found"


class TestOpenRouterClientResponseParsing:
    """Tests for response parsing."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create client instance."""
        return OpenRouterClient(api_key="test-key")

    def test_parse_simple_response(self, client: OpenRouterClient) -> None:
        """Should parse simple text response."""
        data = {
            "choices": [
                {
                    "message": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "model": "anthropic/claude-3.5-sonnet",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        response = client._parse_response(data)

        assert response.content == "Hello!"
        assert response.stop_reason == StopReason.END_TURN
        assert response.model == "anthropic/claude-3.5-sonnet"
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    def test_parse_tool_call_response(self, client: OpenRouterClient) -> None:
        """Should parse response with tool calls."""
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
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
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "openai/gpt-4o",
        }
        response = client._parse_response(data)

        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_weather"
        assert response.stop_reason == StopReason.TOOL_USE

    def test_parse_max_tokens_response(self, client: OpenRouterClient) -> None:
        """Should detect max tokens stop reason."""
        data = {
            "choices": [
                {
                    "message": {"content": "Truncated..."},
                    "finish_reason": "length",
                }
            ],
        }
        response = client._parse_response(data)
        assert response.stop_reason == StopReason.MAX_TOKENS


class TestOpenRouterClientInvoke:
    """Tests for invoke method."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create client instance."""
        return OpenRouterClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_invoke_success(self, client: OpenRouterClient) -> None:
        """Should invoke successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await client.invoke([Message.user("Hi")])

        assert response.content == "Hello!"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client: OpenRouterClient) -> None:
        """Should include tools in request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "I'll help."},
                    "finish_reason": "stop",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        tools = [
            ToolDefinition(
                name="search",
                description="Search web",
                parameters={"query": {"type": "string"}},
                required=["query"],
            )
        ]

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await client.invoke([Message.user("Search")], tools=tools)

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert "tools" in payload


class TestOpenRouterClientStream:
    """Tests for stream method."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create client instance."""
        return OpenRouterClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_stream_yields_content(self, client: OpenRouterClient) -> None:
        """Should yield content chunks."""

        async def mock_aiter_lines():
            lines = [
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " world"}}]}',
                "data: [DONE]",
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


class TestOpenRouterClientUtilities:
    """Tests for utility methods."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create client instance."""
        return OpenRouterClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_list_models(self, client: OpenRouterClient) -> None:
        """Should list available models."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "anthropic/claude-3.5-sonnet"},
                {"id": "openai/gpt-4o"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            models = await client.list_models()

        assert len(models) == 2

    @pytest.mark.asyncio
    async def test_list_models_error(self, client: OpenRouterClient) -> None:
        """Should handle error listing models."""
        import httpx

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("API error")
            models = await client.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_get_credits(self, client: OpenRouterClient) -> None:
        """Should get remaining credits."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"limit_remaining": 50.0}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            credits = await client.get_credits()

        assert credits == 50.0

    @pytest.mark.asyncio
    async def test_get_credits_error(self, client: OpenRouterClient) -> None:
        """Should handle error getting credits."""
        import httpx

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Unauthorized")
            credits = await client.get_credits()

        assert credits is None

    @pytest.mark.asyncio
    async def test_get_generation_stats(self, client: OpenRouterClient) -> None:
        """Should get generation stats."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"tokens_prompt": 100, "tokens_completion": 50}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            stats = await client.get_generation_stats("gen_123")

        assert stats["tokens_prompt"] == 100

    def test_count_tokens(self, client: OpenRouterClient) -> None:
        """Should estimate token count."""
        text = "Hello world, this is a test."
        count = client.count_tokens(text)
        assert count == len(text) // 4

    def test_get_model_shortcuts(self) -> None:
        """Should return model shortcuts."""
        shortcuts = OpenRouterClient.get_model_shortcuts()
        assert "gpt-4o" in shortcuts
        assert "claude-3.5-sonnet" in shortcuts
        assert shortcuts["auto"] == "openrouter/auto"

    @pytest.mark.asyncio
    async def test_close(self, client: OpenRouterClient) -> None:
        """Should close HTTP client."""
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()


class TestOpenRouterModelShortcuts:
    """Tests for model shortcut resolution."""

    def test_all_shortcuts_resolve(self) -> None:
        """All shortcuts should resolve to full model names."""
        for shortcut, full_name in OpenRouterClient.MODELS.items():
            client = OpenRouterClient(api_key="test", model=shortcut)
            assert client.model == full_name

    def test_full_model_name_unchanged(self) -> None:
        """Full model names should not be changed."""
        client = OpenRouterClient(api_key="test", model="meta-llama/llama-3.1-70b-instruct")
        assert client.model == "meta-llama/llama-3.1-70b-instruct"
