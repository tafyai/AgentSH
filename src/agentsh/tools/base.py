"""Base classes for the tool system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RiskLevel(str, Enum):
    """Risk classification for tools and commands."""

    SAFE = "safe"  # Read-only, no side effects
    LOW = "low"  # Minor side effects, easily reversible
    MEDIUM = "medium"  # Significant changes, may need review
    HIGH = "high"  # Dangerous operations, requires approval
    CRITICAL = "critical"  # Extremely dangerous, blocked by default


@dataclass
class Tool:
    """Definition of a tool that the agent can use.

    Attributes:
        name: Unique tool name (e.g., 'shell.run', 'fs.read')
        description: Human-readable description for LLM
        handler: Callable that executes the tool
        parameters: JSON schema for tool parameters
        risk_level: Risk classification for security
        requires_confirmation: Whether to always require user confirmation
        timeout_seconds: Maximum execution time
        max_retries: Number of retry attempts on failure
        examples: Example usages for few-shot prompting
    """

    name: str
    description: str
    handler: Callable[..., Any]
    parameters: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    timeout_seconds: int = 30
    max_retries: int = 2
    examples: list[str] = field(default_factory=list)
    plugin_name: Optional[str] = None

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Convert to Anthropic tool use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully
        output: Output from the tool (stdout, return value, etc.)
        error: Error message if failed
        duration_ms: Execution time in milliseconds
        exit_code: Exit code for shell commands
        metadata: Additional result metadata
    """

    success: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0
    exit_code: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_format(self) -> str:
        """Format result for LLM consumption."""
        if self.success:
            return self.output if self.output else "(No output)"
        else:
            return f"Error: {self.error or 'Unknown error'}"


@dataclass
class ToolCall:
    """Represents a tool call from the LLM.

    Attributes:
        id: Unique identifier for this call
        name: Tool name to invoke
        arguments: Arguments to pass to the tool
    """

    id: str
    name: str
    arguments: dict[str, Any]
