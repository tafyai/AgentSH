"""Base classes for the plugin system."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry


class Toolset(ABC):
    """Abstract base class for plugins that provide tools.

    A Toolset groups related tools together. For example:
    - ShellToolset provides shell.run, shell.explain
    - FilesystemToolset provides fs.read, fs.write, fs.list, etc.

    Subclasses must implement:
    - name: Unique identifier for the toolset
    - description: Human-readable description
    - register_tools: Method to register tools with the registry
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this toolset (e.g., 'shell', 'filesystem')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this toolset."""
        pass

    @abstractmethod
    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register all tools provided by this toolset.

        Args:
            registry: The tool registry to register tools with
        """
        pass

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the toolset with plugin-specific settings.

        Override this method to handle configuration. The config dict
        comes from the plugins section of the AgentSH config.

        Args:
            config: Plugin-specific configuration dictionary
        """
        pass

    def initialize(self) -> None:
        """Initialize the toolset.

        Override this method to perform any setup required before
        tools can be used. Called after configure().
        """
        pass

    def shutdown(self) -> None:
        """Clean up resources when the toolset is unloaded.

        Override this method to clean up any resources (connections,
        file handles, etc.) when AgentSH is shutting down.
        """
        pass


class ToolsetRegistry:
    """Registry of available toolsets."""

    def __init__(self) -> None:
        self._toolsets: dict[str, Toolset] = {}
        self._loaded: set[str] = set()

    def register(self, toolset: Toolset) -> None:
        """Register a toolset.

        Args:
            toolset: Toolset instance to register

        Raises:
            ValueError: If a toolset with the same name is already registered
        """
        if toolset.name in self._toolsets:
            raise ValueError(f"Toolset '{toolset.name}' is already registered")
        self._toolsets[toolset.name] = toolset

    def get(self, name: str) -> Optional[Toolset]:
        """Get a toolset by name.

        Args:
            name: Toolset name

        Returns:
            Toolset instance or None if not found
        """
        return self._toolsets.get(name)

    def list_toolsets(self) -> list[str]:
        """Get list of registered toolset names."""
        return list(self._toolsets.keys())

    def load_toolset(
        self,
        name: str,
        tool_registry: "ToolRegistry",
        config: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Load and initialize a toolset.

        Args:
            name: Toolset name to load
            tool_registry: Tool registry to register tools with
            config: Optional plugin configuration

        Returns:
            True if loaded successfully, False otherwise
        """
        if name in self._loaded:
            return True

        toolset = self._toolsets.get(name)
        if not toolset:
            return False

        try:
            if config:
                toolset.configure(config)
            toolset.initialize()
            toolset.register_tools(tool_registry)
            self._loaded.add(name)
            return True
        except Exception:
            return False

    def unload_toolset(self, name: str) -> bool:
        """Unload a toolset and clean up resources.

        Args:
            name: Toolset name to unload

        Returns:
            True if unloaded successfully
        """
        if name not in self._loaded:
            return False

        toolset = self._toolsets.get(name)
        if toolset:
            try:
                toolset.shutdown()
            except Exception:
                pass

        self._loaded.discard(name)
        return True

    def shutdown_all(self) -> None:
        """Shutdown all loaded toolsets."""
        for name in list(self._loaded):
            self.unload_toolset(name)


# Global toolset registry
_toolset_registry: Optional[ToolsetRegistry] = None


def get_toolset_registry() -> ToolsetRegistry:
    """Get the global toolset registry."""
    global _toolset_registry
    if _toolset_registry is None:
        _toolset_registry = ToolsetRegistry()
    return _toolset_registry
