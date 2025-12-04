"""Prompt Renderer - Custom shell prompt with status indicators."""

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class AgentStatus(Enum):
    """Status of the AI agent."""

    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    ERROR = "error"


class PromptStyle(Enum):
    """Prompt styling options."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


@dataclass
class PromptContext:
    """Context information for rendering the prompt."""

    cwd: Path
    user: str
    hostname: str
    git_branch: Optional[str] = None
    git_dirty: bool = False
    agent_status: AgentStatus = AgentStatus.IDLE
    last_exit_code: int = 0
    virtual_env: Optional[str] = None


class PromptRenderer:
    """Renders custom prompts for AgentSH.

    The prompt includes:
    - [AS] indicator showing AgentSH is active
    - Current directory (abbreviated)
    - Git branch and status (if in a repo)
    - Agent status indicator
    - Virtual environment name (if active)

    Example prompts:
        [AS] ~/projects/myapp (main*) $
        [AS] ~/projects/myapp (main) [thinking] $
        [AS] /etc $
    """

    # Status indicators
    STATUS_ICONS = {
        AgentStatus.IDLE: "",
        AgentStatus.THINKING: "🤔",
        AgentStatus.EXECUTING: "⚡",
        AgentStatus.ERROR: "❌",
    }

    # Status text (for non-emoji terminals)
    STATUS_TEXT = {
        AgentStatus.IDLE: "",
        AgentStatus.THINKING: "[thinking]",
        AgentStatus.EXECUTING: "[running]",
        AgentStatus.ERROR: "[error]",
    }

    def __init__(
        self,
        style: PromptStyle = PromptStyle.STANDARD,
        use_color: bool = True,
        use_emoji: bool = False,
        indicator: str = "AS",
    ) -> None:
        """Initialize the prompt renderer.

        Args:
            style: Prompt style (minimal, standard, full)
            use_color: Whether to use ANSI colors
            use_emoji: Whether to use emoji status indicators
            indicator: Text to show in brackets (default: "AS")
        """
        self.style = style
        self.use_color = use_color
        self.use_emoji = use_emoji
        self.indicator = indicator

    def get_context(self) -> PromptContext:
        """Gather context information for prompt rendering.

        Returns:
            PromptContext with current environment info
        """
        cwd = Path.cwd()
        user = os.environ.get("USER", os.environ.get("USERNAME", "user"))
        hostname = os.uname().nodename

        # Get git info
        git_branch = self._get_git_branch()
        git_dirty = self._is_git_dirty() if git_branch else False

        # Get virtual environment
        virtual_env = self._get_virtual_env()

        return PromptContext(
            cwd=cwd,
            user=user,
            hostname=hostname,
            git_branch=git_branch,
            git_dirty=git_dirty,
            virtual_env=virtual_env,
        )

    def render_ps1(
        self,
        context: Optional[PromptContext] = None,
        agent_status: AgentStatus = AgentStatus.IDLE,
        last_exit_code: int = 0,
    ) -> str:
        """Render the primary prompt (PS1).

        Args:
            context: Prompt context. Auto-gathered if None.
            agent_status: Current agent status
            last_exit_code: Exit code of last command

        Returns:
            Formatted prompt string
        """
        if context is None:
            context = self.get_context()

        context.agent_status = agent_status
        context.last_exit_code = last_exit_code

        if self.style == PromptStyle.MINIMAL:
            return self._render_minimal(context)
        elif self.style == PromptStyle.FULL:
            return self._render_full(context)
        else:
            return self._render_standard(context)

    def render_ps2(self) -> str:
        """Render the continuation prompt (PS2).

        Returns:
            Continuation prompt string
        """
        if self.use_color:
            return f"{Colors.DIM}... {Colors.RESET}"
        return "... "

    def _render_minimal(self, context: PromptContext) -> str:
        """Render minimal prompt."""
        indicator = self._colorize(f"[{self.indicator}]", Colors.CYAN)
        prompt_char = self._get_prompt_char(context)
        return f"{indicator} {prompt_char} "

    def _render_standard(self, context: PromptContext) -> str:
        """Render standard prompt."""
        parts = []

        # AgentSH indicator
        parts.append(self._colorize(f"[{self.indicator}]", Colors.CYAN))

        # Directory
        cwd_display = self._abbreviate_path(context.cwd)
        parts.append(self._colorize(cwd_display, Colors.BLUE))

        # Git info
        if context.git_branch:
            git_str = self._format_git_info(context)
            parts.append(git_str)

        # Agent status
        status_str = self._format_agent_status(context.agent_status)
        if status_str:
            parts.append(status_str)

        # Prompt character
        prompt_char = self._get_prompt_char(context)

        return " ".join(parts) + f" {prompt_char} "

    def _render_full(self, context: PromptContext) -> str:
        """Render full prompt with all info."""
        parts = []

        # Virtual environment
        if context.virtual_env:
            parts.append(self._colorize(f"({context.virtual_env})", Colors.GREEN))

        # User@host
        user_host = f"{context.user}@{context.hostname}"
        parts.append(self._colorize(user_host, Colors.GREEN))

        # AgentSH indicator
        parts.append(self._colorize(f"[{self.indicator}]", Colors.CYAN + Colors.BOLD))

        # Full directory path
        parts.append(self._colorize(str(context.cwd), Colors.BLUE))

        # Git info
        if context.git_branch:
            git_str = self._format_git_info(context)
            parts.append(git_str)

        # Agent status
        status_str = self._format_agent_status(context.agent_status)
        if status_str:
            parts.append(status_str)

        # Last exit code (if non-zero)
        if context.last_exit_code != 0:
            parts.append(self._colorize(f"[{context.last_exit_code}]", Colors.RED))

        # Prompt character
        prompt_char = self._get_prompt_char(context)

        return " ".join(parts) + f"\n{prompt_char} "

    def _abbreviate_path(self, path: Path) -> str:
        """Abbreviate path for display.

        Replaces home directory with ~ and truncates long paths.
        """
        try:
            # Replace home with ~
            home = Path.home()
            if path == home:
                return "~"
            elif str(path).startswith(str(home)):
                return "~" + str(path)[len(str(home)) :]
            return str(path)
        except Exception:
            return str(path)

    def _format_git_info(self, context: PromptContext) -> str:
        """Format git branch and status."""
        if not context.git_branch:
            return ""

        branch = context.git_branch
        dirty_marker = "*" if context.git_dirty else ""

        color = Colors.RED if context.git_dirty else Colors.GREEN
        return self._colorize(f"({branch}{dirty_marker})", color)

    def _format_agent_status(self, status: AgentStatus) -> str:
        """Format agent status indicator."""
        if status == AgentStatus.IDLE:
            return ""

        if self.use_emoji:
            indicator = self.STATUS_ICONS.get(status, "")
        else:
            indicator = self.STATUS_TEXT.get(status, "")

        if not indicator:
            return ""

        color = {
            AgentStatus.THINKING: Colors.YELLOW,
            AgentStatus.EXECUTING: Colors.CYAN,
            AgentStatus.ERROR: Colors.RED,
        }.get(status, Colors.WHITE)

        return self._colorize(indicator, color)

    def _get_prompt_char(self, context: PromptContext) -> str:
        """Get the prompt character ($ or #)."""
        # Use # for root, $ for regular users
        char = "#" if os.geteuid() == 0 else "$"

        # Color based on last exit code
        if context.last_exit_code != 0:
            return self._colorize(char, Colors.RED)
        return self._colorize(char, Colors.BRIGHT_WHITE)

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_git_dirty(self) -> bool:
        """Check if git working directory has changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                return bool(result.stdout.strip())
        except Exception:
            pass
        return False

    def _get_virtual_env(self) -> Optional[str]:
        """Get active virtual environment name."""
        venv = os.environ.get("VIRTUAL_ENV")
        if venv:
            return Path(venv).name

        # Check for conda
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env and conda_env != "base":
            return conda_env

        return None


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Text with potential ANSI codes

    Returns:
        Text with ANSI codes removed
    """
    import re

    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)
