"""Tests for login shell support."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentsh.shell.login import (
    LoginShellManager,
    SessionInfo,
    is_login_shell,
    setup_login_environment,
    get_shell_for_user,
)


class TestSessionInfo:
    """Tests for SessionInfo dataclass."""

    def test_create_session(self) -> None:
        """Should create session with defaults."""
        session = SessionInfo.create()
        assert session.session_id is not None
        assert len(session.session_id) == 8
        assert session.start_time is not None
        assert session.user is not None
        assert session.pid == os.getpid()

    def test_create_login_session(self) -> None:
        """Should create login session."""
        session = SessionInfo.create(is_login=True)
        assert session.is_login_shell is True

    def test_create_non_login_session(self) -> None:
        """Should create non-login session."""
        session = SessionInfo.create(is_login=False)
        assert session.is_login_shell is False

    def test_session_has_home(self) -> None:
        """Should have home directory."""
        session = SessionInfo.create()
        assert session.home == Path.home()


class TestLoginShellManager:
    """Tests for LoginShellManager."""

    def test_init_defaults(self) -> None:
        """Should initialize with defaults."""
        manager = LoginShellManager()
        assert manager._force_login is False
        assert manager._skip_profile is False
        assert manager._skip_rc is False
        assert manager._custom_rc is None

    def test_init_force_login(self) -> None:
        """Should accept force_login."""
        manager = LoginShellManager(force_login=True)
        assert manager._force_login is True

    def test_init_skip_options(self) -> None:
        """Should accept skip options."""
        manager = LoginShellManager(skip_profile=True, skip_rc=True)
        assert manager._skip_profile is True
        assert manager._skip_rc is True

    def test_init_custom_rc(self) -> None:
        """Should accept custom RC file."""
        rc_path = Path("/custom/rc")
        manager = LoginShellManager(custom_rc=rc_path)
        assert manager._custom_rc == rc_path

    def test_session_property(self) -> None:
        """Should create session on demand."""
        manager = LoginShellManager()
        session = manager.session
        assert session is not None
        assert session.session_id is not None
        # Should return same session on subsequent calls
        assert manager.session is session

    def test_is_login_shell_force(self) -> None:
        """Force login should return True."""
        manager = LoginShellManager(force_login=True)
        assert manager.is_login_shell() is True

    def test_is_login_shell_env_var(self) -> None:
        """Should check LOGIN_SHELL env var."""
        with patch.dict(os.environ, {"LOGIN_SHELL": "1"}):
            manager = LoginShellManager()
            assert manager.is_login_shell() is True

    def test_is_login_shell_default(self) -> None:
        """Should return False by default."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove LOGIN_SHELL if present
            os.environ.pop("LOGIN_SHELL", None)
            manager = LoginShellManager()
            # May or may not be login shell depending on how tests run
            result = manager.is_login_shell()
            assert isinstance(result, bool)

    def test_is_interactive_tty(self) -> None:
        """Should detect interactive mode."""
        manager = LoginShellManager()
        result = manager.is_interactive()
        # Result depends on test environment
        assert isinstance(result, bool)

    def test_setup_environment(self) -> None:
        """Should set environment variables."""
        manager = LoginShellManager()
        manager.setup_environment()

        assert "AGENTSH_SESSION_ID" in os.environ
        assert "AGENTSH_SHELL" in os.environ
        assert os.environ["AGENTSH_SHELL"] == "agentsh"

    def test_setup_environment_login(self) -> None:
        """Should set LOGIN_SHELL for login shells."""
        manager = LoginShellManager(force_login=True)
        manager.setup_environment()
        assert os.environ.get("LOGIN_SHELL") == "1"

    def test_get_sourced_files_empty(self) -> None:
        """Should return empty list initially."""
        manager = LoginShellManager()
        assert manager.get_sourced_files() == []

    def test_source_profiles_skipped(self) -> None:
        """Should skip profiles when flag set."""
        manager = LoginShellManager(skip_profile=True, force_login=True)
        manager.source_profiles("bash")
        # Should not have sourced any files
        assert manager.get_sourced_files() == []

    def test_source_rc_skipped(self) -> None:
        """Should skip RC when flag set."""
        manager = LoginShellManager(skip_rc=True)
        manager.source_rc_files("bash")
        assert manager.get_sourced_files() == []

    def test_cleanup(self) -> None:
        """Should cleanup session."""
        manager = LoginShellManager()
        _ = manager.session  # Create session
        manager.cleanup()  # Should not raise


class TestLoginShellDetection:
    """Tests for login shell detection edge cases."""

    def test_argv_leading_dash(self) -> None:
        """Should detect leading dash in argv[0]."""
        with patch.object(sys, "argv", ["-agentsh"]):
            manager = LoginShellManager()
            assert manager.is_login_shell() is True

    def test_argv_login_flag(self) -> None:
        """Should detect --login flag."""
        with patch.object(sys, "argv", ["agentsh", "--login"]):
            manager = LoginShellManager()
            assert manager.is_login_shell() is True

    def test_argv_l_flag(self) -> None:
        """Should detect -l flag."""
        with patch.object(sys, "argv", ["agentsh", "-l"]):
            manager = LoginShellManager()
            assert manager.is_login_shell() is True


class TestLoginShellFunctions:
    """Tests for module-level functions."""

    def test_is_login_shell_function(self) -> None:
        """Should provide is_login_shell function."""
        result = is_login_shell()
        assert isinstance(result, bool)

    def test_setup_login_environment_function(self) -> None:
        """Should set up login environment."""
        manager = setup_login_environment(
            force_login=True,
            skip_profile=True,
            skip_rc=True,
        )
        assert isinstance(manager, LoginShellManager)
        assert "AGENTSH_SESSION_ID" in os.environ

    def test_get_shell_for_user(self) -> None:
        """Should find a shell."""
        shell = get_shell_for_user()
        assert shell is not None
        assert os.path.exists(shell) or shell.startswith("/")


class TestProfileSourcing:
    """Tests for profile file sourcing."""

    def test_profile_files_list(self) -> None:
        """Should have profile file lists."""
        assert len(LoginShellManager.SYSTEM_PROFILES) > 0
        assert len(LoginShellManager.USER_PROFILES) > 0
        assert len(LoginShellManager.SYSTEM_RC_FILES) > 0
        assert len(LoginShellManager.USER_RC_FILES) > 0

    def test_agentshrc_constant(self) -> None:
        """Should have AGENTSH_RC constant."""
        assert LoginShellManager.AGENTSH_RC == ".agentshrc"

    def test_source_file_nonexistent(self) -> None:
        """Should handle nonexistent files."""
        manager = LoginShellManager()
        result = manager._source_file(Path("/nonexistent/file"), "bash")
        assert result is False

    def test_source_agentshrc_nonexistent(self) -> None:
        """Should handle nonexistent agentshrc."""
        manager = LoginShellManager()
        result = manager._source_agentsh_rc(Path("/nonexistent/.agentshrc"))
        assert result is False


class TestLoginShellEnvironment:
    """Tests for environment handling."""

    def test_home_set(self) -> None:
        """Should ensure HOME is set."""
        manager = LoginShellManager()
        manager.setup_environment()
        assert "HOME" in os.environ

    def test_user_set(self) -> None:
        """Should ensure USER is set."""
        manager = LoginShellManager()
        manager.setup_environment()
        assert "USER" in os.environ

    def test_session_id_format(self) -> None:
        """Session ID should be 8 characters."""
        manager = LoginShellManager()
        manager.setup_environment()
        session_id = os.environ.get("AGENTSH_SESSION_ID", "")
        assert len(session_id) == 8
