"""Tests for tool registry."""

import pytest

from agentsh.tools.base import RiskLevel, Tool, ToolResult
from agentsh.tools.registry import ToolRegistry


class TestToolRegistry:
    """Test tool registration and lookup."""

    def test_register_tool(self, tool_registry: ToolRegistry) -> None:
        """Should register a tool successfully."""

        def handler(x: int) -> int:
            return x * 2

        tool = tool_registry.register_tool(
            name="test.double",
            handler=handler,
            description="Double a number",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        )

        assert tool.name == "test.double"
        assert tool.risk_level == RiskLevel.SAFE

    def test_duplicate_registration_fails(self, tool_registry: ToolRegistry) -> None:
        """Should not allow duplicate tool names."""
        tool_registry.register_tool(
            name="test.tool",
            handler=lambda: None,
            description="Test",
            parameters={},
        )

        with pytest.raises(ValueError, match="already registered"):
            tool_registry.register_tool(
                name="test.tool",
                handler=lambda: None,
                description="Duplicate",
                parameters={},
            )

    def test_get_tool(self, tool_registry: ToolRegistry) -> None:
        """Should retrieve registered tool."""
        tool_registry.register_tool(
            name="test.get",
            handler=lambda: None,
            description="Test",
            parameters={},
        )

        tool = tool_registry.get_tool("test.get")
        assert tool is not None
        assert tool.name == "test.get"

        # Non-existent tool
        assert tool_registry.get_tool("nonexistent") is None

    def test_list_tools(self, tool_registry: ToolRegistry) -> None:
        """Should list all registered tools."""
        tool_registry.register_tool(
            name="test.a", handler=lambda: None, description="A", parameters={}
        )
        tool_registry.register_tool(
            name="test.b", handler=lambda: None, description="B", parameters={}
        )

        tools = tool_registry.list_tools()
        names = tool_registry.list_tool_names()

        assert len(tools) == 2
        assert set(names) == {"test.a", "test.b"}

    def test_filter_by_risk_level(self, tool_registry: ToolRegistry) -> None:
        """Should filter tools by risk level."""
        tool_registry.register_tool(
            name="safe.tool",
            handler=lambda: None,
            description="Safe",
            parameters={},
            risk_level=RiskLevel.SAFE,
        )
        tool_registry.register_tool(
            name="high.tool",
            handler=lambda: None,
            description="High risk",
            parameters={},
            risk_level=RiskLevel.HIGH,
        )

        safe_tools = tool_registry.get_tools_by_risk_level(RiskLevel.SAFE)
        high_tools = tool_registry.get_tools_by_risk_level(RiskLevel.HIGH)

        assert len(safe_tools) == 1
        assert safe_tools[0].name == "safe.tool"
        assert len(high_tools) == 1

    def test_openai_schema_generation(self, tool_registry: ToolRegistry) -> None:
        """Should generate OpenAI-compatible schemas."""
        tool_registry.register_tool(
            name="test.schema",
            handler=lambda: None,
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {"arg": {"type": "string"}},
            },
        )

        schemas = tool_registry.get_openai_schemas()

        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "test.schema"

    def test_anthropic_schema_generation(self, tool_registry: ToolRegistry) -> None:
        """Should generate Anthropic-compatible schemas."""
        tool_registry.register_tool(
            name="test.schema",
            handler=lambda: None,
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {"arg": {"type": "string"}},
            },
        )

        schemas = tool_registry.get_anthropic_schemas()

        assert len(schemas) == 1
        assert schemas[0]["name"] == "test.schema"
        assert "input_schema" in schemas[0]


class TestToolResult:
    """Test ToolResult formatting."""

    def test_successful_result(self) -> None:
        """Test successful result formatting."""
        result = ToolResult(success=True, output="Hello, World!")
        assert result.to_llm_format() == "Hello, World!"

    def test_empty_output(self) -> None:
        """Test empty output formatting."""
        result = ToolResult(success=True, output="")
        assert result.to_llm_format() == "(No output)"

    def test_error_result(self) -> None:
        """Test error result formatting."""
        result = ToolResult(success=False, error="Command failed")
        assert "Error:" in result.to_llm_format()
        assert "Command failed" in result.to_llm_format()
