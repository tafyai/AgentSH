"""Tests for provider module initialization and factory."""

import pytest
from unittest.mock import patch

from agentsh.agent.providers import (
    AnthropicClient,
    OpenAIClient,
    OllamaClient,
    OpenRouterClient,
    get_client,
)


class TestProviderExports:
    """Tests for provider exports."""

    def test_anthropic_client_exported(self) -> None:
        """Should export AnthropicClient."""
        assert AnthropicClient is not None

    def test_openai_client_exported(self) -> None:
        """Should export OpenAIClient."""
        assert OpenAIClient is not None

    def test_ollama_client_exported(self) -> None:
        """Should export OllamaClient."""
        assert OllamaClient is not None

    def test_openrouter_client_exported(self) -> None:
        """Should export OpenRouterClient."""
        assert OpenRouterClient is not None


class TestGetClientFactory:
    """Tests for get_client factory function."""

    def test_get_anthropic_client(self) -> None:
        """Should create Anthropic client."""
        client = get_client("anthropic", api_key="test-key")
        assert isinstance(client, AnthropicClient)
        assert client.provider == "anthropic"

    def test_get_openai_client(self) -> None:
        """Should create OpenAI client."""
        client = get_client("openai", api_key="test-key")
        assert isinstance(client, OpenAIClient)
        assert client.provider == "openai"

    def test_get_ollama_client(self) -> None:
        """Should create Ollama client."""
        client = get_client("ollama", model="llama3.2")
        assert isinstance(client, OllamaClient)
        assert client.provider == "ollama"

    def test_get_openrouter_client(self) -> None:
        """Should create OpenRouter client."""
        client = get_client("openrouter", api_key="test-key")
        assert isinstance(client, OpenRouterClient)
        assert client.provider == "openrouter"

    def test_get_client_case_insensitive(self) -> None:
        """Should be case insensitive."""
        client1 = get_client("ANTHROPIC", api_key="test")
        client2 = get_client("Anthropic", api_key="test")
        client3 = get_client("anthropic", api_key="test")

        assert isinstance(client1, AnthropicClient)
        assert isinstance(client2, AnthropicClient)
        assert isinstance(client3, AnthropicClient)

    def test_get_client_unknown_provider(self) -> None:
        """Should raise ValueError for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            get_client("unknown")

        assert "Unknown provider" in str(exc_info.value)
        assert "anthropic" in str(exc_info.value)

    def test_get_client_with_custom_kwargs(self) -> None:
        """Should pass kwargs to client."""
        client = get_client(
            "openai",
            api_key="test-key",
            model="gpt-4-turbo",
            timeout=120.0,
        )

        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4-turbo"


class TestProviderClientProperties:
    """Tests for common client properties."""

    def test_anthropic_properties(self) -> None:
        """Should have correct Anthropic properties."""
        client = AnthropicClient(api_key="test")
        assert client.provider == "anthropic"
        assert "claude" in client.model.lower()

    def test_openai_properties(self) -> None:
        """Should have correct OpenAI properties."""
        client = OpenAIClient(api_key="test")
        assert client.provider == "openai"
        assert "gpt" in client.model.lower()

    def test_ollama_properties(self) -> None:
        """Should have correct Ollama properties."""
        client = OllamaClient()
        assert client.provider == "ollama"
        assert client.model == "llama3.2"

    def test_openrouter_properties(self) -> None:
        """Should have correct OpenRouter properties."""
        client = OpenRouterClient(api_key="test")
        assert client.provider == "openrouter"
