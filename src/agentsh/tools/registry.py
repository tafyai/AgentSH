"""Tool registry for managing available tools."""

from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger
from agentsh.tools.base import RiskLevel, Tool

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry for all available tools.

    The registry maintains a collection of Tool definitions that can be:
    - Registered by plugins/toolsets
    - Queried by the agent
    - Converted to LLM schema format
    - Executed via the ToolRunner
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str,
        parameters: dict[str, Any],
        risk_level: RiskLevel = RiskLevel.SAFE,
        requires_confirmation: bool = False,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        examples: Optional[list[str]] = None,
        plugin_name: Optional[str] = None,
    ) -> Tool:
        """Register a new tool.

        Args:
            name: Unique tool name (e.g., 'shell.run')
            handler: Callable that executes the tool
            description: Human-readable description
            parameters: JSON schema for parameters
            risk_level: Risk classification
            requires_confirmation: Always require confirmation
            timeout_seconds: Execution timeout
            max_retries: Retry attempts on failure
            examples: Example usages
            plugin_name: Name of plugin providing this tool

        Returns:
            The registered Tool instance

        Raises:
            ValueError: If tool name is already registered
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        tool = Tool(
            name=name,
            description=description,
            handler=handler,
            parameters=parameters,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            examples=examples or [],
            plugin_name=plugin_name,
        )

        self._tools[name] = tool
        logger.debug("Registered tool", name=name, risk_level=risk_level.value)
        return tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Get all registered tools.

        Returns:
            List of all Tool instances
        """
        return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tools_by_risk_level(self, risk_level: RiskLevel) -> list[Tool]:
        """Get tools filtered by risk level.

        Args:
            risk_level: Risk level to filter by

        Returns:
            List of tools with the specified risk level
        """
        return [t for t in self._tools.values() if t.risk_level == risk_level]

    def get_tools_by_plugin(self, plugin_name: str) -> list[Tool]:
        """Get tools provided by a specific plugin.

        Args:
            plugin_name: Plugin name to filter by

        Returns:
            List of tools from the specified plugin
        """
        return [t for t in self._tools.values() if t.plugin_name == plugin_name]

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI function calling format.

        Returns:
            List of tool schemas in OpenAI format
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Get all tools in Anthropic tool use format.

        Returns:
            List of tool schemas in Anthropic format
        """
        return [tool.to_anthropic_schema() for tool in self._tools.values()]

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.debug("Unregistered tool", name=name)
            return True
        return False

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
        logger.debug("Cleared all tools")


# Global tool registry
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
