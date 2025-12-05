"""LiteLLM Provider - Unified interface for 100+ LLM providers."""

import json
import os
from typing import Any, AsyncIterator, Optional

from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    MessageRole,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)

# Try to import litellm
try:
    import litellm
    from litellm import acompletion

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None  # type: ignore
    acompletion = None  # type: ignore


class LiteLLMClient(LLMClient):
    """LiteLLM unified client for 100+ LLM providers.

    Supports providers including:
    - OpenAI, Azure OpenAI
    - Anthropic Claude
    - Google Gemini, Vertex AI
    - AWS Bedrock
    - Ollama
    - Groq, Together AI, Anyscale
    - Hugging Face, Replicate
    - And many more...

    Example:
        # OpenAI
        client = LiteLLMClient(model="gpt-4o")

        # Anthropic
        client = LiteLLMClient(model="claude-sonnet-4-20250514")

        # AWS Bedrock
        client = LiteLLMClient(model="bedrock/anthropic.claude-3-sonnet-20240229-v1:0")

        # Ollama
        client = LiteLLMClient(model="ollama/llama3.2")

        response = await client.invoke([Message.user("Hello!")])
        print(response.content)
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """Initialize the LiteLLM client.

        Args:
            model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-20250514", "ollama/llama3.2")
            api_key: API key (if not set via environment)
            api_base: Custom API base URL
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient errors
            **kwargs: Additional provider-specific parameters
        """
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "litellm is not installed. Install with: pip install litellm"
            )

        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._timeout = timeout
        self._max_retries = max_retries
        self._extra_kwargs = kwargs

        # Configure litellm
        litellm.set_verbose = False

        # Determine provider from model name
        self._provider_name = self._detect_provider(model)

        logger.info(
            "LiteLLM client initialized",
            model=model,
            provider=self._provider_name,
            api_base=api_base,
        )

    def _detect_provider(self, model: str) -> str:
        """Detect the underlying provider from model name.

        Args:
            model: Model identifier

        Returns:
            Provider name
        """
        model_lower = model.lower()
        if model_lower.startswith("gpt") or model_lower.startswith("o1"):
            return "openai"
        elif model_lower.startswith("claude"):
            return "anthropic"
        elif model_lower.startswith("gemini"):
            return "google"
        elif model_lower.startswith("bedrock/"):
            return "bedrock"
        elif model_lower.startswith("azure/"):
            return "azure"
        elif model_lower.startswith("ollama/"):
            return "ollama"
        elif model_lower.startswith("groq/"):
            return "groq"
        elif model_lower.startswith("together_ai/"):
            return "together_ai"
        elif model_lower.startswith("replicate/"):
            return "replicate"
        elif model_lower.startswith("huggingface/"):
            return "huggingface"
        elif model_lower.startswith("vertex_ai/"):
            return "vertex_ai"
        else:
            return "litellm"

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return f"litellm/{self._provider_name}"

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._model

    async def invoke(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Invoke the model with messages and optional tools.

        Args:
            messages: Conversation history
            tools: Available tools (function calling)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool calls
        """
        litellm_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": litellm_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self._timeout,
            "num_retries": self._max_retries,
        }

        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        # Add any extra provider-specific kwargs
        kwargs.update(self._extra_kwargs)

        logger.debug(
            "Invoking LiteLLM API",
            model=self._model,
            message_count=len(litellm_messages),
            has_tools=bool(tools),
        )

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error("LiteLLM API error", error=str(e))
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from the model.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Text chunks as they are generated
        """
        litellm_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": litellm_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "timeout": self._timeout,
        }

        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        kwargs.update(self._extra_kwargs)

        response = await acompletion(**kwargs)
        async for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    yield delta.content

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert our messages to LiteLLM format (OpenAI-compatible).

        Args:
            messages: List of Message objects

        Returns:
            List of LiteLLM-formatted messages
        """
        litellm_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                litellm_messages.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                litellm_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                if msg.tool_calls:
                    litellm_messages.append(
                        {
                            "role": "assistant",
                            "content": msg.content or None,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(tc.arguments),
                                    },
                                }
                                for tc in msg.tool_calls
                            ],
                        }
                    )
                else:
                    litellm_messages.append(
                        {"role": "assistant", "content": msg.content}
                    )
            elif msg.role == MessageRole.TOOL:
                litellm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )

        return litellm_messages

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response to our format.

        Args:
            response: LiteLLM API response

        Returns:
            LLMResponse object
        """
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls: list[ToolCall] = []

        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, AttributeError):
                    arguments = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Map finish reason
        finish_reason = getattr(choice, "finish_reason", "stop") or "stop"
        finish_reason_map = {
            "stop": StopReason.END_TURN,
            "tool_calls": StopReason.TOOL_USE,
            "function_call": StopReason.TOOL_USE,
            "length": StopReason.MAX_TOKENS,
            "content_filter": StopReason.STOP_SEQUENCE,
        }
        stop_reason = finish_reason_map.get(finish_reason, StopReason.END_TURN)

        # If we have tool calls, override stop reason
        if tool_calls:
            stop_reason = StopReason.TOOL_USE

        # Get token usage
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=getattr(response, "model", self._model),
        )

    @staticmethod
    def list_supported_models() -> list[str]:
        """List a sample of supported models.

        Returns:
            List of example model identifiers
        """
        return [
            # OpenAI
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1-preview",
            # Anthropic
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
            # Google
            "gemini/gemini-1.5-pro",
            "gemini/gemini-1.5-flash",
            # AWS Bedrock
            "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
            "bedrock/amazon.titan-text-express-v1",
            # Azure
            "azure/gpt-4o",
            # Ollama
            "ollama/llama3.2",
            "ollama/mistral",
            "ollama/codellama",
            # Groq
            "groq/llama-3.1-70b-versatile",
            "groq/mixtral-8x7b-32768",
            # Together AI
            "together_ai/meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            # Replicate
            "replicate/meta/llama-2-70b-chat",
        ]

    def count_tokens(self, text: str) -> int:
        """Estimate token count.

        Args:
            text: Text to count

        Returns:
            Estimated token count
        """
        # Use litellm's token counting if available
        if LITELLM_AVAILABLE and litellm is not None:
            try:
                return litellm.token_counter(model=self._model, text=text)
            except Exception:
                pass
        # Fallback to rough estimate
        return len(text) // 4
