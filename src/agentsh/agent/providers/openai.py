"""OpenAI LLM Provider - GPT integration."""

import json
import os
from typing import Any, AsyncIterator, Optional

import openai

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


class OpenAIClient(LLMClient):
    """OpenAI GPT LLM client.

    Supports GPT-4 and GPT-3.5 models with function calling.

    Example:
        client = OpenAIClient(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o",
        )
        response = await client.invoke([Message.user("Hello!")])
        print(response.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. Uses OPENAI_API_KEY env var if not provided.
            model: Model to use (default: gpt-4o)
            base_url: Optional custom base URL (for Azure, etc.)
            max_retries: Number of retries on transient errors
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = base_url
        self._max_retries = max_retries
        self._timeout = timeout

        if not self._api_key:
            logger.warning("No OpenAI API key provided")

        self._client = openai.AsyncOpenAI(
            api_key=self._api_key,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
        )

        logger.info(
            "OpenAI client initialized",
            model=model,
            has_api_key=bool(self._api_key),
            base_url=base_url,
        )

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "openai"

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
        """Invoke GPT with messages and optional tools.

        Args:
            messages: Conversation history
            tools: Available tools (function calling)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool calls
        """
        openai_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
        }

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        logger.debug(
            "Invoking OpenAI API",
            model=self._model,
            message_count=len(openai_messages),
            has_tools=bool(tools),
        )

        try:
            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from GPT.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Text chunks as they are generated
        """
        openai_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert our messages to OpenAI format.

        Args:
            messages: List of Message objects

        Returns:
            List of OpenAI-formatted messages
        """
        openai_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                openai_messages.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                openai_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                if msg.tool_calls:
                    # Assistant message with function calls
                    openai_messages.append(
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
                    openai_messages.append(
                        {"role": "assistant", "content": msg.content}
                    )
            elif msg.role == MessageRole.TOOL:
                # Tool/function result
                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )

        return openai_messages

    def _parse_response(
        self, response: openai.types.chat.ChatCompletion
    ) -> LLMResponse:
        """Parse OpenAI response to our format.

        Args:
            response: OpenAI API response

        Returns:
            LLMResponse object
        """
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Map finish reason
        finish_reason_map = {
            "stop": StopReason.END_TURN,
            "tool_calls": StopReason.TOOL_USE,
            "length": StopReason.MAX_TOKENS,
            "content_filter": StopReason.STOP_SEQUENCE,
        }
        stop_reason = finish_reason_map.get(
            choice.finish_reason or "stop", StopReason.END_TURN
        )

        # Get token usage
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=response.model,
        )

    def count_tokens(self, text: str) -> int:
        """Estimate token count.

        Args:
            text: Text to count

        Returns:
            Estimated token count
        """
        # GPT uses cl100k_base tokenizer
        # Rough estimate: ~4 characters per token
        return len(text) // 4
