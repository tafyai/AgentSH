"""LLM Client Abstraction - Unified interface for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class MessageRole(Enum):
    """Role of a message in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """Represents a tool call from the LLM.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to call
        arguments: Tool arguments as a dictionary
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """A message in the conversation.

    Attributes:
        role: The role of the message sender
        content: The text content of the message
        tool_calls: List of tool calls (for assistant messages)
        tool_call_id: ID of the tool call this message responds to (for tool messages)
        name: Name of the tool (for tool messages)
    """

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        d: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(
        cls, content: str, tool_calls: Optional[list[ToolCall]] = None
    ) -> "Message":
        """Create an assistant message."""
        return cls(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "Message":
        """Create a tool result message."""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM consumption.

    Attributes:
        name: Unique tool name
        description: Human-readable description
        parameters: JSON Schema for parameters
        required: List of required parameter names
    """

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] = field(default_factory=list)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required,
            },
        }


class StopReason(Enum):
    """Reason why the LLM stopped generating."""

    END_TURN = "end_turn"  # Natural end of response
    TOOL_USE = "tool_use"  # Wants to use a tool
    MAX_TOKENS = "max_tokens"  # Hit token limit
    STOP_SEQUENCE = "stop_sequence"  # Hit a stop sequence
    ERROR = "error"  # An error occurred


@dataclass
class LLMResponse:
    """Response from an LLM.

    Attributes:
        content: The text content of the response
        tool_calls: List of tool calls to execute
        stop_reason: Why the LLM stopped generating
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        model: The model that generated this response
    """

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: StopReason = StopReason.END_TURN
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class LLMClient(ABC):
    """Abstract base class for LLM clients.

    This provides a unified interface for different LLM providers
    (Anthropic, OpenAI, Ollama, etc.).

    Example:
        client = AnthropicClient(api_key="...", model="claude-sonnet-4-20250514")
        messages = [Message.user("Hello, what's 2+2?")]
        response = await client.invoke(messages)
        print(response.content)
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """Get the provider name (e.g., 'anthropic', 'openai')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Get the model name."""
        ...

    @abstractmethod
    async def invoke(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Invoke the LLM with messages and optional tools.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool calls
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        ...

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Default implementation uses a rough estimate.
        Providers can override with their own tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token for English
        return len(text) // 4
