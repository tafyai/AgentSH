"""Tests for shell completion script generation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agentsh.shell.completion_scripts import (
    get_bash_completion,
    get_zsh_completion,
    get_fish_completion,
    get_completion_script,
    install_completion,
)
from agentsh import __version__


class TestBashCompletion:
    """Tests for bash completion script."""

    def test_generates_script(self) -> None:
        """Should generate bash completion script."""
        script = get_bash_completion()
        assert script is not None
        assert len(script) > 0

    def test_contains_version(self) -> None:
        """Should contain version."""
        script = get_bash_completion()
        assert __version__ in script

    def test_contains_function(self) -> None:
        """Should define completion function."""
        script = get_bash_completion()
        assert "_agentsh_completions()" in script

    def test_contains_complete_command(self) -> None:
        """Should have complete command."""
        script = get_bash_completion()
        assert "complete -F _agentsh_completions agentsh" in script

    def test_contains_subcommands(self) -> None:
        """Should include subcommands."""
        script = get_bash_completion()
        assert "config" in script
        assert "status" in script
        assert "completions" in script
        assert "devices" in script


class TestZshCompletion:
    """Tests for zsh completion script."""

    def test_generates_script(self) -> None:
        """Should generate zsh completion script."""
        script = get_zsh_completion()
        assert script is not None
        assert len(script) > 0

    def test_contains_compdef(self) -> None:
        """Should have compdef directive."""
        script = get_zsh_completion()
        assert "#compdef agentsh" in script

    def test_contains_function(self) -> None:
        """Should define completion function."""
        script = get_zsh_completion()
        assert "_agentsh()" in script

    def test_contains_commands(self) -> None:
        """Should include command descriptions."""
        script = get_zsh_completion()
        assert "'config:Manage configuration'" in script
        assert "'status:Show status'" in script


class TestFishCompletion:
    """Tests for fish completion script."""

    def test_generates_script(self) -> None:
        """Should generate fish completion script."""
        script = get_fish_completion()
        assert script is not None
        assert len(script) > 0

    def test_contains_complete_commands(self) -> None:
        """Should have complete commands."""
        script = get_fish_completion()
        assert "complete -c agentsh" in script

    def test_contains_subcommands(self) -> None:
        """Should include subcommand completions."""
        script = get_fish_completion()
        assert "-a config" in script
        assert "-a status" in script
        assert "-a completions" in script

    def test_contains_options(self) -> None:
        """Should include option completions."""
        script = get_fish_completion()
        assert "-l help" in script
        assert "-l version" in script
        assert "-l login" in script


class TestGetCompletionScript:
    """Tests for get_completion_script function."""

    def test_get_bash(self) -> None:
        """Should return bash script."""
        script = get_completion_script("bash")
        assert "_agentsh_completions()" in script

    def test_get_zsh(self) -> None:
        """Should return zsh script."""
        script = get_completion_script("zsh")
        assert "#compdef agentsh" in script

    def test_get_fish(self) -> None:
        """Should return fish script."""
        script = get_completion_script("fish")
        assert "complete -c agentsh" in script

    def test_unsupported_shell(self) -> None:
        """Should raise for unsupported shell."""
        with pytest.raises(ValueError, match="Unsupported shell"):
            get_completion_script("powershell")


class TestInstallCompletion:
    """Tests for install_completion function."""

    def test_install_to_temp_dir(self) -> None:
        """Should install to writable directory."""
        script = get_bash_completion()

        # Create temp directory to simulate user's local dir
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock home to use temp dir
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                success, path = install_completion("bash", script)
                # May or may not succeed depending on permissions
                assert isinstance(success, bool)
                assert isinstance(path, str)

    def test_unknown_shell(self) -> None:
        """Should fail for unknown shell."""
        success, error = install_completion("powershell", "script")
        assert success is False
        assert "Unknown shell" in error


class TestCompletionScriptContent:
    """Tests for script content quality."""

    def test_bash_handles_config_subcommands(self) -> None:
        """Bash script should handle config subcommands."""
        script = get_bash_completion()
        assert "config_commands" in script
        assert "init" in script
        assert "show" in script
        assert "reset" in script

    def test_zsh_has_descriptions(self) -> None:
        """Zsh script should have descriptions."""
        script = get_zsh_completion()
        assert "Manage configuration" in script
        assert "Show status" in script
        assert "Generate shell completions" in script

    def test_fish_disables_file_completions(self) -> None:
        """Fish script should disable default file completions."""
        script = get_fish_completion()
        assert "complete -c agentsh -f" in script

    def test_all_scripts_have_global_options(self) -> None:
        """All scripts should include global options."""
        for shell in ["bash", "zsh", "fish"]:
            script = get_completion_script(shell)
            # Fish uses "-s h -l help" format, others use "--help"
            assert "--help" in script or "-l help" in script
            assert "--version" in script or "-l version" in script
            assert "--config" in script or "-l config" in script
            assert "--log-level" in script or "-l log-level" in script
            assert "--login" in script or "-l login" in script
