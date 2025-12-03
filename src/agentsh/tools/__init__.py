"""Tool interface and registry for AgentSH."""

from agentsh.tools.base import Tool, ToolResult, RiskLevel
from agentsh.tools.registry import ToolRegistry, get_tool_registry

__all__ = [
    "Tool",
    "ToolResult",
    "RiskLevel",
    "ToolRegistry",
    "get_tool_registry",
]
