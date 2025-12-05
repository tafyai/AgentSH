"""LLM Provider implementations.

Supported providers:
- AnthropicClient: Claude models via Anthropic API
- OpenAIClient: GPT models via OpenAI API
- OllamaClient: Local models via Ollama
- LiteLLMClient: 100+ models via LiteLLM (unified interface)
- OpenRouterClient: 200+ models via OpenRouter API
"""

from agentsh.agent.providers.anthropic import AnthropicClient
from agentsh.agent.providers.ollama import OllamaClient
from agentsh.agent.providers.openai import OpenAIClient
from agentsh.agent.providers.openrouter import OpenRouterClient

# LiteLLM is optional (requires litellm package)
try:
    from agentsh.agent.providers.litellm import LiteLLMClient

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    LiteLLMClient = None  # type: ignore

__all__ = [
    "AnthropicClient",
    "OpenAIClient",
    "OllamaClient",
    "OpenRouterClient",
    "LiteLLMClient",
]


def get_client(provider: str, **kwargs):
    """Factory function to get an LLM client by provider name.

    Args:
        provider: Provider name (anthropic, openai, ollama, openrouter, litellm)
        **kwargs: Provider-specific configuration

    Returns:
        LLMClient instance

    Example:
        client = get_client("anthropic", model="claude-sonnet-4-20250514")
        client = get_client("ollama", model="llama3.2")
        client = get_client("openrouter", model="anthropic/claude-3.5-sonnet")
    """
    providers = {
        "anthropic": AnthropicClient,
        "openai": OpenAIClient,
        "ollama": OllamaClient,
        "openrouter": OpenRouterClient,
    }

    if _LITELLM_AVAILABLE:
        providers["litellm"] = LiteLLMClient

    provider_lower = provider.lower()
    if provider_lower not in providers:
        available = list(providers.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")

    return providers[provider_lower](**kwargs)
