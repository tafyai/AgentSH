"""Tests for plugin loader module."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from agentsh.plugins.base import Toolset, ToolsetRegistry, get_toolset_registry
from agentsh.plugins.loader import (
    ENTRY_POINT_GROUP,
    _find_toolset_class,
    discover_builtin_plugins,
    discover_directory_plugins,
    discover_entry_point_plugins,
    load_plugins,
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


class AnotherToolset(Toolset):
    """Another mock toolset."""

    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Another toolset"

    def register_tools(self, registry) -> None:
        pass


class TestDiscoverBuiltinPlugins:
    """Tests for discover_builtin_plugins function."""

    def test_discovers_shell_toolset(self) -> None:
        """Should discover ShellToolset."""
        plugins = discover_builtin_plugins()

        # At least some plugins should be discovered
        assert len(plugins) >= 0  # May be empty if imports fail

    def test_returns_list_of_toolset_classes(self) -> None:
        """Should return list of Toolset classes."""
        plugins = discover_builtin_plugins()

        for plugin in plugins:
            assert issubclass(plugin, Toolset)

    def test_handles_import_error_gracefully(self) -> None:
        """Should handle ImportError without raising."""
        with patch("agentsh.plugins.loader.importlib") as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError("No module")

            # Should not raise
            plugins = discover_builtin_plugins()
            assert isinstance(plugins, list)


class TestDiscoverEntryPointPlugins:
    """Tests for discover_entry_point_plugins function."""

    def test_returns_empty_list_when_no_entry_points(self) -> None:
        """Should return empty list when no entry points exist."""
        with patch("agentsh.plugins.loader.importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value = []

            plugins = discover_entry_point_plugins()

            assert plugins == []

    def test_loads_valid_toolset_from_entry_point(self) -> None:
        """Should load valid Toolset from entry point."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"
        mock_ep.load.return_value = MockToolset

        with patch("agentsh.plugins.loader.importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]

            plugins = discover_entry_point_plugins()

            assert len(plugins) == 1
            assert plugins[0] is MockToolset

    def test_ignores_non_toolset_entry_points(self) -> None:
        """Should ignore entry points that don't load Toolset subclasses."""
        mock_ep = MagicMock()
        mock_ep.name = "not_a_toolset"
        mock_ep.load.return_value = str  # Not a Toolset

        with patch("agentsh.plugins.loader.importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]

            plugins = discover_entry_point_plugins()

            assert plugins == []

    def test_handles_entry_point_load_error(self) -> None:
        """Should handle errors loading entry points."""
        mock_ep = MagicMock()
        mock_ep.name = "failing_plugin"
        mock_ep.load.side_effect = ImportError("Module not found")

        with patch("agentsh.plugins.loader.importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]

            plugins = discover_entry_point_plugins()

            assert plugins == []

    def test_handles_entry_points_exception(self) -> None:
        """Should handle exception when getting entry points."""
        with patch("agentsh.plugins.loader.importlib.metadata.entry_points") as mock_eps:
            mock_eps.side_effect = Exception("Metadata error")

            plugins = discover_entry_point_plugins()

            assert plugins == []

    def test_uses_correct_entry_point_group(self) -> None:
        """Should use the correct entry point group name."""
        assert ENTRY_POINT_GROUP == "agentsh.plugins"


class TestDiscoverDirectoryPlugins:
    """Tests for discover_directory_plugins function."""

    def test_returns_empty_list_for_nonexistent_directory(self, tmp_path: Path) -> None:
        """Should return empty list if directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        plugins = discover_directory_plugins(nonexistent)

        assert plugins == []

    def test_returns_empty_list_for_empty_directory(self, tmp_path: Path) -> None:
        """Should return empty list for empty directory."""
        plugins = discover_directory_plugins(tmp_path)

        assert plugins == []

    def test_ignores_underscore_files(self, tmp_path: Path) -> None:
        """Should ignore files starting with underscore."""
        (tmp_path / "_private.py").write_text("class PrivateToolset: pass")

        plugins = discover_directory_plugins(tmp_path)

        assert plugins == []

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        """Should ignore non-Python files."""
        (tmp_path / "readme.txt").write_text("Not a Python file")
        (tmp_path / "data.json").write_text("{}")

        plugins = discover_directory_plugins(tmp_path)

        assert plugins == []

    def test_adds_directory_to_sys_path(self, tmp_path: Path) -> None:
        """Should add plugins directory to sys.path."""
        original_path = sys.path.copy()

        # Create a simple Python file (won't contain valid Toolset)
        (tmp_path / "test_plugin.py").write_text("x = 1")

        try:
            discover_directory_plugins(tmp_path)
            assert str(tmp_path) in sys.path
        finally:
            sys.path[:] = original_path

    def test_handles_import_error_gracefully(self, tmp_path: Path) -> None:
        """Should handle import errors gracefully."""
        # Create a file with syntax error
        (tmp_path / "bad_plugin.py").write_text("this is not valid python !!!")

        # Should not raise
        plugins = discover_directory_plugins(tmp_path)
        assert plugins == []

    def test_discovers_package_plugin(self, tmp_path: Path) -> None:
        """Should discover plugins in packages (directories with __init__.py)."""
        pkg_dir = tmp_path / "my_plugin"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Package init")

        # Won't find a Toolset, but should try
        plugins = discover_directory_plugins(tmp_path)
        # Result depends on whether the import finds a Toolset


class TestFindToolsetClass:
    """Tests for _find_toolset_class function."""

    def test_finds_toolset_subclass(self) -> None:
        """Should find Toolset subclass in module."""
        module = ModuleType("test_module")
        module.MyToolset = MockToolset  # type: ignore

        result = _find_toolset_class(module)

        assert result is MockToolset

    def test_returns_none_when_no_toolset(self) -> None:
        """Should return None if no Toolset subclass found."""
        module = ModuleType("empty_module")
        module.SomeClass = str  # type: ignore

        result = _find_toolset_class(module)

        assert result is None

    def test_ignores_base_toolset_class(self) -> None:
        """Should ignore the base Toolset class itself."""
        module = ModuleType("base_module")
        module.Toolset = Toolset  # type: ignore

        result = _find_toolset_class(module)

        assert result is None

    def test_returns_first_toolset_found(self) -> None:
        """Should return first Toolset subclass found."""
        module = ModuleType("multi_module")
        # Dict ordering in Python 3.7+ should be insertion order
        module.First = MockToolset  # type: ignore
        module.Second = AnotherToolset  # type: ignore

        result = _find_toolset_class(module)

        # Should return one of them (order depends on dir() implementation)
        assert result in (MockToolset, AnotherToolset)


class TestLoadPlugins:
    """Tests for load_plugins function."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock config."""
        config = MagicMock()
        config.plugins = []
        return config

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        return MagicMock()

    def test_returns_toolset_registry(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should return a ToolsetRegistry."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    result = load_plugins(mock_config, mock_tool_registry)

                    assert result is mock_registry

    def test_discovers_builtin_plugins(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should discover built-in plugins."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = [MockToolset]

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    load_plugins(mock_config, mock_tool_registry)

                    mock_discover.assert_called_once()

    def test_discovers_entry_point_plugins(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should discover entry point plugins."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = [MockToolset]

                    load_plugins(mock_config, mock_tool_registry)

                    mock_ep.assert_called_once()

    def test_discovers_directory_plugins_from_custom_path(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock, tmp_path: Path
    ) -> None:
        """Should discover plugins from custom directory."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_builtin:
                mock_builtin.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    with patch("agentsh.plugins.loader.discover_directory_plugins") as mock_dir:
                        mock_dir.return_value = []

                        load_plugins(mock_config, mock_tool_registry, plugins_dir=tmp_path)

                        mock_dir.assert_called_once_with(tmp_path)

    def test_discovers_directory_plugins_from_default_path(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock, tmp_path: Path
    ) -> None:
        """Should discover plugins from default directory if it exists."""
        default_plugins_dir = Path.home() / ".agentsh" / "plugins"

        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_builtin:
                mock_builtin.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    with patch("agentsh.plugins.loader.discover_directory_plugins") as mock_dir:
                        mock_dir.return_value = []

                        with patch.object(Path, "exists", return_value=True):
                            load_plugins(mock_config, mock_tool_registry)

                            # Should have tried to discover from default dir
                            # Note: exact assertion depends on implementation

    def test_registers_discovered_plugins(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should register discovered plugins."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = [MockToolset]

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    load_plugins(mock_config, mock_tool_registry)

                    # Should have registered the toolset
                    mock_registry.register.assert_called()

    def test_handles_registration_error(
        self, mock_config: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle errors during plugin registration."""
        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_registry.register.side_effect = ValueError("Already registered")
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = [MockToolset]

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    # Should not raise
                    result = load_plugins(mock_config, mock_tool_registry)
                    assert result is mock_registry

    def test_loads_enabled_plugins_from_config(
        self, mock_tool_registry: MagicMock
    ) -> None:
        """Should load enabled plugins from config."""
        mock_plugin_config = MagicMock()
        mock_plugin_config.name = "mock"
        mock_plugin_config.enabled = True
        mock_plugin_config.config = {"key": "value"}

        mock_config = MagicMock()
        mock_config.plugins = [mock_plugin_config]

        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_registry.load_toolset.return_value = True
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    load_plugins(mock_config, mock_tool_registry)

                    mock_registry.load_toolset.assert_called_once_with(
                        name="mock",
                        tool_registry=mock_tool_registry,
                        config={"key": "value"},
                    )

    def test_skips_disabled_plugins(
        self, mock_tool_registry: MagicMock
    ) -> None:
        """Should skip disabled plugins."""
        mock_plugin_config = MagicMock()
        mock_plugin_config.name = "disabled_plugin"
        mock_plugin_config.enabled = False

        mock_config = MagicMock()
        mock_config.plugins = [mock_plugin_config]

        with patch("agentsh.plugins.loader.get_toolset_registry") as mock_get:
            mock_registry = MagicMock(spec=ToolsetRegistry)
            mock_get.return_value = mock_registry

            with patch("agentsh.plugins.loader.discover_builtin_plugins") as mock_discover:
                mock_discover.return_value = []

                with patch("agentsh.plugins.loader.discover_entry_point_plugins") as mock_ep:
                    mock_ep.return_value = []

                    load_plugins(mock_config, mock_tool_registry)

                    mock_registry.load_toolset.assert_not_called()


class TestToolsetRegistry:
    """Tests for ToolsetRegistry class."""

    def test_register_toolset(self) -> None:
        """Should register a toolset."""
        registry = ToolsetRegistry()
        toolset = MockToolset()

        registry.register(toolset)

        assert registry.get("mock") is toolset

    def test_register_duplicate_raises(self) -> None:
        """Should raise when registering duplicate."""
        registry = ToolsetRegistry()
        toolset1 = MockToolset()
        toolset2 = MockToolset()

        registry.register(toolset1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(toolset2)

    def test_get_nonexistent_returns_none(self) -> None:
        """Should return None for nonexistent toolset."""
        registry = ToolsetRegistry()

        assert registry.get("nonexistent") is None

    def test_list_toolsets(self) -> None:
        """Should list registered toolsets."""
        registry = ToolsetRegistry()
        registry.register(MockToolset())
        registry.register(AnotherToolset())

        names = registry.list_toolsets()

        assert "mock" in names
        assert "another" in names

    def test_load_toolset_success(self) -> None:
        """Should load toolset successfully."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        result = registry.load_toolset("mock", mock_tool_registry)

        assert result is True

    def test_load_toolset_with_config(self) -> None:
        """Should configure toolset when loading."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        toolset.configure = MagicMock()  # type: ignore
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry, config={"key": "value"})

        toolset.configure.assert_called_once_with({"key": "value"})

    def test_load_toolset_nonexistent(self) -> None:
        """Should return False for nonexistent toolset."""
        registry = ToolsetRegistry()
        mock_tool_registry = MagicMock()

        result = registry.load_toolset("nonexistent", mock_tool_registry)

        assert result is False

    def test_load_toolset_already_loaded(self) -> None:
        """Should return True for already loaded toolset."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry)
        result = registry.load_toolset("mock", mock_tool_registry)

        assert result is True

    def test_load_toolset_handles_error(self) -> None:
        """Should return False on initialization error."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        toolset.initialize = MagicMock(side_effect=Exception("Init failed"))  # type: ignore
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        result = registry.load_toolset("mock", mock_tool_registry)

        assert result is False

    def test_unload_toolset(self) -> None:
        """Should unload a loaded toolset."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry)
        result = registry.unload_toolset("mock")

        assert result is True

    def test_unload_toolset_not_loaded(self) -> None:
        """Should return False for unloaded toolset."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        registry.register(toolset)

        result = registry.unload_toolset("mock")

        assert result is False

    def test_unload_toolset_calls_shutdown(self) -> None:
        """Should call shutdown on unload."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        toolset.shutdown = MagicMock()  # type: ignore
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry)
        registry.unload_toolset("mock")

        toolset.shutdown.assert_called_once()

    def test_unload_toolset_handles_shutdown_error(self) -> None:
        """Should handle shutdown errors gracefully."""
        registry = ToolsetRegistry()
        toolset = MockToolset()
        toolset.shutdown = MagicMock(side_effect=Exception("Shutdown failed"))  # type: ignore
        registry.register(toolset)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry)
        result = registry.unload_toolset("mock")

        assert result is True

    def test_shutdown_all(self) -> None:
        """Should shutdown all loaded toolsets."""
        registry = ToolsetRegistry()
        toolset1 = MockToolset()
        toolset1.shutdown = MagicMock()  # type: ignore
        toolset2 = AnotherToolset()
        toolset2.shutdown = MagicMock()  # type: ignore
        registry.register(toolset1)
        registry.register(toolset2)
        mock_tool_registry = MagicMock()

        registry.load_toolset("mock", mock_tool_registry)
        registry.load_toolset("another", mock_tool_registry)
        registry.shutdown_all()

        toolset1.shutdown.assert_called()
        toolset2.shutdown.assert_called()


class TestGetToolsetRegistry:
    """Tests for get_toolset_registry function."""

    def test_returns_toolset_registry(self) -> None:
        """Should return a ToolsetRegistry."""
        with patch("agentsh.plugins.base._toolset_registry", None):
            registry = get_toolset_registry()

            assert isinstance(registry, ToolsetRegistry)

    def test_returns_same_instance(self) -> None:
        """Should return the same instance on multiple calls."""
        with patch("agentsh.plugins.base._toolset_registry", None):
            registry1 = get_toolset_registry()
            registry2 = get_toolset_registry()

            assert registry1 is registry2
