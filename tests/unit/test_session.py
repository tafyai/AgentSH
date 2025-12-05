"""Tests for session management."""

import os
from unittest.mock import MagicMock, patch

import pytest

from agentsh.shell.session import (
    Job,
    JobState,
    SessionManager,
    SessionState,
    get_session,
    cleanup_session,
)


class TestJobState:
    """Tests for JobState enum."""

    def test_running_state(self) -> None:
        """Should have running state."""
        assert JobState.RUNNING == "running"

    def test_stopped_state(self) -> None:
        """Should have stopped state."""
        assert JobState.STOPPED == "stopped"

    def test_done_state(self) -> None:
        """Should have done state."""
        assert JobState.DONE == "done"

    def test_terminated_state(self) -> None:
        """Should have terminated state."""
        assert JobState.TERMINATED == "terminated"


class TestJob:
    """Tests for Job dataclass."""

    def test_create_job(self) -> None:
        """Should create job with required fields."""
        job = Job(
            job_id=1,
            pid=12345,
            command="sleep 10",
            state=JobState.RUNNING,
        )
        assert job.job_id == 1
        assert job.pid == 12345
        assert job.command == "sleep 10"
        assert job.state == JobState.RUNNING

    def test_job_defaults(self) -> None:
        """Should have default values."""
        job = Job(
            job_id=1,
            pid=12345,
            command="test",
        )
        assert job.state == JobState.RUNNING
        assert job.start_time is not None
        assert job.end_time is None
        assert job.exit_code is None

    def test_status_str_running(self) -> None:
        """Running job should show Running status."""
        job = Job(job_id=1, pid=123, command="test", state=JobState.RUNNING)
        assert job.status_str == "Running"

    def test_status_str_stopped(self) -> None:
        """Stopped job should show Stopped status."""
        job = Job(job_id=1, pid=123, command="test", state=JobState.STOPPED)
        assert job.status_str == "Stopped"

    def test_status_str_done(self) -> None:
        """Done job should show Done status."""
        job = Job(job_id=1, pid=123, command="test", state=JobState.DONE)
        assert job.status_str == "Done"

    def test_status_str_exit_code(self) -> None:
        """Done job with non-zero exit should show exit code."""
        job = Job(job_id=1, pid=123, command="test", state=JobState.DONE, exit_code=1)
        assert job.status_str == "Exit 1"

    def test_status_str_terminated(self) -> None:
        """Terminated job should show Terminated status."""
        job = Job(job_id=1, pid=123, command="test", state=JobState.TERMINATED)
        assert job.status_str == "Terminated"


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_create_session_state(self) -> None:
        """Should create session state."""
        from datetime import datetime
        state = SessionState(
            session_id="abc12345",
            start_time=datetime.now(),
            cwd="/tmp",
        )
        assert state.session_id == "abc12345"
        assert state.start_time is not None
        assert state.cwd == "/tmp"

    def test_session_state_defaults(self) -> None:
        """Should have default values."""
        from datetime import datetime
        state = SessionState(
            session_id="abc12345",
            start_time=datetime.now(),
            cwd="/tmp",
        )
        assert state.history == []
        assert state.variables == {}
        assert state.last_exit_code == 0


class TestSessionManager:
    """Tests for SessionManager."""

    def test_init(self) -> None:
        """Should initialize with defaults."""
        manager = SessionManager()
        assert manager._jobs == {}
        assert manager._next_job_id == 1
        assert manager._current_fg_job is None

    def test_init_with_session_id(self) -> None:
        """Should accept custom session ID."""
        manager = SessionManager(session_id="mytest")
        assert manager.session_id == "mytest"

    def test_session_id_property(self) -> None:
        """Should have session_id property."""
        manager = SessionManager()
        assert manager.session_id is not None
        assert len(manager.session_id) == 8

    def test_start_time_property(self) -> None:
        """Should have start_time property."""
        manager = SessionManager()
        assert manager.start_time is not None

    def test_add_job(self) -> None:
        """Should add job."""
        manager = SessionManager()
        job = manager.add_job(12345, "sleep 10")
        assert job.job_id == 1
        assert job.pid == 12345
        assert job.command == "sleep 10"
        assert job.state == JobState.RUNNING

    def test_add_multiple_jobs(self) -> None:
        """Should track multiple jobs."""
        manager = SessionManager()
        job1 = manager.add_job(123, "cmd1")
        job2 = manager.add_job(456, "cmd2")
        assert job1.job_id == 1
        assert job2.job_id == 2
        assert len(manager._jobs) == 2

    def test_get_job(self) -> None:
        """Should get job by id."""
        manager = SessionManager()
        job = manager.add_job(123, "test")
        retrieved = manager.get_job(1)
        assert retrieved is job

    def test_get_job_not_found(self) -> None:
        """Should return None for unknown job."""
        manager = SessionManager()
        assert manager.get_job(999) is None

    def test_list_jobs(self) -> None:
        """Should list all jobs."""
        manager = SessionManager()
        manager.add_job(123, "cmd1")
        manager.add_job(456, "cmd2")
        jobs = manager.list_jobs()
        assert len(jobs) == 2


class TestSessionModuleFunctions:
    """Tests for module-level functions."""

    def test_cleanup_session(self) -> None:
        """Should cleanup without error."""
        # Just ensure it doesn't raise
        cleanup_session()


class TestJobControl:
    """Tests for job control operations."""

    def test_foreground_no_jobs(self) -> None:
        """Should return False with no jobs."""
        manager = SessionManager()
        assert manager.foreground() is False

    def test_background_no_jobs(self) -> None:
        """Should return False with no jobs."""
        manager = SessionManager()
        assert manager.background() is False

    def test_foreground_specific_job_not_found(self) -> None:
        """Should return False for unknown job."""
        manager = SessionManager()
        assert manager.foreground(999) is False

    def test_background_specific_job_not_found(self) -> None:
        """Should return False for unknown job."""
        manager = SessionManager()
        assert manager.background(999) is False

    def test_kill_job_not_found(self) -> None:
        """Should return False for unknown job."""
        manager = SessionManager()
        assert manager.kill_job(999) is False

    def test_print_jobs_empty(self) -> None:
        """Should handle empty job list."""
        manager = SessionManager()
        manager.print_jobs()  # Should not raise
