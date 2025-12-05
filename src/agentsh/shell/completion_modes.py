"""Shell completion modes and proxy for hybrid completions.

Provides configurable completion modes that integrate AgentSH completions
with the underlying shell's native completion system.
"""

import asyncio
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class CompletionMode(str, Enum):
    """Tab completion modes.

    NATIVE: Only AgentSH completions (special commands, tools, paths)
    PASSTHROUGH: Full PTY passthrough - let the shell handle completions
    HYBRID: Merge AgentSH + shell completions (default)
    """

    NATIVE = "native"
    PASSTHROUGH = "passthrough"
    HYBRID = "hybrid"


@dataclass
class ShellCompletionResult:
    """Result from shell completion query."""

    completions: list[str] = field(default_factory=list)
    shell: str = ""
    query: str = ""
    success: bool = True
    error: Optional[str] = None


class ShellCompletionProxy:
    """Proxy for querying underlying shell's completion system.

    Supports bash, zsh, and fish completion systems.

    Example:
        proxy = ShellCompletionProxy()
        result = proxy.query("git sta")
        # Returns: ["status", "stash", "stage"]
    """

    # Timeout for completion queries (seconds)
    DEFAULT_TIMEOUT = 2.0

    # Maximum completions to return
    MAX_COMPLETIONS = 100

    def __init__(
        self,
        shell: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize completion proxy.

        Args:
            shell: Shell to use for completions. Auto-detected if None.
            timeout: Timeout for completion queries in seconds.
        """
        self.shell = shell or self._detect_shell()
        self.shell_name = os.path.basename(self.shell)
        self.timeout = timeout
        self._compgen_available: Optional[bool] = None

    def _detect_shell(self) -> str:
        """Detect the user's shell."""
        shell = os.environ.get("SHELL", "/bin/bash")
        if shutil.which(shell):
            return shell
        return "/bin/bash"

    def query(self, partial: str, cwd: Optional[str] = None) -> ShellCompletionResult:
        """Query shell for completions synchronously.

        Args:
            partial: Partial command/path to complete
            cwd: Working directory for context

        Returns:
            ShellCompletionResult with completions
        """
        try:
            return asyncio.get_event_loop().run_until_complete(
                self.query_async(partial, cwd)
            )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.query_async(partial, cwd))

    async def query_async(
        self, partial: str, cwd: Optional[str] = None
    ) -> ShellCompletionResult:
        """Query shell for completions asynchronously.

        Args:
            partial: Partial command/path to complete
            cwd: Working directory for context

        Returns:
            ShellCompletionResult with completions
        """
        if not partial:
            return ShellCompletionResult(shell=self.shell_name, query=partial)

        try:
            if self.shell_name in ("bash", "sh"):
                return await self._query_bash(partial, cwd)
            elif self.shell_name == "zsh":
                return await self._query_zsh(partial, cwd)
            elif self.shell_name == "fish":
                return await self._query_fish(partial, cwd)
            else:
                # Fall back to bash-style
                return await self._query_bash(partial, cwd)

        except asyncio.TimeoutError:
            logger.debug("Completion query timed out", partial=partial)
            return ShellCompletionResult(
                shell=self.shell_name,
                query=partial,
                success=False,
                error="timeout",
            )
        except Exception as e:
            logger.debug("Completion query failed", partial=partial, error=str(e))
            return ShellCompletionResult(
                shell=self.shell_name,
                query=partial,
                success=False,
                error=str(e),
            )

    async def _query_bash(
        self, partial: str, cwd: Optional[str] = None
    ) -> ShellCompletionResult:
        """Query bash for completions using compgen."""
        completions: list[str] = []

        # Parse the partial input
        words = self._safe_split(partial)
        if not words:
            return ShellCompletionResult(shell="bash", query=partial)

        # Determine what to complete
        if len(words) == 1 and not partial.endswith(" "):
            # Completing command name
            completions = await self._compgen_commands(words[0], cwd)
        else:
            # Completing arguments
            word_to_complete = words[-1] if not partial.endswith(" ") else ""
            completions = await self._compgen_files(word_to_complete, cwd)

        return ShellCompletionResult(
            completions=completions[: self.MAX_COMPLETIONS],
            shell="bash",
            query=partial,
        )

    async def _compgen_commands(
        self, prefix: str, cwd: Optional[str] = None
    ) -> list[str]:
        """Get command completions using compgen."""
        # compgen -c: commands (aliases, builtins, functions, executables)
        cmd = f"compgen -c -- {shlex.quote(prefix)} 2>/dev/null | head -n {self.MAX_COMPLETIONS}"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=os.environ,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            return stdout.decode().strip().split("\n") if stdout else []
        except Exception:
            return []

    async def _compgen_files(
        self, prefix: str, cwd: Optional[str] = None
    ) -> list[str]:
        """Get file completions using compgen."""
        # compgen -f: files, -d: directories
        cmd = f"compgen -f -- {shlex.quote(prefix)} 2>/dev/null | head -n {self.MAX_COMPLETIONS}"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=os.environ,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)

            if not stdout:
                return []

            completions = []
            for line in stdout.decode().strip().split("\n"):
                if line:
                    # Add trailing slash for directories
                    full_path = os.path.join(cwd or ".", line) if not line.startswith("/") else line
                    if os.path.isdir(full_path):
                        completions.append(line + "/")
                    else:
                        completions.append(line)
            return completions
        except Exception:
            return []

    async def _query_zsh(
        self, partial: str, cwd: Optional[str] = None
    ) -> ShellCompletionResult:
        """Query zsh for completions.

        Zsh's completion system is complex. We use a simplified approach
        that captures basic completions.
        """
        # Use zsh with completion initialization
        # This is a simplified version - full zsh completion is very complex
        words = self._safe_split(partial)
        if not words:
            return ShellCompletionResult(shell="zsh", query=partial)

        completions: list[str] = []

        if len(words) == 1 and not partial.endswith(" "):
            # Command completion - use hash lookup and path
            prefix = words[0]
            cmd = f'''
            zsh -c '
            setopt nullglob
            # Get commands from PATH
            for dir in ${{(s/:/)PATH}}; do
                for cmd in $dir/{shlex.quote(prefix)}*(N:t); do
                    echo "$cmd"
                done
            done | sort -u | head -n {self.MAX_COMPLETIONS}
            ' 2>/dev/null
            '''
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    cwd=cwd,
                )
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout
                )
                completions = stdout.decode().strip().split("\n") if stdout else []
            except Exception:
                pass
        else:
            # File completion
            word = words[-1] if not partial.endswith(" ") else ""
            completions = await self._compgen_files(word, cwd)

        return ShellCompletionResult(
            completions=[c for c in completions if c][: self.MAX_COMPLETIONS],
            shell="zsh",
            query=partial,
        )

    async def _query_fish(
        self, partial: str, cwd: Optional[str] = None
    ) -> ShellCompletionResult:
        """Query fish for completions using fish_complete."""
        # Fish has a built-in completion command
        cmd = f"fish -c 'complete -C {shlex.quote(partial)}' 2>/dev/null"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=os.environ,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)

            if not stdout:
                return ShellCompletionResult(shell="fish", query=partial)

            # Fish outputs: completion\tdescription
            completions = []
            for line in stdout.decode().strip().split("\n"):
                if line:
                    parts = line.split("\t", 1)
                    completions.append(parts[0])

            return ShellCompletionResult(
                completions=completions[: self.MAX_COMPLETIONS],
                shell="fish",
                query=partial,
            )

        except Exception as e:
            return ShellCompletionResult(
                shell="fish",
                query=partial,
                success=False,
                error=str(e),
            )

    def _safe_split(self, text: str) -> list[str]:
        """Safely split text into shell words."""
        try:
            return shlex.split(text)
        except ValueError:
            # Incomplete quoting - split on whitespace
            return text.split()

    def get_executable_completions(self, prefix: str) -> list[str]:
        """Get executable completions from PATH.

        Args:
            prefix: Command prefix

        Returns:
            List of matching executables
        """
        completions = set()
        prefix_lower = prefix.lower()

        path_dirs = os.environ.get("PATH", "").split(os.pathsep)

        for path_dir in path_dirs:
            try:
                if not os.path.isdir(path_dir):
                    continue

                for entry in os.listdir(path_dir):
                    if entry.lower().startswith(prefix_lower):
                        full_path = os.path.join(path_dir, entry)
                        if os.access(full_path, os.X_OK):
                            completions.add(entry)

                        if len(completions) >= self.MAX_COMPLETIONS:
                            break
            except (OSError, PermissionError):
                continue

            if len(completions) >= self.MAX_COMPLETIONS:
                break

        return sorted(completions)[: self.MAX_COMPLETIONS]


@dataclass
class CompletionConfig:
    """Configuration for shell completion."""

    mode: CompletionMode = CompletionMode.HYBRID
    shell: Optional[str] = None
    timeout: float = 2.0
    include_hidden: bool = False
    max_results: int = 100

    # Priority weights for hybrid mode
    priority_special_commands: int = 100
    priority_tools: int = 80
    priority_shell_commands: int = 60
    priority_files: int = 40


def merge_completions(
    agentsh_completions: list[str],
    shell_completions: list[str],
    config: Optional[CompletionConfig] = None,
) -> list[str]:
    """Merge AgentSH and shell completions with deduplication.

    Args:
        agentsh_completions: Completions from AgentSH
        shell_completions: Completions from underlying shell
        config: Completion configuration

    Returns:
        Merged and deduplicated completions
    """
    config = config or CompletionConfig()

    # Use dict to preserve order while deduplicating
    seen: dict[str, int] = {}

    # AgentSH completions have higher priority
    for i, comp in enumerate(agentsh_completions):
        if comp not in seen:
            seen[comp] = i

    # Add shell completions that aren't duplicates
    offset = len(agentsh_completions)
    for i, comp in enumerate(shell_completions):
        if comp not in seen:
            seen[comp] = offset + i

    # Sort by original order (AgentSH first, then shell)
    merged = sorted(seen.keys(), key=lambda x: seen[x])

    return merged[: config.max_results]
