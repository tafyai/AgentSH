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


class TestToolRegistryExtended:
    """Extended tests for tool registry."""

    def test_unregister_tool(self, tool_registry: ToolRegistry) -> None:
        """Should unregister a tool."""
        tool_registry.register_tool(
            name="test.unregister",
            handler=lambda: None,
            description="Test",
            parameters={},
        )

        assert tool_registry.get_tool("test.unregister") is not None

        result = tool_registry.unregister_tool("test.unregister")
        assert result is True
        assert tool_registry.get_tool("test.unregister") is None

    def test_unregister_nonexistent_tool(self, tool_registry: ToolRegistry) -> None:
        """Should return False for non-existent tool."""
        result = tool_registry.unregister_tool("nonexistent.tool")
        assert result is False

    def test_clear_tools(self, tool_registry: ToolRegistry) -> None:
        """Should clear all tools."""
        tool_registry.register_tool(
            name="test.a", handler=lambda: None, description="A", parameters={}
        )
        tool_registry.register_tool(
            name="test.b", handler=lambda: None, description="B", parameters={}
        )

        assert len(tool_registry.list_tools()) == 2

        tool_registry.clear()

        assert len(tool_registry.list_tools()) == 0

    def test_get_tools_by_plugin(self, tool_registry: ToolRegistry) -> None:
        """Should get tools by plugin name."""
        tool_registry.register_tool(
            name="plugin1.tool",
            handler=lambda: None,
            description="Tool 1",
            parameters={},
            plugin_name="plugin1",
        )
        tool_registry.register_tool(
            name="plugin2.tool",
            handler=lambda: None,
            description="Tool 2",
            parameters={},
            plugin_name="plugin2",
        )
        tool_registry.register_tool(
            name="plugin1.other",
            handler=lambda: None,
            description="Other",
            parameters={},
            plugin_name="plugin1",
        )

        plugin1_tools = tool_registry.get_tools_by_plugin("plugin1")
        plugin2_tools = tool_registry.get_tools_by_plugin("plugin2")

        assert len(plugin1_tools) == 2
        assert len(plugin2_tools) == 1
        assert plugin2_tools[0].name == "plugin2.tool"

    def test_get_tools_by_plugin_empty(self, tool_registry: ToolRegistry) -> None:
        """Should return empty list for unknown plugin."""
        tools = tool_registry.get_tools_by_plugin("nonexistent")
        assert tools == []

    def test_register_with_all_options(self, tool_registry: ToolRegistry) -> None:
        """Should register tool with all options."""
        tool = tool_registry.register_tool(
            name="full.tool",
            handler=lambda x: x,
            description="Full options tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            timeout_seconds=60,
            max_retries=5,
            examples=["example1", "example2"],
            plugin_name="test_plugin",
        )

        assert tool.name == "full.tool"
        assert tool.risk_level == RiskLevel.MEDIUM
        assert tool.requires_confirmation is True
        assert tool.timeout_seconds == 60
        assert tool.max_retries == 5
        assert len(tool.examples) == 2
        assert tool.plugin_name == "test_plugin"


class TestGetToolRegistry:
    """Tests for get_tool_registry function."""

    def test_get_tool_registry_returns_same_instance(self) -> None:
        """Should return same instance on multiple calls."""
        from agentsh.tools.registry import get_tool_registry, _tool_registry
        import agentsh.tools.registry as registry_module

        # Reset global
        registry_module._tool_registry = None

        first = get_tool_registry()
        second = get_tool_registry()

        assert first is second

    def test_get_tool_registry_creates_new_if_none(self) -> None:
        """Should create new registry if global is None."""
        import agentsh.tools.registry as registry_module
        from agentsh.tools.registry import get_tool_registry

        # Reset global
        registry_module._tool_registry = None

        registry = get_tool_registry()

        assert registry is not None
        assert isinstance(registry, ToolRegistry)
