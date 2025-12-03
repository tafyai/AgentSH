"""Configuration loading with hierarchy support."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from agentsh.config.schemas import AgentSHConfig


def get_default_config_path() -> Path:
    """Get the default user configuration path."""
    return Path.home() / ".agentsh" / "config.yaml"


def get_config_paths() -> list[Path]:
    """Get ordered list of configuration paths to check."""
    paths = []

    # System-wide config
    system_config = Path("/etc/agentsh/config.yaml")
    if system_config.exists():
        paths.append(system_config)

    # User config
    user_config = get_default_config_path()
    if user_config.exists():
        paths.append(user_config)

    # Project-level config
    project_config = Path.cwd() / ".agentsh.yaml"
    if project_config.exists():
        paths.append(project_config)

    return paths


def load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    with open(path, "r") as f:
        content = yaml.safe_load(f) or {}
    return content


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get_env_overrides() -> dict[str, Any]:
    """Get configuration overrides from environment variables.

    Environment variables are prefixed with AGENTSH_ and use double underscores
    for nested keys. For example:
    - AGENTSH_LOG_LEVEL=DEBUG -> {"log_level": "DEBUG"}
    - AGENTSH_LLM__PROVIDER=openai -> {"llm": {"provider": "openai"}}
    """
    overrides: dict[str, Any] = {}
    prefix = "AGENTSH_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Remove prefix and convert to lowercase
        config_key = key[len(prefix):].lower()

        # Handle nested keys (double underscore)
        parts = config_key.split("__")

        # Build nested dictionary
        current = overrides
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value (try to parse as appropriate type)
        final_key = parts[-1]
        current[final_key] = _parse_env_value(value)

    return overrides


def _parse_env_value(value: str) -> Any:
    """Parse an environment variable value to appropriate type."""
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    # String
    return value


def load_config(
    config_path: Optional[Path] = None,
    include_env: bool = True,
) -> AgentSHConfig:
    """Load configuration from all sources with proper hierarchy.

    Loading order (later overrides earlier):
    1. Default values (from schema)
    2. System config (/etc/agentsh/config.yaml)
    3. User config (~/.agentsh/config.yaml)
    4. Project config (.agentsh.yaml in cwd)
    5. Explicit config file (--config argument)
    6. Environment variables (AGENTSH_*)

    Args:
        config_path: Optional explicit configuration file path
        include_env: Whether to include environment variable overrides

    Returns:
        Validated AgentSHConfig instance
    """
    # Start with empty config (defaults come from schema)
    merged_config: dict[str, Any] = {}

    # Load from standard paths
    for path in get_config_paths():
        try:
            file_config = load_yaml_config(path)
            merged_config = deep_merge(merged_config, file_config)
        except Exception:
            # Skip files that can't be read
            pass

    # Load explicit config file if provided
    if config_path:
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        explicit_config = load_yaml_config(config_path)
        merged_config = deep_merge(merged_config, explicit_config)

    # Apply environment variable overrides
    if include_env:
        env_overrides = get_env_overrides()
        merged_config = deep_merge(merged_config, env_overrides)

    # Create and validate configuration
    return AgentSHConfig(**merged_config)


def create_default_config(path: Path) -> None:
    """Create a default configuration file.

    Args:
        path: Path where to create the config file
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Generate default config
    default_config = AgentSHConfig()

    # Convert to dict and then to YAML
    config_dict = default_config.model_dump(exclude_none=True)

    # Add helpful comments
    yaml_content = """# AgentSH Configuration
# See documentation for all options: https://github.com/agentsh/agentsh/docs

"""
    yaml_content += yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

    with open(path, "w") as f:
        f.write(yaml_content)
