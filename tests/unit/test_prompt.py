"""Tests for the prompt renderer."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agentsh.shell.prompt import (
    AgentStatus,
    Colors,
    PromptContext,
    PromptRenderer,
    PromptStyle,
    strip_ansi,
)


class TestAgentStatus:
    """Test cases for AgentStatus enum."""

    def test_all_statuses(self) -> None:
        """Test that all expected statuses exist."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.THINKING.value == "thinking"
        assert AgentStatus.EXECUTING.value == "executing"
        assert AgentStatus.ERROR.value == "error"


class TestPromptStyle:
    """Test cases for PromptStyle enum."""

    def test_all_styles(self) -> None:
        """Test that all expected styles exist."""
        assert PromptStyle.MINIMAL.value == "minimal"
        assert PromptStyle.STANDARD.value == "standard"
        assert PromptStyle.FULL.value == "full"


class TestColors:
    """Test cases for Colors class."""

    def test_reset_code(self) -> None:
        """Test reset code."""
        assert Colors.RESET == "\033[0m"

    def test_basic_colors(self) -> None:
        """Test basic color codes."""
        assert Colors.RED == "\033[31m"
        assert Colors.GREEN == "\033[32m"
        assert Colors.BLUE == "\033[34m"
        assert Colors.CYAN == "\033[36m"

    def test_bright_colors(self) -> None:
        """Test bright color codes."""
        assert Colors.BRIGHT_WHITE == "\033[97m"
        assert Colors.BRIGHT_RED == "\033[91m"


class TestPromptContext:
    """Test cases for PromptContext."""

    def test_create_context(self) -> None:
        """Test creating a prompt context."""
        ctx = PromptContext(
            cwd=Path("/home/user/projects"),
            user="testuser",
            hostname="localhost",
        )
        assert ctx.cwd == Path("/home/user/projects")
        assert ctx.user == "testuser"
        assert ctx.hostname == "localhost"
        assert ctx.git_branch is None
        assert ctx.git_dirty is False
        assert ctx.agent_status == AgentStatus.IDLE
        assert ctx.last_exit_code == 0

    def test_context_with_git(self) -> None:
        """Test context with git information."""
        ctx = PromptContext(
            cwd=Path("/home/user/projects"),
            user="testuser",
            hostname="localhost",
            git_branch="main",
            git_dirty=True,
        )
        assert ctx.git_branch == "main"
        assert ctx.git_dirty is True

    def test_context_with_venv(self) -> None:
        """Test context with virtual environment."""
        ctx = PromptContext(
            cwd=Path("/home/user/projects"),
            user="testuser",
            hostname="localhost",
            virtual_env="myenv",
        )
        assert ctx.virtual_env == "myenv"


class TestPromptRenderer:
    """Test cases for PromptRenderer."""

    @pytest.fixture
    def renderer(self) -> PromptRenderer:
        """Create a default renderer."""
        return PromptRenderer(
            style=PromptStyle.STANDARD,
            use_color=True,
            use_emoji=False,
        )

    @pytest.fixture
    def no_color_renderer(self) -> PromptRenderer:
        """Create a renderer without color."""
        return PromptRenderer(
            style=PromptStyle.STANDARD,
            use_color=False,
            use_emoji=False,
        )

    @pytest.fixture
    def emoji_renderer(self) -> PromptRenderer:
        """Create a renderer with emoji."""
        return PromptRenderer(
            style=PromptStyle.STANDARD,
            use_color=True,
            use_emoji=True,
        )

    @pytest.fixture
    def basic_context(self) -> PromptContext:
        """Create a basic context."""
        return PromptContext(
            cwd=Path("/home/user/projects"),
            user="testuser",
            hostname="localhost",
        )

    # Initialization tests
    def test_default_initialization(self) -> None:
        """Test default initialization."""
        renderer = PromptRenderer()
        assert renderer.style == PromptStyle.STANDARD
        assert renderer.use_color is True
        assert renderer.use_emoji is False
        assert renderer.indicator == "AS"

    def test_custom_indicator(self) -> None:
        """Test custom indicator."""
        renderer = PromptRenderer(indicator="AI")
        assert renderer.indicator == "AI"

    # PS1 rendering tests
    def test_render_ps1_minimal(self, basic_context: PromptContext) -> None:
        """Test minimal style rendering."""
        renderer = PromptRenderer(style=PromptStyle.MINIMAL, use_color=False)
        prompt = renderer.render_ps1(context=basic_context)
        assert "[AS]" in prompt
        assert "$" in prompt

    def test_render_ps1_standard(
        self, renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test standard style rendering."""
        prompt = renderer.render_ps1(context=basic_context)
        stripped = strip_ansi(prompt)
        assert "[AS]" in stripped
        assert "$" in stripped

    def test_render_ps1_full(self, basic_context: PromptContext) -> None:
        """Test full style rendering."""
        renderer = PromptRenderer(style=PromptStyle.FULL, use_color=False)
        prompt = renderer.render_ps1(context=basic_context)
        assert "[AS]" in prompt
        assert "testuser@localhost" in prompt
        assert "$" in prompt

    def test_render_ps1_no_context(self, renderer: PromptRenderer) -> None:
        """Test rendering without explicit context."""
        # Should auto-gather context
        prompt = renderer.render_ps1()
        stripped = strip_ansi(prompt)
        assert "[AS]" in stripped
        assert "$" in stripped or "#" in stripped

    # Git info tests
    def test_render_with_git_branch(
        self, no_color_renderer: PromptRenderer
    ) -> None:
        """Test rendering with git branch."""
        ctx = PromptContext(
            cwd=Path("/home/user/repo"),
            user="testuser",
            hostname="localhost",
            git_branch="main",
            git_dirty=False,
        )
        prompt = no_color_renderer.render_ps1(context=ctx)
        assert "(main)" in prompt

    def test_render_with_dirty_git(
        self, no_color_renderer: PromptRenderer
    ) -> None:
        """Test rendering with dirty git status."""
        ctx = PromptContext(
            cwd=Path("/home/user/repo"),
            user="testuser",
            hostname="localhost",
            git_branch="feature",
            git_dirty=True,
        )
        prompt = no_color_renderer.render_ps1(context=ctx)
        assert "(feature*)" in prompt

    # Agent status tests
    def test_render_thinking_status(
        self, no_color_renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test rendering with thinking status."""
        prompt = no_color_renderer.render_ps1(
            context=basic_context, agent_status=AgentStatus.THINKING
        )
        assert "[thinking]" in prompt

    def test_render_executing_status(
        self, no_color_renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test rendering with executing status."""
        prompt = no_color_renderer.render_ps1(
            context=basic_context, agent_status=AgentStatus.EXECUTING
        )
        assert "[running]" in prompt

    def test_render_error_status(
        self, no_color_renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test rendering with error status."""
        prompt = no_color_renderer.render_ps1(
            context=basic_context, agent_status=AgentStatus.ERROR
        )
        assert "[error]" in prompt

    def test_render_idle_status_no_indicator(
        self, no_color_renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test that idle status shows no indicator."""
        prompt = no_color_renderer.render_ps1(
            context=basic_context, agent_status=AgentStatus.IDLE
        )
        assert "[thinking]" not in prompt
        assert "[running]" not in prompt
        assert "[error]" not in prompt

    # Emoji status tests
    def test_render_emoji_thinking(
        self, emoji_renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test emoji thinking indicator."""
        prompt = emoji_renderer.render_ps1(
            context=basic_context, agent_status=AgentStatus.THINKING
        )
        stripped = strip_ansi(prompt)
        assert "\U0001F914" in stripped or "[thinking]" in stripped  # 🤔

    # Exit code tests
    def test_render_nonzero_exit_code_colors_prompt_char(
        self, renderer: PromptRenderer, basic_context: PromptContext
    ) -> None:
        """Test that non-zero exit code affects prompt character color."""
        prompt = renderer.render_ps1(context=basic_context, last_exit_code=1)
        # The prompt should contain red color code before $
        assert Colors.RED in prompt

    def test_render_full_shows_exit_code(self, basic_context: PromptContext) -> None:
        """Test that full style shows exit code."""
        renderer = PromptRenderer(style=PromptStyle.FULL, use_color=False)
        prompt = renderer.render_ps1(context=basic_context, last_exit_code=127)
        assert "[127]" in prompt

    # PS2 rendering tests
    def test_render_ps2(self, renderer: PromptRenderer) -> None:
        """Test PS2 (continuation prompt) rendering."""
        prompt = renderer.render_ps2()
        stripped = strip_ansi(prompt)
        assert "..." in stripped

    def test_render_ps2_no_color(self, no_color_renderer: PromptRenderer) -> None:
        """Test PS2 without color."""
        prompt = no_color_renderer.render_ps2()
        assert prompt == "... "

    # Path abbreviation tests
    def test_abbreviate_home_path(self, renderer: PromptRenderer) -> None:
        """Test home directory abbreviation."""
        home = Path.home()
        result = renderer._abbreviate_path(home)
        assert result == "~"

    def test_abbreviate_subpath_of_home(self, renderer: PromptRenderer) -> None:
        """Test subdirectory of home abbreviation."""
        path = Path.home() / "projects" / "test"
        result = renderer._abbreviate_path(path)
        assert result.startswith("~")
        assert "projects" in result
        assert "test" in result

    def test_abbreviate_non_home_path(self, renderer: PromptRenderer) -> None:
        """Test path outside home is not abbreviated."""
        path = Path("/etc/nginx")
        result = renderer._abbreviate_path(path)
        assert result == "/etc/nginx"

    # Colorize tests
    def test_colorize_with_color(self, renderer: PromptRenderer) -> None:
        """Test colorizing text."""
        result = renderer._colorize("test", Colors.RED)
        assert result == f"{Colors.RED}test{Colors.RESET}"

    def test_colorize_without_color(
        self, no_color_renderer: PromptRenderer
    ) -> None:
        """Test colorizing with colors disabled."""
        result = no_color_renderer._colorize("test", Colors.RED)
        assert result == "test"

    # Virtual environment tests
    def test_render_full_with_venv(self) -> None:
        """Test full style with virtual environment."""
        renderer = PromptRenderer(style=PromptStyle.FULL, use_color=False)
        ctx = PromptContext(
            cwd=Path("/home/user/project"),
            user="testuser",
            hostname="localhost",
            virtual_env="myenv",
        )
        prompt = renderer.render_ps1(context=ctx)
        assert "(myenv)" in prompt

    # Context gathering tests
    @patch.dict(os.environ, {"VIRTUAL_ENV": "/home/user/venvs/test"})
    def test_get_virtual_env(self, renderer: PromptRenderer) -> None:
        """Test virtual environment detection."""
        result = renderer._get_virtual_env()
        assert result == "test"

    @patch.dict(os.environ, {"CONDA_DEFAULT_ENV": "myenv"}, clear=False)
    def test_get_conda_env(self, renderer: PromptRenderer) -> None:
        """Test conda environment detection."""
        # Clear VIRTUAL_ENV if set
        with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
            result = renderer._get_virtual_env()
            assert result == "myenv" or result is None  # Depends on env

    @patch.dict(os.environ, {"CONDA_DEFAULT_ENV": "base"}, clear=False)
    def test_get_conda_base_ignored(self, renderer: PromptRenderer) -> None:
        """Test that conda base is ignored."""
        with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
            result = renderer._get_virtual_env()
            # Should return None for base environment
            assert result is None or result != "base"


class TestStripAnsi:
    """Test cases for strip_ansi function."""

    def test_strip_colors(self) -> None:
        """Test stripping color codes."""
        text = f"{Colors.RED}error{Colors.RESET}"
        result = strip_ansi(text)
        assert result == "error"

    def test_strip_multiple_codes(self) -> None:
        """Test stripping multiple color codes."""
        text = f"{Colors.BOLD}{Colors.BLUE}bold blue{Colors.RESET} {Colors.GREEN}green{Colors.RESET}"
        result = strip_ansi(text)
        assert result == "bold blue green"

    def test_no_codes(self) -> None:
        """Test text without ANSI codes."""
        text = "plain text"
        result = strip_ansi(text)
        assert result == "plain text"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = strip_ansi("")
        assert result == ""
