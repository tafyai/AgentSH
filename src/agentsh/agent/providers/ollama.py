"""Ollama LLM Provider - Local LLM integration via Ollama."""

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


class OllamaClient(LLMClient):
    """Ollama local LLM client.

    Supports running local models via Ollama with optional tool use.

    Example:
        client = OllamaClient(
            model="llama3.2",
            base_url="http://localhost:11434",
        )
        response = await client.invoke([Message.user("Hello!")])
        print(response.content)
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        keep_alive: str = "5m",
    ) -> None:
        """Initialize the Ollama client.

        Args:
            model: Model to use (e.g., llama3.2, mistral, codellama)
            base_url: Ollama server URL. Uses OLLAMA_HOST env var or defaults to localhost.
            timeout: Request timeout in seconds (longer for local inference)
            keep_alive: How long to keep model loaded (e.g., "5m", "1h", "-1" for forever)
        """
        self._model = model
        self._base_url = (
            base_url
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        self._timeout = timeout
        self._keep_alive = keep_alive

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
        )

        logger.info(
            "Ollama client initialized",
            model=model,
            base_url=self._base_url,
        )

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "ollama"

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
        """Invoke local model with messages and optional tools.

        Args:
            messages: Conversation history
            tools: Available tools (requires Ollama 0.4+ with tool support)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool calls
        """
        ollama_messages = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": self._keep_alive,
        }

        if tools:
            # Ollama uses OpenAI-compatible tool format
            payload["tools"] = [t.to_openai_format() for t in tools]

        logger.debug(
            "Invoking Ollama API",
            model=self._model,
            message_count=len(ollama_messages),
            has_tools=bool(tools),
        )

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except httpx.HTTPError as e:
            logger.error("Ollama API error", error=str(e))
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from local model.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Text chunks as they are generated
        """
        ollama_messages = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": self._keep_alive,
        }

        if tools:
            payload["tools"] = [t.to_openai_format() for t in tools]

        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            content = data["message"]["content"]
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert our messages to Ollama format (OpenAI-compatible).

        Args:
            messages: List of Message objects

        Returns:
            List of Ollama-formatted messages
        """
        ollama_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                ollama_messages.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                ollama_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                if msg.tool_calls:
                    ollama_messages.append(
                        {
                            "role": "assistant",
                            "content": msg.content or "",
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
                    ollama_messages.append(
                        {"role": "assistant", "content": msg.content}
                    )
            elif msg.role == MessageRole.TOOL:
                ollama_messages.append(
                    {
                        "role": "tool",
                        "content": msg.content,
                    }
                )

        return ollama_messages

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse Ollama response to our format.

        Args:
            data: Ollama API response

        Returns:
            LLMResponse object
        """
        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls: list[ToolCall] = []

        # Parse tool calls if present
        if "tool_calls" in message:
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

        # Determine stop reason
        done_reason = data.get("done_reason", "")
        if tool_calls:
            stop_reason = StopReason.TOOL_USE
        elif done_reason == "length":
            stop_reason = StopReason.MAX_TOKENS
        elif done_reason == "stop":
            stop_reason = StopReason.END_TURN
        else:
            stop_reason = StopReason.END_TURN

        # Token counts (if available)
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=data.get("model", self._model),
        )

    async def list_models(self) -> list[str]:
        """List available models on the Ollama server.

        Returns:
            List of model names
        """
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except httpx.HTTPError as e:
            logger.error("Failed to list Ollama models", error=str(e))
            return []

    async def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama library.

        Args:
            model: Model name to pull

        Returns:
            True if successful
        """
        try:
            response = await self._client.post(
                "/api/pull",
                json={"name": model, "stream": False},
                timeout=600.0,  # Long timeout for model download
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to pull model", model=model, error=str(e))
            return False

    async def is_available(self) -> bool:
        """Check if Ollama server is available.

        Returns:
            True if server is responding
        """
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to count

        Returns:
            Estimated token count (rough approximation)
        """
        # Most LLMs use similar tokenization
        # Rough estimate: ~4 characters per token
        return len(text) // 4
