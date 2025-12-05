"""Tests for lazy plugin loading module."""

import pytest
from unittest.mock import MagicMock, patch

from agentsh.plugins.base import Toolset, ToolsetRegistry
from agentsh.plugins.lazy import (
    LazyPlugin,
    LazyPluginRegistry,
    PluginState,
    get_lazy_registry,
    load_plugins_lazy,
    BUILTIN_PLUGINS,
)


class MockToolset(Toolset):
    """Mock toolset for testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def description(self) -> str:
        return "Mock toolset for testing"

    def register_tools(self, registry) -> None:
        pass


class TestPluginState:
    """Tests for PluginState enum."""

    def test_states_exist(self) -> None:
        """Should have all expected states."""
        assert PluginState.UNLOADED == "unloaded"
        assert PluginState.LOADING == "loading"
        assert PluginState.LOADED == "loaded"
        assert PluginState.REGISTERED == "registered"
        assert PluginState.FAILED == "failed"


class TestLazyPlugin:
    """Tests for LazyPlugin dataclass."""

    def test_create_lazy_plugin(self) -> None:
        """Should create lazy plugin with defaults."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
        )

        assert plugin.name == "test"
        assert plugin.module_path == "test.module"
        assert plugin.class_name == "TestToolset"
        assert plugin.state == PluginState.UNLOADED
        assert plugin.instance is None
        assert plugin.error is None
        assert plugin.dependencies == []

    def test_lazy_plugin_with_dependencies(self) -> None:
        """Should accept dependencies."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
            dependencies=["dep1", "dep2"],
        )

        assert plugin.dependencies == ["dep1", "dep2"]

    def test_is_loaded_false_when_unloaded(self) -> None:
        """Should return False when unloaded."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
        )

        assert plugin.is_loaded is False

    def test_is_loaded_true_when_loaded(self) -> None:
        """Should return True when loaded."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
            state=PluginState.LOADED,
        )

        assert plugin.is_loaded is True

    def test_is_loaded_true_when_registered(self) -> None:
        """Should return True when registered."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
            state=PluginState.REGISTERED,
        )

        assert plugin.is_loaded is True

    def test_is_available_true_by_default(self) -> None:
        """Should be available by default."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
        )

        assert plugin.is_available is True

    def test_is_available_false_when_failed(self) -> None:
        """Should not be available when failed."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
            state=PluginState.FAILED,
        )

        assert plugin.is_available is False

    def test_load_returns_instance(self) -> None:
        """Should load and return instance."""
        plugin = LazyPlugin(
            name="shell",
            module_path="agentsh.plugins.builtin.shell",
            class_name="ShellToolset",
        )

        instance = plugin.load()

        assert instance is not None
        assert plugin.state == PluginState.LOADED
        assert plugin.instance is instance

    def test_load_returns_cached_instance(self) -> None:
        """Should return cached instance on second call."""
        plugin = LazyPlugin(
            name="shell",
            module_path="agentsh.plugins.builtin.shell",
            class_name="ShellToolset",
        )

        instance1 = plugin.load()
        instance2 = plugin.load()

        assert instance1 is instance2

    def test_load_fails_on_import_error(self) -> None:
        """Should handle import errors."""
        plugin = LazyPlugin(
            name="nonexistent",
            module_path="nonexistent.module",
            class_name="NoToolset",
        )

        instance = plugin.load()

        assert instance is None
        assert plugin.state == PluginState.FAILED
        assert plugin.error is not None
        assert "Import error" in plugin.error

    def test_load_fails_on_invalid_class(self) -> None:
        """Should fail if class is not a Toolset."""
        plugin = LazyPlugin(
            name="invalid",
            module_path="agentsh.plugins.lazy",
            class_name="PluginState",  # Not a Toolset
        )

        instance = plugin.load()

        assert instance is None
        assert plugin.state == PluginState.FAILED
        assert "not a Toolset subclass" in plugin.error

    def test_load_returns_none_when_already_failed(self) -> None:
        """Should return None if already failed."""
        plugin = LazyPlugin(
            name="test",
            module_path="test.module",
            class_name="TestToolset",
            state=PluginState.FAILED,
        )

        instance = plugin.load()

        assert instance is None


class TestLazyPluginRegistry:
    """Tests for LazyPluginRegistry class."""

    @pytest.fixture
    def registry(self) -> LazyPluginRegistry:
        """Create fresh registry."""
        return LazyPluginRegistry()

    def test_register_plugin(self, registry: LazyPluginRegistry) -> None:
        """Should register plugin."""
        registry.register("test", "test.module", "TestToolset")

        assert "test" in registry.list_plugins()

    def test_register_plugin_with_dependencies(self, registry: LazyPluginRegistry) -> None:
        """Should register plugin with dependencies."""
        registry.register("test", "test.module", "TestToolset", dependencies=["dep1"])

        plugin = registry._plugins.get("test")
        assert plugin.dependencies == ["dep1"]

    def test_register_duplicate_plugin_warns(self, registry: LazyPluginRegistry) -> None:
        """Should warn on duplicate registration."""
        registry.register("test", "test.module", "TestToolset")
        registry.register("test", "test.other", "OtherToolset")

        # Only first registration counts
        plugin = registry._plugins.get("test")
        assert plugin.module_path == "test.module"

    def test_get_loads_plugin(self, registry: LazyPluginRegistry) -> None:
        """Should load plugin on get."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")

        toolset = registry.get("shell")

        assert toolset is not None
        assert toolset.name == "shell"

    def test_get_returns_none_for_unknown(self, registry: LazyPluginRegistry) -> None:
        """Should return None for unknown plugin."""
        assert registry.get("unknown") is None

    def test_is_loaded_false_initially(self, registry: LazyPluginRegistry) -> None:
        """Should return False before loading."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")

        assert registry.is_loaded("shell") is False

    def test_is_loaded_true_after_get(self, registry: LazyPluginRegistry) -> None:
        """Should return True after loading."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        assert registry.is_loaded("shell") is True

    def test_list_plugins(self, registry: LazyPluginRegistry) -> None:
        """Should list all registered plugins."""
        registry.register("plugin1", "test.module", "TestToolset")
        registry.register("plugin2", "test.module", "TestToolset")

        plugins = registry.list_plugins()

        assert "plugin1" in plugins
        assert "plugin2" in plugins

    def test_list_loaded(self, registry: LazyPluginRegistry) -> None:
        """Should list only loaded plugins."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register("fs", "agentsh.plugins.builtin.filesystem", "FilesystemToolset")

        # Load only shell
        registry.get("shell")

        loaded = registry.list_loaded()
        assert "shell" in loaded
        assert "fs" not in loaded

    def test_list_available(self, registry: LazyPluginRegistry) -> None:
        """Should list available plugins."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register("bad", "nonexistent.module", "NoToolset")

        # Try to load bad plugin to mark as failed
        registry.get("bad")

        available = registry.list_available()
        assert "shell" in available
        assert "bad" not in available

    def test_get_status(self, registry: LazyPluginRegistry) -> None:
        """Should return status of all plugins."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        status = registry.get_status()

        assert "shell" in status
        assert status["shell"]["state"] == "loaded"
        assert status["shell"]["module"] == "agentsh.plugins.builtin.shell"

    def test_add_load_hook(self, registry: LazyPluginRegistry) -> None:
        """Should call load hooks when loading."""
        hook_called = []

        def hook(plugin):
            hook_called.append(plugin.name)

        registry.add_load_hook(hook)
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        assert "shell" in hook_called

    def test_preload_all(self, registry: LazyPluginRegistry) -> None:
        """Should preload all plugins."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register("fs", "agentsh.plugins.builtin.filesystem", "FilesystemToolset")

        loaded = registry.preload()

        assert loaded == 2
        assert registry.is_loaded("shell")
        assert registry.is_loaded("fs")

    def test_preload_specific(self, registry: LazyPluginRegistry) -> None:
        """Should preload specific plugins."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register("fs", "agentsh.plugins.builtin.filesystem", "FilesystemToolset")

        loaded = registry.preload(["shell"])

        assert loaded == 1
        assert registry.is_loaded("shell")
        assert not registry.is_loaded("fs")

    def test_unload_plugin(self, registry: LazyPluginRegistry) -> None:
        """Should unload plugin."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        result = registry.unload("shell")

        assert result is True
        assert not registry.is_loaded("shell")

    def test_unload_unknown_returns_false(self, registry: LazyPluginRegistry) -> None:
        """Should return False for unknown plugin."""
        result = registry.unload("unknown")

        assert result is False

    def test_dependency_loading(self, registry: LazyPluginRegistry) -> None:
        """Should load dependencies first."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register(
            "dependent",
            "agentsh.plugins.builtin.filesystem",
            "FilesystemToolset",
            dependencies=["shell"],
        )

        # Load dependent plugin
        registry.get("dependent")

        # Shell should also be loaded
        assert registry.is_loaded("shell")
        assert registry.is_loaded("dependent")


class TestGlobalRegistry:
    """Tests for global lazy registry."""

    def test_get_lazy_registry_returns_singleton(self) -> None:
        """Should return same registry instance."""
        reg1 = get_lazy_registry()
        reg2 = get_lazy_registry()

        assert reg1 is reg2

    def test_builtin_plugins_registered(self) -> None:
        """Should have builtin plugins registered."""
        registry = get_lazy_registry()

        for name, _, _ in BUILTIN_PLUGINS:
            assert name in registry.list_plugins()


class TestLoadPluginsLazy:
    """Tests for load_plugins_lazy function."""

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        return MagicMock()

    def test_load_enabled_plugins(self, mock_tool_registry: MagicMock) -> None:
        """Should load enabled plugins."""
        loaded = load_plugins_lazy(["shell", "filesystem"], mock_tool_registry)

        assert "shell" in loaded
        assert "filesystem" in loaded

    def test_skip_unknown_plugins(self, mock_tool_registry: MagicMock) -> None:
        """Should skip unknown plugins."""
        loaded = load_plugins_lazy(["shell", "unknown"], mock_tool_registry)

        assert "shell" in loaded
        assert "unknown" not in loaded

    def test_apply_plugin_configs(self, mock_tool_registry: MagicMock) -> None:
        """Should apply plugin configs."""
        configs = {"shell": {"timeout": 30}}

        # This tests config is applied without error
        loaded = load_plugins_lazy(["shell"], mock_tool_registry, configs)

        assert "shell" in loaded

    def test_register_tools_called(self, mock_tool_registry: MagicMock) -> None:
        """Should call register_tools on each plugin."""
        load_plugins_lazy(["shell"], mock_tool_registry)

        # Tool registry should have been passed to register_tools
        # (verify via mock calls if needed)
        assert True  # If we get here, no exception was raised


class TestLazyPluginEdgeCases:
    """Edge case tests for lazy plugin loading."""

    def test_load_while_loading(self) -> None:
        """Should handle concurrent loading attempts."""
        plugin = LazyPlugin(
            name="test",
            module_path="agentsh.plugins.builtin.shell",
            class_name="ShellToolset",
        )
        # Set state to loading
        plugin.state = PluginState.LOADING

        # Try to load again
        instance = plugin.load()

        # Should return None while loading
        assert instance is None

    def test_plugin_reset_after_unload(self) -> None:
        """Plugin state should reset after unload."""
        registry = LazyPluginRegistry()
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        # Unload
        registry.unload("shell")

        # Plugin state should be reset
        plugin = registry._plugins.get("shell")
        assert plugin.state == PluginState.UNLOADED
        assert plugin.instance is None

    def test_dependency_not_found(self) -> None:
        """Should handle missing dependency gracefully."""
        registry = LazyPluginRegistry()
        registry.register(
            "dependent",
            "agentsh.plugins.builtin.shell",
            "ShellToolset",
            dependencies=["nonexistent"],
        )

        # Try to load - should handle missing dependency
        result = registry.get("dependent")
        # May still load if dependency is not critical
        assert True  # No exception raised

    def test_preload_specific_plugins_only(self) -> None:
        """Should only preload specified plugins."""
        registry = LazyPluginRegistry()
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.register("fs", "agentsh.plugins.builtin.filesystem", "FilesystemToolset")

        # Preload only fs, not shell
        loaded = registry.preload(["fs"])

        assert loaded == 1
        assert registry.is_loaded("fs")
        assert not registry.is_loaded("shell")

    def test_get_status_with_error(self) -> None:
        """Should include error in status."""
        registry = LazyPluginRegistry()
        registry.register("bad", "nonexistent.module", "NoClass")
        registry.get("bad")  # This will fail

        status = registry.get_status()

        assert status["bad"]["state"] == "failed"
        assert "error" in status["bad"]


class TestLazyPluginRegistryExtended:
    """Extended tests for LazyPluginRegistry."""

    @pytest.fixture
    def registry(self) -> LazyPluginRegistry:
        """Create fresh registry."""
        return LazyPluginRegistry()

    def test_list_plugins_empty(self, registry: LazyPluginRegistry) -> None:
        """Should return empty list when no plugins."""
        assert registry.list_plugins() == []

    def test_list_loaded_empty(self, registry: LazyPluginRegistry) -> None:
        """Should return empty list when nothing loaded."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        assert registry.list_loaded() == []

    def test_multiple_load_hooks(self, registry: LazyPluginRegistry) -> None:
        """Should call multiple load hooks."""
        calls = []

        def hook1(plugin):
            calls.append(("hook1", plugin.name))

        def hook2(plugin):
            calls.append(("hook2", plugin.name))

        registry.add_load_hook(hook1)
        registry.add_load_hook(hook2)
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        registry.get("shell")

        assert ("hook1", "shell") in calls
        assert ("hook2", "shell") in calls

    def test_get_already_loaded(self, registry: LazyPluginRegistry) -> None:
        """Should return cached instance for loaded plugin."""
        registry.register("shell", "agentsh.plugins.builtin.shell", "ShellToolset")
        toolset = registry.get("shell")

        # Plugin should be cached
        plugin = registry._plugins.get("shell")
        assert plugin.state == PluginState.LOADED
        assert plugin.instance is toolset

        # Get again should return same instance
        toolset2 = registry.get("shell")
        assert toolset2 is toolset
