"""Plugin system for AgentSH extensibility."""

from agentsh.plugins.base import Toolset, ToolsetRegistry, get_toolset_registry
from agentsh.plugins.lazy import (
    LazyPlugin,
    LazyPluginRegistry,
    PluginState,
    get_lazy_registry,
    load_plugins_lazy,
)
from agentsh.plugins.loader import (
    discover_builtin_plugins,
    discover_directory_plugins,
    discover_entry_point_plugins,
    load_plugins,
)

__all__ = [
    # Base classes
    "Toolset",
    "ToolsetRegistry",
    "get_toolset_registry",
    # Lazy loading
    "LazyPlugin",
    "LazyPluginRegistry",
    "PluginState",
    "get_lazy_registry",
    "load_plugins_lazy",
    # Loader
    "discover_builtin_plugins",
    "discover_directory_plugins",
    "discover_entry_point_plugins",
    "load_plugins",
]
