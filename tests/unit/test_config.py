"""Tests for configuration system."""

import os
from pathlib import Path

import pytest

from agentsh.config.schemas import (
    AgentSHConfig,
    LLMConfig,
    LLMProvider,
    SecurityMode,
)
from agentsh.config.loader import (
    load_config,
    deep_merge,
    get_env_overrides,
    _parse_env_value,
)


class TestConfigSchemas:
    """Test configuration schema validation."""

    def test_default_config_valid(self) -> None:
        """Default configuration should be valid."""
        config = AgentSHConfig()
        assert config.llm.provider == LLMProvider.ANTHROPIC
        assert config.shell.backend == "zsh"
        assert config.security.mode == SecurityMode.NORMAL

    def test_llm_config_validation(self) -> None:
        """LLM config should validate temperature range."""
        config = LLMConfig(temperature=0.5)
        assert config.temperature == 0.5

        with pytest.raises(ValueError):
            LLMConfig(temperature=3.0)  # Too high

    def test_log_level_validation(self) -> None:
        """Log level should be validated."""
        config = AgentSHConfig(log_level="DEBUG")
        assert config.log_level == "DEBUG"

        with pytest.raises(ValueError):
            AgentSHConfig(log_level="INVALID")

    def test_plugin_config_access(self) -> None:
        """Test plugin configuration access."""
        config = AgentSHConfig()

        assert config.is_plugin_enabled("shell") is True
        assert config.is_plugin_enabled("nonexistent") is False

        shell_config = config.get_plugin_config("shell")
        assert shell_config is not None
        assert shell_config.name == "shell"


class TestConfigLoader:
    """Test configuration loading."""

    def test_load_default_config(self) -> None:
        """Loading without file should return defaults."""
        config = load_config(include_env=False)
        assert isinstance(config, AgentSHConfig)

    def test_load_from_file(self, temp_config_file: Path) -> None:
        """Should load config from file."""
        config = load_config(temp_config_file, include_env=False)
        assert config.shell.backend == "bash"
        assert config.log_level == "DEBUG"

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Should raise error for missing explicit config file."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_deep_merge(self) -> None:
        """Test deep dictionary merging."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 10}, "e": 5}

        result = deep_merge(base, override)

        assert result["a"] == 1
        assert result["b"]["c"] == 10
        assert result["b"]["d"] == 3
        assert result["e"] == 5

    def test_parse_env_value_types(self) -> None:
        """Test parsing of environment variable types."""
        assert _parse_env_value("true") is True
        assert _parse_env_value("false") is False
        assert _parse_env_value("42") == 42
        assert _parse_env_value("3.14") == 3.14
        assert _parse_env_value("hello") == "hello"

    def test_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable overrides."""
        monkeypatch.setenv("AGENTSH_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("AGENTSH_LLM__PROVIDER", "openai")

        overrides = get_env_overrides()

        assert overrides["log_level"] == "DEBUG"
        assert overrides["llm"]["provider"] == "openai"
