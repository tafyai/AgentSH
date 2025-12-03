"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from typing import Generator

from agentsh.config.schemas import AgentSHConfig
from agentsh.tools.registry import ToolRegistry


@pytest.fixture
def test_config() -> AgentSHConfig:
    """Create a test configuration."""
    return AgentSHConfig()


@pytest.fixture
def tool_registry() -> Generator[ToolRegistry, None, None]:
    """Create a fresh tool registry for testing."""
    registry = ToolRegistry()
    yield registry
    registry.clear()


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514

shell:
  backend: bash
  ai_prefix: "ai "

log_level: DEBUG
""")
    return config_file
