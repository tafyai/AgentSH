"""OpenRouter Provider - Access 200+ models through a unified API."""

import json
import os
from typing import Any, AsyncIterator, Optional

import httpx

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

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterClient(LLMClient):
    """OpenRouter unified API client for 200+ models.

    OpenRouter provides access to models from:
    - OpenAI (GPT-4, GPT-4o, o1)
    - Anthropic (Claude 3.5, Claude 3)
    - Google (Gemini Pro, Gemini Flash)
    - Meta (Llama 3.2, Llama 3.1)
    - Mistral (Mixtral, Mistral Large)
    - And many more...

    Features:
    - Automatic fallback between providers
    - Usage-based pricing
    - Model routing and load balancing

    Example:
        client = OpenRouterClient(
            api_key=os.environ["OPENROUTER_API_KEY"],
            model="anthropic/claude-sonnet-4-20250514",
        )
        response = await client.invoke([Message.user("Hello!")])
        print(response.content)
    """

    # Popular model shortcuts
    MODELS = {
        # Anthropic
        "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
        "claude-3-opus": "anthropic/claude-3-opus",
        "claude-3-sonnet": "anthropic/claude-3-sonnet",
        "claude-3-haiku": "anthropic/claude-3-haiku",
        # OpenAI
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4-turbo": "openai/gpt-4-turbo",
        "o1-preview": "openai/o1-preview",
        "o1-mini": "openai/o1-mini",
        # Google
        "gemini-pro": "google/gemini-pro-1.5",
        "gemini-flash": "google/gemini-flash-1.5",
        # Meta Llama
        "llama-3.2-90b": "meta-llama/llama-3.2-90b-vision-instruct",
        "llama-3.1-405b": "meta-llama/llama-3.1-405b-instruct",
        "llama-3.1-70b": "meta-llama/llama-3.1-70b-instruct",
        # Mistral
        "mixtral-8x22b": "mistralai/mixtral-8x22b-instruct",
        "mistral-large": "mistralai/mistral-large",
        # Auto-router (best model for the job)
        "auto": "openrouter/auto",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-3.5-sonnet",
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key. Uses OPENROUTER_API_KEY env var if not provided.
            model: Model to use (e.g., "anthropic/claude-3.5-sonnet", "openai/gpt-4o")
            site_url: Your site URL for rankings (optional)
            site_name: Your site name for rankings (optional)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient errors
        """
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._timeout = timeout
        self._max_retries = max_retries

        # Resolve model shortcut if used
        self._model = self.MODELS.get(model, model)

        # Optional site info for OpenRouter rankings
        self._site_url = site_url
        self._site_name = site_name or "agentsh"

        if not self._api_key:
            logger.warning("No OpenRouter API key provided")

        self._client = httpx.AsyncClient(
            base_url=OPENROUTER_API_BASE,
            timeout=timeout,
            headers=self._build_headers(),
        )

        logger.info(
            "OpenRouter client initialized",
            model=self._model,
            has_api_key=bool(self._api_key),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url or "https://github.com/agentsh",
            "X-Title": self._site_name,
        }
        return headers

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "openrouter"

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
        openrouter_messages = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": openrouter_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]

        logger.debug(
            "Invoking OpenRouter API",
            model=self._model,
            message_count=len(openrouter_messages),
            has_tools=bool(tools),
        )

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except httpx.HTTPError as e:
            logger.error("OpenRouter API error", error=str(e))
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
        openrouter_messages = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": openrouter_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]

        async with self._client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert our messages to OpenRouter format (OpenAI-compatible).

        Args:
            messages: List of Message objects

        Returns:
            List of OpenRouter-formatted messages
        """
        openrouter_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                openrouter_messages.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                openrouter_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                if msg.tool_calls:
                    openrouter_messages.append(
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
                    openrouter_messages.append(
                        {"role": "assistant", "content": msg.content}
                    )
            elif msg.role == MessageRole.TOOL:
                openrouter_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )

        return openrouter_messages

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse OpenRouter response to our format.

        Args:
            data: OpenRouter API response

        Returns:
            LLMResponse object
        """
        choice = data["choices"][0]
        message = choice.get("message", {})

        content = message.get("content") or ""
        tool_calls: list[ToolCall] = []

        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", f"call_{len(tool_calls)}"),
                        name=func.get("name", ""),
                        arguments=args,
                    )
                )

        # Map finish reason
        finish_reason = choice.get("finish_reason", "stop")
        finish_reason_map = {
            "stop": StopReason.END_TURN,
            "tool_calls": StopReason.TOOL_USE,
            "length": StopReason.MAX_TOKENS,
            "content_filter": StopReason.STOP_SEQUENCE,
        }
        stop_reason = finish_reason_map.get(finish_reason, StopReason.END_TURN)

        if tool_calls:
            stop_reason = StopReason.TOOL_USE

        # Get token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=data.get("model", self._model),
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models on OpenRouter.

        Returns:
            List of model info dictionaries
        """
        try:
            response = await self._client.get("/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPError as e:
            logger.error("Failed to list OpenRouter models", error=str(e))
            return []

    async def get_credits(self) -> Optional[float]:
        """Get remaining API credits.

        Returns:
            Remaining credits in USD, or None if unavailable
        """
        try:
            response = await self._client.get("/auth/key")
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("limit_remaining")
        except httpx.HTTPError as e:
            logger.error("Failed to get OpenRouter credits", error=str(e))
            return None

    async def get_generation_stats(self, generation_id: str) -> Optional[dict[str, Any]]:
        """Get stats for a specific generation.

        Args:
            generation_id: The generation ID from a response

        Returns:
            Generation stats or None
        """
        try:
            response = await self._client.get(f"/generation?id={generation_id}")
            response.raise_for_status()
            return response.json().get("data")
        except httpx.HTTPError as e:
            logger.error("Failed to get generation stats", error=str(e))
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def count_tokens(self, text: str) -> int:
        """Estimate token count.

        Args:
            text: Text to count

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    @classmethod
    def get_model_shortcuts(cls) -> dict[str, str]:
        """Get available model shortcuts.

        Returns:
            Dictionary of shortcut -> full model name
        """
        return cls.MODELS.copy()
