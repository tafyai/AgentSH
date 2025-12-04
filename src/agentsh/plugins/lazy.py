"""Lazy loading support for plugins.

Provides deferred loading of plugins to improve startup time.
Plugins are only imported when first accessed.
"""

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from agentsh.plugins.base import Toolset, ToolsetRegistry
from agentsh.telemetry.logger import get_logger

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


class PluginState(str, Enum):
    """Plugin loading states."""

    UNLOADED = "unloaded"  # Not yet imported
    LOADING = "loading"  # Currently importing
    LOADED = "loaded"  # Imported and instantiated
    REGISTERED = "registered"  # Tools registered with registry
    FAILED = "failed"  # Failed to load


@dataclass
class LazyPlugin:
    """Lazy-loaded plugin descriptor.

    Holds the information needed to load a plugin on demand.

    Attributes:
        name: Plugin name
        module_path: Full module path (e.g., "agentsh.plugins.builtin.shell")
        class_name: Class name within the module (e.g., "ShellToolset")
        state: Current loading state
        instance: Loaded toolset instance (when loaded)
        error: Error message if loading failed
    """

    name: str
    module_path: str
    class_name: str
    state: PluginState = PluginState.UNLOADED
    instance: Optional[Toolset] = None
    error: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)

    def load(self) -> Optional[Toolset]:
        """Load the plugin.

        Returns:
            Toolset instance or None if loading fails
        """
        if self.state == PluginState.LOADED:
            return self.instance

        if self.state == PluginState.FAILED:
            return None

        if self.state == PluginState.LOADING:
            # Prevent circular loading
            logger.warning("Plugin is already loading", plugin=self.name)
            return None

        try:
            self.state = PluginState.LOADING
            logger.debug("Lazy loading plugin", plugin=self.name, module=self.module_path)

            # Import the module
            module = importlib.import_module(self.module_path)

            # Get the class
            plugin_class = getattr(module, self.class_name)

            if not isinstance(plugin_class, type) or not issubclass(plugin_class, Toolset):
                self.state = PluginState.FAILED
                self.error = f"{self.class_name} is not a Toolset subclass"
                logger.error("Invalid plugin class", plugin=self.name, error=self.error)
                return None

            # Create instance
            self.instance = plugin_class()
            self.state = PluginState.LOADED
            logger.info("Lazy loaded plugin", plugin=self.name)

            return self.instance

        except ImportError as e:
            self.state = PluginState.FAILED
            self.error = f"Import error: {e}"
            logger.warning("Failed to import plugin", plugin=self.name, error=str(e))
            return None

        except Exception as e:
            self.state = PluginState.FAILED
            self.error = str(e)
            logger.error("Failed to load plugin", plugin=self.name, error=str(e))
            return None

    @property
    def is_loaded(self) -> bool:
        """Check if plugin is loaded."""
        return self.state in (PluginState.LOADED, PluginState.REGISTERED)

    @property
    def is_available(self) -> bool:
        """Check if plugin can be loaded."""
        return self.state not in (PluginState.FAILED,)


class LazyPluginRegistry:
    """Registry of lazy-loaded plugins.

    Plugins are registered by their import path and only loaded when first accessed.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, LazyPlugin] = {}
        self._load_hooks: list[Callable[[LazyPlugin], None]] = []

    def register(
        self,
        name: str,
        module_path: str,
        class_name: str,
        dependencies: Optional[list[str]] = None,
    ) -> None:
        """Register a lazy plugin.

        Args:
            name: Plugin name
            module_path: Full module path
            class_name: Class name in module
            dependencies: Optional list of plugin names this depends on
        """
        if name in self._plugins:
            logger.warning("Plugin already registered", plugin=name)
            return

        self._plugins[name] = LazyPlugin(
            name=name,
            module_path=module_path,
            class_name=class_name,
            dependencies=dependencies or [],
        )
        logger.debug("Registered lazy plugin", plugin=name, module=module_path)

    def get(self, name: str) -> Optional[Toolset]:
        """Get a plugin by name, loading it if necessary.

        Args:
            name: Plugin name

        Returns:
            Toolset instance or None
        """
        plugin = self._plugins.get(name)
        if not plugin:
            return None

        # Load dependencies first
        for dep_name in plugin.dependencies:
            dep = self.get(dep_name)
            if not dep:
                logger.warning(
                    "Plugin dependency not available",
                    plugin=name,
                    dependency=dep_name,
                )

        # Load the plugin
        instance = plugin.load()

        # Call load hooks
        if instance:
            for hook in self._load_hooks:
                try:
                    hook(plugin)
                except Exception as e:
                    logger.warning("Load hook failed", plugin=name, error=str(e))

        return instance

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            name: Plugin name

        Returns:
            True if loaded
        """
        plugin = self._plugins.get(name)
        return plugin.is_loaded if plugin else False

    def list_plugins(self) -> list[str]:
        """Get list of registered plugin names."""
        return list(self._plugins.keys())

    def list_loaded(self) -> list[str]:
        """Get list of loaded plugin names."""
        return [name for name, plugin in self._plugins.items() if plugin.is_loaded]

    def list_available(self) -> list[str]:
        """Get list of available (loadable) plugin names."""
        return [name for name, plugin in self._plugins.items() if plugin.is_available]

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all plugins.

        Returns:
            Dict mapping plugin names to their status
        """
        return {
            name: {
                "state": plugin.state.value,
                "module": plugin.module_path,
                "class": plugin.class_name,
                "error": plugin.error,
            }
            for name, plugin in self._plugins.items()
        }

    def add_load_hook(self, hook: Callable[[LazyPlugin], None]) -> None:
        """Add a hook called when plugins are loaded.

        Args:
            hook: Callable taking LazyPlugin as argument
        """
        self._load_hooks.append(hook)

    def preload(self, names: Optional[list[str]] = None) -> int:
        """Preload specified plugins or all registered plugins.

        Args:
            names: Optional list of plugin names to preload

        Returns:
            Number of successfully loaded plugins
        """
        target_names = names if names else list(self._plugins.keys())
        loaded = 0

        for name in target_names:
            if self.get(name):
                loaded += 1

        return loaded

    def unload(self, name: str) -> bool:
        """Unload a plugin and reset its state.

        Note: This doesn't actually unload the module from Python,
        but resets the state so it will be re-imported on next access.

        Args:
            name: Plugin name

        Returns:
            True if unloaded
        """
        plugin = self._plugins.get(name)
        if not plugin:
            return False

        if plugin.instance:
            try:
                plugin.instance.shutdown()
            except Exception as e:
                logger.warning("Plugin shutdown failed", plugin=name, error=str(e))

        plugin.instance = None
        plugin.state = PluginState.UNLOADED
        plugin.error = None
        return True


# Builtin plugin definitions
BUILTIN_PLUGINS: list[tuple[str, str, str]] = [
    ("shell", "agentsh.plugins.builtin.shell", "ShellToolset"),
    ("filesystem", "agentsh.plugins.builtin.filesystem", "FilesystemToolset"),
    ("process", "agentsh.plugins.builtin.process", "ProcessToolset"),
    ("code", "agentsh.plugins.builtin.code", "CodeToolset"),
    ("remote", "agentsh.plugins.builtin.remote", "RemoteToolset"),
]

# Optional plugin definitions (only loaded if dependencies are available)
OPTIONAL_PLUGINS: list[tuple[str, str, str, list[str]]] = [
    # (name, module_path, class_name, required_packages)
    # Example: ("ros", "agentsh.plugins.robotics.robotics_toolset", "RoboticsToolset", ["rclpy"])
]


# Global lazy registry
_lazy_registry: Optional[LazyPluginRegistry] = None


def get_lazy_registry() -> LazyPluginRegistry:
    """Get the global lazy plugin registry.

    Returns:
        LazyPluginRegistry instance
    """
    global _lazy_registry
    if _lazy_registry is None:
        _lazy_registry = LazyPluginRegistry()

        # Register builtin plugins
        for name, module, class_name in BUILTIN_PLUGINS:
            _lazy_registry.register(name, module, class_name)

        # Register optional plugins (check dependencies first)
        for name, module, class_name, required_packages in OPTIONAL_PLUGINS:
            # Check if required packages are installed
            all_available = True
            for package in required_packages:
                try:
                    importlib.import_module(package)
                except ImportError:
                    all_available = False
                    break

            if all_available:
                _lazy_registry.register(name, module, class_name)
            else:
                logger.debug(
                    "Skipping optional plugin (missing dependencies)",
                    plugin=name,
                    required=required_packages,
                )

    return _lazy_registry


def load_plugins_lazy(
    enabled_plugins: list[str],
    tool_registry: "ToolRegistry",
    configs: Optional[dict[str, dict[str, Any]]] = None,
) -> list[str]:
    """Load plugins lazily by name.

    Args:
        enabled_plugins: List of plugin names to load
        tool_registry: Tool registry to register tools with
        configs: Optional dict of plugin configs keyed by name

    Returns:
        List of successfully loaded plugin names
    """
    configs = configs or {}
    registry = get_lazy_registry()
    toolset_registry = ToolsetRegistry()
    loaded: list[str] = []

    for name in enabled_plugins:
        toolset = registry.get(name)
        if not toolset:
            logger.warning("Plugin not found", plugin=name)
            continue

        try:
            # Configure if config provided
            if name in configs:
                toolset.configure(configs[name])

            # Initialize and register
            toolset.initialize()
            toolset.register_tools(tool_registry)

            # Update lazy plugin state
            plugin = registry._plugins.get(name)
            if plugin:
                plugin.state = PluginState.REGISTERED

            loaded.append(name)
            logger.info("Loaded plugin", plugin=name)

        except Exception as e:
            logger.error("Failed to load plugin", plugin=name, error=str(e))

    return loaded
