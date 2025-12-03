"""Plugin discovery and loading."""

import importlib
import importlib.metadata
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from agentsh.plugins.base import Toolset, ToolsetRegistry, get_toolset_registry
from agentsh.telemetry.logger import get_logger

if TYPE_CHECKING:
    from agentsh.config.schemas import AgentSHConfig
    from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


# Entry point group for discovering plugins
ENTRY_POINT_GROUP = "agentsh.plugins"


def discover_builtin_plugins() -> list[type[Toolset]]:
    """Discover built-in plugins.

    Returns:
        List of Toolset classes from built-in plugins
    """
    plugins: list[type[Toolset]] = []

    try:
        from agentsh.plugins.builtin.shell import ShellToolset

        plugins.append(ShellToolset)
    except ImportError:
        pass

    try:
        from agentsh.plugins.builtin.filesystem import FilesystemToolset

        plugins.append(FilesystemToolset)
    except ImportError:
        pass

    try:
        from agentsh.plugins.builtin.process import ProcessToolset

        plugins.append(ProcessToolset)
    except ImportError:
        pass

    try:
        from agentsh.plugins.builtin.code import CodeToolset

        plugins.append(CodeToolset)
    except ImportError:
        pass

    return plugins


def discover_entry_point_plugins() -> list[type[Toolset]]:
    """Discover plugins via entry points.

    Plugins can register themselves using:
    [project.entry-points."agentsh.plugins"]
    my_plugin = "my_package.plugin:MyToolset"

    Returns:
        List of Toolset classes from entry points
    """
    plugins: list[type[Toolset]] = []

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                plugin_class = ep.load()
                if isinstance(plugin_class, type) and issubclass(plugin_class, Toolset):
                    plugins.append(plugin_class)
                    logger.info("Discovered plugin via entry point", plugin=ep.name)
            except Exception as e:
                logger.warning(
                    "Failed to load plugin from entry point",
                    entry_point=ep.name,
                    error=str(e),
                )
    except Exception as e:
        logger.debug("No entry points found", error=str(e))

    return plugins


def discover_directory_plugins(plugins_dir: Path) -> list[type[Toolset]]:
    """Discover plugins from a directory.

    Each subdirectory or .py file in the plugins directory is checked
    for a Toolset subclass.

    Args:
        plugins_dir: Directory to scan for plugins

    Returns:
        List of Toolset classes found
    """
    plugins: list[type[Toolset]] = []

    if not plugins_dir.exists():
        return plugins

    # Add plugins directory to path
    if str(plugins_dir) not in sys.path:
        sys.path.insert(0, str(plugins_dir))

    for item in plugins_dir.iterdir():
        try:
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                # Single file plugin
                module_name = item.stem
                module = importlib.import_module(module_name)
                plugin_class = _find_toolset_class(module)
                if plugin_class:
                    plugins.append(plugin_class)
                    logger.info("Discovered plugin from file", file=str(item))

            elif item.is_dir() and (item / "__init__.py").exists():
                # Package plugin
                module_name = item.name
                module = importlib.import_module(module_name)
                plugin_class = _find_toolset_class(module)
                if plugin_class:
                    plugins.append(plugin_class)
                    logger.info("Discovered plugin from package", package=str(item))

        except Exception as e:
            logger.warning(
                "Failed to load plugin from directory",
                path=str(item),
                error=str(e),
            )

    return plugins


def _find_toolset_class(module: object) -> Optional[type[Toolset]]:
    """Find a Toolset subclass in a module.

    Args:
        module: Python module to search

    Returns:
        First Toolset subclass found, or None
    """
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, Toolset)
            and obj is not Toolset
        ):
            return obj
    return None


def load_plugins(
    config: "AgentSHConfig",
    tool_registry: "ToolRegistry",
    plugins_dir: Optional[Path] = None,
) -> ToolsetRegistry:
    """Load all plugins based on configuration.

    Args:
        config: AgentSH configuration
        tool_registry: Tool registry to register tools with
        plugins_dir: Optional custom plugins directory

    Returns:
        ToolsetRegistry with loaded plugins
    """
    registry = get_toolset_registry()

    # Discover all available plugins
    all_plugins: list[type[Toolset]] = []
    all_plugins.extend(discover_builtin_plugins())
    all_plugins.extend(discover_entry_point_plugins())

    if plugins_dir:
        all_plugins.extend(discover_directory_plugins(plugins_dir))
    else:
        # Default plugins directory
        default_dir = Path.home() / ".agentsh" / "plugins"
        if default_dir.exists():
            all_plugins.extend(discover_directory_plugins(default_dir))

    # Register discovered plugins
    for plugin_class in all_plugins:
        try:
            toolset = plugin_class()
            registry.register(toolset)
            logger.debug("Registered toolset", name=toolset.name)
        except Exception as e:
            logger.warning(
                "Failed to register toolset",
                toolset=plugin_class.__name__,
                error=str(e),
            )

    # Load enabled plugins
    for plugin_config in config.plugins:
        if not plugin_config.enabled:
            continue

        success = registry.load_toolset(
            name=plugin_config.name,
            tool_registry=tool_registry,
            config=plugin_config.config,
        )

        if success:
            logger.info("Loaded plugin", name=plugin_config.name)
        else:
            logger.warning("Plugin not found or failed to load", name=plugin_config.name)

    return registry
