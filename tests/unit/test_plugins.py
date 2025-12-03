"""Tests for plugin system."""

import pytest

from agentsh.plugins.base import Toolset, ToolsetRegistry
from agentsh.tools.registry import ToolRegistry


class DummyToolset(Toolset):
    """A dummy toolset for testing."""

    def __init__(self, name: str = "dummy") -> None:
        self._name = name
        self.configured = False
        self.initialized = False
        self.shutdown_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A dummy toolset for testing"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register_tool(
            name=f"{self.name}.test",
            handler=lambda: "test",
            description="Test tool",
            parameters={},
            plugin_name=self.name,
        )

    def configure(self, config: dict) -> None:
        self.configured = True
        self.config = config

    def initialize(self) -> None:
        self.initialized = True

    def shutdown(self) -> None:
        self.shutdown_called = True


class TestToolset:
    """Test Toolset base class."""

    def test_toolset_properties(self) -> None:
        """Toolset should have required properties."""
        toolset = DummyToolset("test")
        assert toolset.name == "test"
        assert isinstance(toolset.description, str)

    def test_toolset_lifecycle(self, tool_registry: ToolRegistry) -> None:
        """Toolset should support full lifecycle."""
        toolset = DummyToolset("lifecycle")

        # Configure
        toolset.configure({"key": "value"})
        assert toolset.configured
        assert toolset.config["key"] == "value"

        # Initialize
        toolset.initialize()
        assert toolset.initialized

        # Register tools
        toolset.register_tools(tool_registry)
        assert tool_registry.get_tool("lifecycle.test") is not None

        # Shutdown
        toolset.shutdown()
        assert toolset.shutdown_called


class TestToolsetRegistry:
    """Test ToolsetRegistry."""

    def test_register_toolset(self) -> None:
        """Should register a toolset."""
        registry = ToolsetRegistry()
        toolset = DummyToolset("test")

        registry.register(toolset)

        assert "test" in registry.list_toolsets()
        assert registry.get("test") is toolset

    def test_duplicate_registration_fails(self) -> None:
        """Should not allow duplicate toolset names."""
        registry = ToolsetRegistry()
        registry.register(DummyToolset("test"))

        with pytest.raises(ValueError, match="already registered"):
            registry.register(DummyToolset("test"))

    def test_load_toolset(self, tool_registry: ToolRegistry) -> None:
        """Should load and initialize a toolset."""
        ts_registry = ToolsetRegistry()
        toolset = DummyToolset("loadtest")
        ts_registry.register(toolset)

        success = ts_registry.load_toolset(
            name="loadtest",
            tool_registry=tool_registry,
            config={"option": True},
        )

        assert success
        assert toolset.configured
        assert toolset.initialized
        assert tool_registry.get_tool("loadtest.test") is not None

    def test_load_missing_toolset(self, tool_registry: ToolRegistry) -> None:
        """Loading non-existent toolset should fail gracefully."""
        registry = ToolsetRegistry()

        success = registry.load_toolset(
            name="nonexistent",
            tool_registry=tool_registry,
        )

        assert not success

    def test_unload_toolset(self, tool_registry: ToolRegistry) -> None:
        """Should unload and shutdown a toolset."""
        ts_registry = ToolsetRegistry()
        toolset = DummyToolset("unloadtest")
        ts_registry.register(toolset)
        ts_registry.load_toolset("unloadtest", tool_registry)

        success = ts_registry.unload_toolset("unloadtest")

        assert success
        assert toolset.shutdown_called

    def test_shutdown_all(self, tool_registry: ToolRegistry) -> None:
        """Should shutdown all loaded toolsets."""
        ts_registry = ToolsetRegistry()
        toolset1 = DummyToolset("ts1")
        toolset2 = DummyToolset("ts2")

        ts_registry.register(toolset1)
        ts_registry.register(toolset2)
        ts_registry.load_toolset("ts1", tool_registry)
        ts_registry.load_toolset("ts2", tool_registry)

        ts_registry.shutdown_all()

        assert toolset1.shutdown_called
        assert toolset2.shutdown_called
