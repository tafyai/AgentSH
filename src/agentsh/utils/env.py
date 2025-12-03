"""Environment variable utilities."""

import os
from typing import Optional


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable value.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value or default
    """
    return os.environ.get(name, default)


def get_env_or_fail(name: str) -> str:
    """Get a required environment variable.

    Args:
        name: Environment variable name

    Returns:
        Environment variable value

    Raises:
        EnvironmentError: If variable is not set
    """
    value = os.environ.get(name)
    if value is None:
        raise EnvironmentError(f"Required environment variable '{name}' is not set")
    return value


def get_env_bool(name: str, default: bool = False) -> bool:
    """Get an environment variable as boolean.

    Truthy values: 'true', 'yes', '1', 'on'
    Falsy values: 'false', 'no', '0', 'off'

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value
    """
    value = os.environ.get(name)
    if value is None:
        return default

    return value.lower() in ("true", "yes", "1", "on")


def get_env_int(name: str, default: int = 0) -> int:
    """Get an environment variable as integer.

    Args:
        name: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Integer value
    """
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default
