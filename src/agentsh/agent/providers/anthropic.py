"""Anthropic LLM Provider - Claude integration."""

import json
import os
from typing import Any, AsyncIterator, Optional

import anthropic

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


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client.

    Supports Claude models with tool use capabilities.

    Example:
        client = AnthropicClient(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="claude-sonnet-4-20250514",
        )
        response = await client.invoke([Message.user("Hello!")])
        print(response.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key. Uses ANTHROPIC_API_KEY env var if not provided.
            model: Model to use (default: claude-sonnet-4-20250514)
            max_retries: Number of retries on transient errors
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._max_retries = max_retries
        self._timeout = timeout

        if not self._api_key:
            logger.warning("No Anthropic API key provided")

        self._client = anthropic.AsyncAnthropic(
            api_key=self._api_key,
            max_retries=max_retries,
            timeout=timeout,
        )

        logger.info(
            "Anthropic client initialized",
            model=model,
            has_api_key=bool(self._api_key),
        )

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "anthropic"

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
        """Invoke Claude with messages and optional tools.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool calls
        """
        # Convert messages to Anthropic format
        system_prompt, anthropic_messages = self._convert_messages(messages)

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = [t.to_anthropic_format() for t in tools]

        logger.debug(
            "Invoking Anthropic API",
            model=self._model,
            message_count=len(anthropic_messages),
            has_tools=bool(tools),
        )

        try:
            response = await self._client.messages.create(**kwargs)
            return self._parse_response(response)
        except anthropic.APIError as e:
            logger.error("Anthropic API error", error=str(e))
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from Claude.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Text chunks as they are generated
        """
        system_prompt, anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = [t.to_anthropic_format() for t in tools]

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Convert our messages to Anthropic format.

        Args:
            messages: List of Message objects

        Returns:
            Tuple of (system_prompt, anthropic_messages)
        """
        system_prompt = ""
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Anthropic uses a separate system parameter
                system_prompt = msg.content
            elif msg.role == MessageRole.USER:
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                if msg.tool_calls:
                    # Assistant message with tool use
                    content: list[dict[str, Any]] = []
                    if msg.content:
                        content.append({"type": "text", "text": msg.content})
                    for tc in msg.tool_calls:
                        content.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        )
                    anthropic_messages.append({"role": "assistant", "content": content})
                else:
                    anthropic_messages.append(
                        {"role": "assistant", "content": msg.content}
                    )
            elif msg.role == MessageRole.TOOL:
                # Tool result message
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )

        return system_prompt, anthropic_messages

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        """Parse Anthropic response to our format.

        Args:
            response: Anthropic API response

        Returns:
            LLMResponse object
        """
        content = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input) if block.input else {},
                    )
                )

        # Map stop reason
        stop_reason_map = {
            "end_turn": StopReason.END_TURN,
            "tool_use": StopReason.TOOL_USE,
            "max_tokens": StopReason.MAX_TOKENS,
            "stop_sequence": StopReason.STOP_SEQUENCE,
        }
        stop_reason = stop_reason_map.get(response.stop_reason, StopReason.END_TURN)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        # Anthropic uses cl100k_base-like tokenizer
        # Rough estimate: ~4 characters per token
        return len(text) // 4
