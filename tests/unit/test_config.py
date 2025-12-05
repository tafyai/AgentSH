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


class TestConfigLoaderExtended:
    """Extended tests for configuration loader."""

    def test_get_default_config_path(self) -> None:
        """Test getting default config path."""
        from agentsh.config.loader import get_default_config_path

        path = get_default_config_path()
        assert path == Path.home() / ".agentsh" / "config.yaml"

    def test_get_config_paths_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting config paths when none exist."""
        from agentsh.config.loader import get_config_paths

        # Change to temp directory where no configs exist
        monkeypatch.chdir(tmp_path)

        # Mock home to avoid finding user config
        monkeypatch.setattr(Path, 'home', lambda: tmp_path / "fake_home")

        paths = get_config_paths()
        # Should be empty since no config files exist
        assert paths == []

    def test_get_config_paths_with_project_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting config paths with project config."""
        from agentsh.config.loader import get_config_paths

        # Create a project config
        project_config = tmp_path / ".agentsh.yaml"
        project_config.write_text("log_level: INFO")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, 'home', lambda: tmp_path / "fake_home")

        paths = get_config_paths()
        assert project_config in paths

    def test_load_yaml_config(self, tmp_path: Path) -> None:
        """Test loading YAML config file."""
        from agentsh.config.loader import load_yaml_config

        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
log_level: DEBUG
llm:
  provider: openai
  model: gpt-4
""")

        config = load_yaml_config(config_file)
        assert config["log_level"] == "DEBUG"
        assert config["llm"]["provider"] == "openai"

    def test_load_yaml_config_empty(self, tmp_path: Path) -> None:
        """Test loading empty YAML config file."""
        from agentsh.config.loader import load_yaml_config

        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = load_yaml_config(config_file)
        assert config == {}

    def test_create_default_config(self, tmp_path: Path) -> None:
        """Test creating default configuration file."""
        from agentsh.config.loader import create_default_config

        config_path = tmp_path / "newconfig" / "config.yaml"
        create_default_config(config_path)

        assert config_path.exists()
        content = config_path.read_text()
        assert "# AgentSH Configuration" in content

    def test_load_config_with_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading config with environment variable overrides."""
        monkeypatch.setenv("AGENTSH_LOG_LEVEL", "WARNING")

        config = load_config(include_env=True)
        assert config.log_level == "WARNING"

    def test_load_config_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading config without environment variables."""
        monkeypatch.setenv("AGENTSH_LOG_LEVEL", "INVALID_LEVEL")

        # Should not fail because env is not included
        config = load_config(include_env=False)
        assert config.log_level != "INVALID_LEVEL"

    def test_parse_env_value_yes_no(self) -> None:
        """Test parsing yes/no boolean values."""
        assert _parse_env_value("yes") is True
        assert _parse_env_value("no") is False
        assert _parse_env_value("YES") is True
        assert _parse_env_value("NO") is False
        assert _parse_env_value("1") is True
        assert _parse_env_value("0") is False

    def test_deep_merge_with_non_dict_values(self) -> None:
        """Test deep merge with non-dict values."""
        base = {"a": [1, 2, 3], "b": "string"}
        override = {"a": [4, 5], "c": True}

        result = deep_merge(base, override)

        assert result["a"] == [4, 5]  # List is replaced, not merged
        assert result["b"] == "string"
        assert result["c"] is True

    def test_env_overrides_deeply_nested(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test deeply nested environment variable overrides."""
        monkeypatch.setenv("AGENTSH_LLM__PARAMETERS__MAX_TOKENS", "4096")
        monkeypatch.setenv("AGENTSH_LLM__PARAMETERS__TEMPERATURE", "0.7")

        overrides = get_env_overrides()

        assert overrides["llm"]["parameters"]["max_tokens"] == 4096
        assert overrides["llm"]["parameters"]["temperature"] == 0.7

    def test_load_config_merges_multiple_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that config files are merged properly."""
        from agentsh.config.loader import load_yaml_config

        # Create project config
        project_config = tmp_path / ".agentsh.yaml"
        project_config.write_text("""
log_level: DEBUG
shell:
  backend: bash
""")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, 'home', lambda: tmp_path / "fake_home")

        config = load_config(include_env=False)

        # Values from project config should be applied
        assert config.log_level == "DEBUG"
        assert config.shell.backend == "bash"
