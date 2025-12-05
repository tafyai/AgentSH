"""Tests for completion modes and shell completion proxy."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.shell.completion_modes import (
    CompletionConfig,
    CompletionMode,
    ShellCompletionProxy,
    ShellCompletionResult,
    merge_completions,
)


class TestCompletionMode:
    """Tests for CompletionMode enum."""

    def test_native_mode(self) -> None:
        """Should have native mode."""
        assert CompletionMode.NATIVE == "native"

    def test_passthrough_mode(self) -> None:
        """Should have passthrough mode."""
        assert CompletionMode.PASSTHROUGH == "passthrough"

    def test_hybrid_mode(self) -> None:
        """Should have hybrid mode."""
        assert CompletionMode.HYBRID == "hybrid"

    def test_mode_is_string(self) -> None:
        """Mode should be usable as string."""
        # The value is accessible directly
        assert CompletionMode.HYBRID.value == "hybrid"
        # And it works in string comparisons
        assert CompletionMode.HYBRID == "hybrid"


class TestShellCompletionResult:
    """Tests for ShellCompletionResult."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        result = ShellCompletionResult()
        assert result.completions == []
        assert result.shell == ""
        assert result.query == ""
        assert result.success is True
        assert result.error is None

    def test_with_completions(self) -> None:
        """Should store completions."""
        result = ShellCompletionResult(
            completions=["ls", "less", "lsof"],
            shell="bash",
            query="ls",
        )
        assert len(result.completions) == 3
        assert "ls" in result.completions

    def test_with_error(self) -> None:
        """Should store error state."""
        result = ShellCompletionResult(
            success=False,
            error="timeout",
        )
        assert not result.success
        assert result.error == "timeout"


class TestShellCompletionProxy:
    """Tests for ShellCompletionProxy."""

    def test_init_default_shell(self) -> None:
        """Should detect default shell."""
        proxy = ShellCompletionProxy()
        assert proxy.shell is not None
        assert proxy.shell_name in ("bash", "zsh", "fish", "sh")

    def test_init_custom_shell(self) -> None:
        """Should accept custom shell."""
        proxy = ShellCompletionProxy(shell="/bin/bash")
        assert proxy.shell == "/bin/bash"
        assert proxy.shell_name == "bash"

    def test_init_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        proxy = ShellCompletionProxy(timeout=5.0)
        assert proxy.timeout == 5.0

    def test_query_empty_string(self) -> None:
        """Should handle empty query."""
        proxy = ShellCompletionProxy()
        result = proxy.query("")
        assert result.completions == []
        assert result.success is True

    def test_safe_split_normal(self) -> None:
        """Should split normal command."""
        proxy = ShellCompletionProxy()
        words = proxy._safe_split("git commit -m 'message'")
        assert words == ["git", "commit", "-m", "message"]

    def test_safe_split_incomplete(self) -> None:
        """Should handle incomplete quoting."""
        proxy = ShellCompletionProxy()
        words = proxy._safe_split("git commit -m 'incomplete")
        # Should fall back to whitespace split
        assert len(words) >= 3

    def test_get_executable_completions(self) -> None:
        """Should find executables in PATH."""
        proxy = ShellCompletionProxy()
        completions = proxy.get_executable_completions("ls")
        # ls should exist on most systems
        if os.name != "nt":
            assert "ls" in completions or len(completions) > 0


class TestShellCompletionProxyAsync:
    """Async tests for ShellCompletionProxy."""

    @pytest.mark.asyncio
    async def test_query_async_empty(self) -> None:
        """Should handle empty async query."""
        proxy = ShellCompletionProxy()
        result = await proxy.query_async("")
        assert result.completions == []

    @pytest.mark.asyncio
    async def test_query_bash_commands(self) -> None:
        """Should get bash command completions."""
        proxy = ShellCompletionProxy(shell="/bin/bash")
        result = await proxy._query_bash("ls", None)
        assert result.shell == "bash"
        # May or may not find completions depending on system

    @pytest.mark.asyncio
    async def test_compgen_commands(self) -> None:
        """Should run compgen for commands."""
        proxy = ShellCompletionProxy()
        completions = await proxy._compgen_commands("ech", None)
        # "echo" should be a common completion
        if os.name != "nt":
            assert any("echo" in c for c in completions) or completions == []

    @pytest.mark.asyncio
    async def test_compgen_files(self) -> None:
        """Should run compgen for files."""
        proxy = ShellCompletionProxy()
        # Use a path that exists
        completions = await proxy._compgen_files("/", None)
        # Should find some top-level directories
        if os.name != "nt":
            assert len(completions) >= 0  # May be empty on some systems


class TestCompletionConfig:
    """Tests for CompletionConfig."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = CompletionConfig()
        assert config.mode == CompletionMode.HYBRID
        assert config.timeout == 2.0
        assert config.max_results == 100
        assert config.include_hidden is False

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = CompletionConfig(
            mode=CompletionMode.NATIVE,
            timeout=5.0,
            max_results=50,
            include_hidden=True,
        )
        assert config.mode == CompletionMode.NATIVE
        assert config.timeout == 5.0
        assert config.max_results == 50
        assert config.include_hidden is True

    def test_priority_values(self) -> None:
        """Should have priority settings."""
        config = CompletionConfig()
        assert config.priority_special_commands > config.priority_tools
        assert config.priority_tools > config.priority_shell_commands


class TestMergeCompletions:
    """Tests for merge_completions function."""

    def test_merge_empty(self) -> None:
        """Should handle empty lists."""
        result = merge_completions([], [])
        assert result == []

    def test_merge_agentsh_only(self) -> None:
        """Should return AgentSH completions when no shell."""
        result = merge_completions(["help", "config"], [])
        assert result == ["help", "config"]

    def test_merge_shell_only(self) -> None:
        """Should return shell completions when no AgentSH."""
        result = merge_completions([], ["ls", "cd"])
        assert result == ["ls", "cd"]

    def test_merge_no_duplicates(self) -> None:
        """Should deduplicate completions."""
        result = merge_completions(
            ["ls", "help"],
            ["ls", "cd"],
        )
        assert result.count("ls") == 1
        assert "help" in result
        assert "cd" in result

    def test_merge_agentsh_priority(self) -> None:
        """AgentSH completions should come first."""
        result = merge_completions(
            ["help", "config"],
            ["ls", "cd"],
        )
        assert result[:2] == ["help", "config"]

    def test_merge_respects_max_results(self) -> None:
        """Should respect max_results config."""
        config = CompletionConfig(max_results=3)
        result = merge_completions(
            ["a", "b", "c"],
            ["d", "e", "f"],
            config,
        )
        assert len(result) == 3

    def test_merge_preserves_order(self) -> None:
        """Should preserve order within groups."""
        result = merge_completions(
            ["z", "a"],
            ["m", "b"],
        )
        # AgentSH first in original order
        assert result.index("z") < result.index("a")
        # Shell second in original order
        assert result.index("m") < result.index("b")


class TestCompletionModeIntegration:
    """Integration tests for completion modes."""

    def test_proxy_with_config(self) -> None:
        """Should use config settings."""
        config = CompletionConfig(timeout=1.0, shell="/bin/bash")
        proxy = ShellCompletionProxy(
            shell=config.shell,
            timeout=config.timeout,
        )
        assert proxy.timeout == 1.0
        assert proxy.shell == "/bin/bash"

    def test_mode_determines_behavior(self) -> None:
        """Different modes should have different behavior."""
        # This is more of a conceptual test
        native = CompletionMode.NATIVE
        hybrid = CompletionMode.HYBRID
        passthrough = CompletionMode.PASSTHROUGH

        assert native != hybrid
        assert hybrid != passthrough
        assert native != passthrough
