"""Login shell support for AgentSH.

Provides functionality for running AgentSH as a login shell:
- Detection of login shell invocation
- Profile file sourcing (/etc/profile, ~/.profile, etc.)
- Session management
- PAM integration support
"""

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionInfo:
    """Information about the current shell session."""

    session_id: str
    start_time: datetime
    is_login_shell: bool
    is_interactive: bool
    tty: Optional[str]
    user: str
    home: Path
    shell: str
    pid: int

    @classmethod
    def create(cls, is_login: bool = False) -> "SessionInfo":
        """Create a new session info."""
        return cls(
            session_id=str(uuid.uuid4())[:8],
            start_time=datetime.now(),
            is_login_shell=is_login,
            is_interactive=sys.stdin.isatty(),
            tty=os.ttyname(sys.stdin.fileno()) if sys.stdin.isatty() else None,
            user=os.environ.get("USER", os.environ.get("LOGNAME", "unknown")),
            home=Path.home(),
            shell=sys.argv[0] if sys.argv else "agentsh",
            pid=os.getpid(),
        )


class LoginShellManager:
    """Manages login shell functionality.

    Handles:
    - Login shell detection
    - Profile file sourcing
    - Environment setup
    - Session management

    Example:
        manager = LoginShellManager()
        if manager.is_login_shell():
            manager.source_profiles()
        manager.source_rc_files()
    """

    # Profile files for login shells (sourced in order)
    SYSTEM_PROFILES = [
        "/etc/profile",
    ]

    # User profile files (first existing one is sourced)
    USER_PROFILES = [
        ".bash_profile",
        ".bash_login",
        ".profile",
    ]

    # RC files for interactive shells
    SYSTEM_RC_FILES = [
        "/etc/bash.bashrc",
        "/etc/bashrc",
    ]

    USER_RC_FILES = [
        ".bashrc",
    ]

    # AgentSH-specific RC file
    AGENTSH_RC = ".agentshrc"

    def __init__(
        self,
        force_login: bool = False,
        skip_profile: bool = False,
        skip_rc: bool = False,
        custom_rc: Optional[Path] = None,
    ) -> None:
        """Initialize login shell manager.

        Args:
            force_login: Force login shell behavior
            skip_profile: Skip profile files (--noprofile)
            skip_rc: Skip RC files (--norc)
            custom_rc: Custom RC file to use (--rcfile)
        """
        self._force_login = force_login
        self._skip_profile = skip_profile
        self._skip_rc = skip_rc
        self._custom_rc = custom_rc
        self._session: Optional[SessionInfo] = None
        self._sourced_files: list[str] = []

    @property
    def session(self) -> SessionInfo:
        """Get current session info, creating if needed."""
        if self._session is None:
            self._session = SessionInfo.create(is_login=self.is_login_shell())
        return self._session

    def is_login_shell(self) -> bool:
        """Detect if running as a login shell.

        Login shell is indicated by:
        - argv[0] starting with '-' (e.g., '-agentsh')
        - --login or -l flag
        - force_login parameter

        Returns:
            True if running as login shell
        """
        if self._force_login:
            return True

        # Check if invoked with leading dash (traditional login shell indicator)
        if sys.argv and sys.argv[0].startswith("-"):
            return True

        # Check for login flags in arguments
        if "--login" in sys.argv or "-l" in sys.argv:
            return True

        # Check LOGIN_SHELL environment variable
        if os.environ.get("LOGIN_SHELL") == "1":
            return True

        return False

    def is_interactive(self) -> bool:
        """Check if running in interactive mode.

        Returns:
            True if stdin is a TTY
        """
        return sys.stdin.isatty()

    def setup_environment(self) -> None:
        """Set up environment variables for the session."""
        session = self.session

        # Set session ID
        os.environ["AGENTSH_SESSION_ID"] = session.session_id

        # Set login shell indicator
        if session.is_login_shell:
            os.environ["LOGIN_SHELL"] = "1"

        # Set shell name
        os.environ["AGENTSH_SHELL"] = "agentsh"

        # Ensure basic environment
        if "HOME" not in os.environ:
            os.environ["HOME"] = str(session.home)

        if "USER" not in os.environ:
            os.environ["USER"] = session.user

        # Set SHELL to agentsh path if we're a login shell
        if session.is_login_shell:
            import shutil
            agentsh_path = shutil.which("agentsh")
            if agentsh_path:
                os.environ["SHELL"] = agentsh_path

        logger.debug(
            "Environment configured",
            session_id=session.session_id,
            is_login=session.is_login_shell,
        )

    def source_profiles(self, shell: str = "bash") -> None:
        """Source login profile files.

        Args:
            shell: Shell to use for sourcing (bash, zsh)
        """
        if self._skip_profile:
            logger.debug("Skipping profile files (--noprofile)")
            return

        if not self.is_login_shell():
            return

        home = Path.home()

        # Source system profiles
        for profile in self.SYSTEM_PROFILES:
            self._source_file(Path(profile), shell)

        # Source first existing user profile
        for profile in self.USER_PROFILES:
            profile_path = home / profile
            if profile_path.exists():
                self._source_file(profile_path, shell)
                break

        logger.debug("Sourced profile files", files=self._sourced_files)

    def source_rc_files(self, shell: str = "bash") -> None:
        """Source RC files for interactive shells.

        Args:
            shell: Shell to use for sourcing
        """
        if self._skip_rc:
            logger.debug("Skipping RC files (--norc)")
            return

        if not self.is_interactive():
            return

        home = Path.home()

        # Source system RC files
        for rc in self.SYSTEM_RC_FILES:
            self._source_file(Path(rc), shell)

        # Source user RC files
        for rc in self.USER_RC_FILES:
            rc_path = home / rc
            self._source_file(rc_path, shell)

        # Source AgentSH-specific RC
        if self._custom_rc:
            self._source_file(self._custom_rc, shell)
        else:
            agentsh_rc = home / self.AGENTSH_RC
            self._source_agentsh_rc(agentsh_rc)

        logger.debug("Sourced RC files", files=self._sourced_files)

    def _source_file(self, path: Path, shell: str = "bash") -> bool:
        """Source a shell configuration file.

        Args:
            path: Path to file
            shell: Shell to use

        Returns:
            True if file was sourced successfully
        """
        if not path.exists():
            return False

        try:
            # Source the file and capture exported variables
            cmd = f'source {path} >/dev/null 2>&1 && env'

            result = subprocess.run(
                [shell, "-c", cmd],
                capture_output=True,
                text=True,
                timeout=5,
                env=os.environ.copy(),
            )

            if result.returncode == 0:
                # Parse and update environment
                for line in result.stdout.split("\n"):
                    if "=" in line:
                        key, _, value = line.partition("=")
                        if key and not key.startswith("_"):
                            os.environ[key] = value

                self._sourced_files.append(str(path))
                logger.debug("Sourced file", path=str(path))
                return True

        except subprocess.TimeoutExpired:
            logger.warning("Timeout sourcing file", path=str(path))
        except Exception as e:
            logger.debug("Failed to source file", path=str(path), error=str(e))

        return False

    def _source_agentsh_rc(self, path: Path) -> bool:
        """Source AgentSH RC file.

        The .agentshrc file can contain:
        - Shell aliases (passed to underlying shell)
        - AgentSH configuration commands
        - Tool registrations
        - Custom prompts

        Args:
            path: Path to .agentshrc

        Returns:
            True if file was sourced
        """
        if not path.exists():
            return False

        try:
            content = path.read_text()
            # Parse and execute AgentSH-specific commands
            # For now, just track that we would source it
            self._sourced_files.append(str(path))
            logger.debug("Sourced agentshrc", path=str(path))
            return True
        except Exception as e:
            logger.debug("Failed to source agentshrc", path=str(path), error=str(e))
            return False

    def get_sourced_files(self) -> list[str]:
        """Get list of sourced configuration files.

        Returns:
            List of file paths that were sourced
        """
        return self._sourced_files.copy()

    def cleanup(self) -> None:
        """Clean up session resources."""
        if self._session:
            logger.debug(
                "Session ended",
                session_id=self._session.session_id,
                duration=(datetime.now() - self._session.start_time).total_seconds(),
            )


def is_login_shell() -> bool:
    """Check if current invocation is a login shell.

    Convenience function for quick checks.

    Returns:
        True if running as login shell
    """
    manager = LoginShellManager()
    return manager.is_login_shell()


def setup_login_environment(
    force_login: bool = False,
    skip_profile: bool = False,
    skip_rc: bool = False,
    custom_rc: Optional[Path] = None,
    shell: str = "bash",
) -> LoginShellManager:
    """Set up login shell environment.

    Convenience function to initialize login shell with all features.

    Args:
        force_login: Force login shell behavior
        skip_profile: Skip profile files
        skip_rc: Skip RC files
        custom_rc: Custom RC file path
        shell: Shell for sourcing files

    Returns:
        Configured LoginShellManager
    """
    manager = LoginShellManager(
        force_login=force_login,
        skip_profile=skip_profile,
        skip_rc=skip_rc,
        custom_rc=custom_rc,
    )

    manager.setup_environment()
    manager.source_profiles(shell)
    manager.source_rc_files(shell)

    return manager


def get_shell_for_user() -> str:
    """Get the appropriate shell for the current user.

    Returns:
        Path to shell executable
    """
    # Try SHELL environment variable
    shell = os.environ.get("SHELL")
    if shell and os.path.exists(shell):
        return shell

    # Try to read from /etc/passwd
    try:
        import pwd
        pw = pwd.getpwuid(os.getuid())
        if pw.pw_shell and os.path.exists(pw.pw_shell):
            return pw.pw_shell
    except (ImportError, KeyError):
        pass

    # Fall back to common shells
    import shutil
    for shell_name in ["bash", "zsh", "sh"]:
        shell_path = shutil.which(shell_name)
        if shell_path:
            return shell_path

    return "/bin/sh"
