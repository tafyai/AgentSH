"""Session management for AgentSH.

Provides session tracking, persistence, and job control.
"""

import os
import signal
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class JobState(str, Enum):
    """State of a background job."""

    RUNNING = "running"
    STOPPED = "stopped"
    DONE = "done"
    TERMINATED = "terminated"


@dataclass
class Job:
    """Represents a background job."""

    job_id: int
    pid: int
    command: str
    state: JobState = JobState.RUNNING
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None

    @property
    def status_str(self) -> str:
        """Get status string for display."""
        state_map = {
            JobState.RUNNING: "Running",
            JobState.STOPPED: "Stopped",
            JobState.DONE: "Done",
            JobState.TERMINATED: "Terminated",
        }
        status = state_map.get(self.state, "Unknown")
        if self.state == JobState.DONE and self.exit_code is not None:
            if self.exit_code != 0:
                status = f"Exit {self.exit_code}"
        return status


@dataclass
class SessionState:
    """Persistent session state."""

    session_id: str
    start_time: datetime
    cwd: str
    history: List[str] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)
    last_exit_code: int = 0


class SessionManager:
    """Manages shell session state and job control.

    Provides:
    - Session ID tracking
    - Job control (fg, bg, jobs)
    - Signal handling (SIGTSTP, SIGCONT)
    - Session persistence

    Example:
        session = SessionManager()
        session.start()

        # Add a background job
        job = session.add_job(pid=1234, command="sleep 100")

        # List jobs
        session.list_jobs()

        # Bring job to foreground
        session.foreground(job.job_id)
    """

    SESSION_DIR = Path.home() / ".agentsh" / "sessions"

    def __init__(self, session_id: Optional[str] = None) -> None:
        """Initialize session manager.

        Args:
            session_id: Optional session ID to resume
        """
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._start_time = datetime.now()
        self._jobs: Dict[int, Job] = {}
        self._next_job_id = 1
        self._current_fg_job: Optional[Job] = None

        # Original signal handlers
        self._original_sigtstp: Optional[signal.Handlers] = None
        self._original_sigcont: Optional[signal.Handlers] = None
        self._original_sigchld: Optional[signal.Handlers] = None

    @property
    def session_id(self) -> str:
        """Get session ID."""
        return self._session_id

    @property
    def start_time(self) -> datetime:
        """Get session start time."""
        return self._start_time

    def start(self) -> None:
        """Start the session and set up signal handlers."""
        # Set environment variable
        os.environ["AGENTSH_SESSION_ID"] = self._session_id

        # Set up signal handlers for job control
        self._setup_signal_handlers()

        # Create session directory
        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("Session started", session_id=self._session_id)

    def stop(self) -> None:
        """Stop the session and clean up."""
        # Restore original signal handlers
        self._restore_signal_handlers()

        # Clean up any remaining jobs
        for job in self._jobs.values():
            if job.state == JobState.RUNNING:
                try:
                    os.kill(job.pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass

        logger.info(
            "Session ended",
            session_id=self._session_id,
            duration=(datetime.now() - self._start_time).total_seconds(),
        )

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for job control."""
        try:
            # SIGTSTP (Ctrl+Z) - suspend foreground job
            self._original_sigtstp = signal.signal(
                signal.SIGTSTP, self._handle_sigtstp
            )

            # SIGCONT - continue stopped job
            self._original_sigcont = signal.signal(
                signal.SIGCONT, self._handle_sigcont
            )

            # SIGCHLD - child process state change
            self._original_sigchld = signal.signal(
                signal.SIGCHLD, self._handle_sigchld
            )

        except (ValueError, OSError) as e:
            logger.debug("Could not set up signal handlers", error=str(e))

    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        try:
            if self._original_sigtstp is not None:
                signal.signal(signal.SIGTSTP, self._original_sigtstp)
            if self._original_sigcont is not None:
                signal.signal(signal.SIGCONT, self._original_sigcont)
            if self._original_sigchld is not None:
                signal.signal(signal.SIGCHLD, self._original_sigchld)
        except (ValueError, OSError):
            pass

    def _handle_sigtstp(self, signum: int, frame: object) -> None:
        """Handle SIGTSTP (Ctrl+Z) - suspend foreground job."""
        if self._current_fg_job:
            try:
                os.kill(self._current_fg_job.pid, signal.SIGSTOP)
                self._current_fg_job.state = JobState.STOPPED
                print(f"\n[{self._current_fg_job.job_id}]+  Stopped    {self._current_fg_job.command}")
            except (OSError, ProcessLookupError):
                pass
            self._current_fg_job = None

    def _handle_sigcont(self, signum: int, frame: object) -> None:
        """Handle SIGCONT - continue stopped job."""
        pass  # Handled by fg/bg commands

    def _handle_sigchld(self, signum: int, frame: object) -> None:
        """Handle SIGCHLD - child process state change."""
        # Check status of all jobs
        for job in self._jobs.values():
            if job.state in (JobState.RUNNING, JobState.STOPPED):
                try:
                    pid, status = os.waitpid(job.pid, os.WNOHANG | os.WUNTRACED)
                    if pid == job.pid:
                        if os.WIFEXITED(status):
                            job.state = JobState.DONE
                            job.exit_code = os.WEXITSTATUS(status)
                            job.end_time = datetime.now()
                        elif os.WIFSIGNALED(status):
                            job.state = JobState.TERMINATED
                            job.end_time = datetime.now()
                        elif os.WIFSTOPPED(status):
                            job.state = JobState.STOPPED
                except (OSError, ChildProcessError):
                    pass

    def add_job(self, pid: int, command: str) -> Job:
        """Add a new background job.

        Args:
            pid: Process ID
            command: Command being executed

        Returns:
            Job object
        """
        job = Job(
            job_id=self._next_job_id,
            pid=pid,
            command=command,
        )
        self._jobs[job.job_id] = job
        self._next_job_id += 1

        logger.debug("Job added", job_id=job.job_id, pid=pid, command=command)
        return job

    def get_job(self, job_id: int) -> Optional[Job]:
        """Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None
        """
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Job]:
        """List all jobs.

        Returns:
            List of jobs
        """
        # Update job states
        self._update_job_states()
        return list(self._jobs.values())

    def _update_job_states(self) -> None:
        """Update states of all jobs."""
        for job in self._jobs.values():
            if job.state in (JobState.RUNNING, JobState.STOPPED):
                try:
                    pid, status = os.waitpid(job.pid, os.WNOHANG | os.WUNTRACED)
                    if pid == job.pid:
                        if os.WIFEXITED(status):
                            job.state = JobState.DONE
                            job.exit_code = os.WEXITSTATUS(status)
                            job.end_time = datetime.now()
                        elif os.WIFSIGNALED(status):
                            job.state = JobState.TERMINATED
                            job.end_time = datetime.now()
                        elif os.WIFSTOPPED(status):
                            job.state = JobState.STOPPED
                except (OSError, ChildProcessError):
                    # Process doesn't exist
                    if job.state == JobState.RUNNING:
                        job.state = JobState.DONE
                        job.end_time = datetime.now()

    def foreground(self, job_id: Optional[int] = None) -> bool:
        """Bring a job to foreground.

        Args:
            job_id: Job ID (or most recent if None)

        Returns:
            True if job was brought to foreground
        """
        if job_id is None:
            # Find most recent stopped or running job
            for jid in sorted(self._jobs.keys(), reverse=True):
                job = self._jobs[jid]
                if job.state in (JobState.RUNNING, JobState.STOPPED):
                    job_id = jid
                    break

        if job_id is None:
            print("fg: no current job")
            return False

        job = self._jobs.get(job_id)
        if job is None:
            print(f"fg: {job_id}: no such job")
            return False

        if job.state == JobState.STOPPED:
            try:
                os.kill(job.pid, signal.SIGCONT)
                job.state = JobState.RUNNING
            except (OSError, ProcessLookupError):
                print(f"fg: job has terminated")
                return False

        print(job.command)
        self._current_fg_job = job

        # Wait for job
        try:
            _, status = os.waitpid(job.pid, os.WUNTRACED)
            if os.WIFEXITED(status):
                job.state = JobState.DONE
                job.exit_code = os.WEXITSTATUS(status)
                job.end_time = datetime.now()
            elif os.WIFSIGNALED(status):
                job.state = JobState.TERMINATED
                job.end_time = datetime.now()
            elif os.WIFSTOPPED(status):
                job.state = JobState.STOPPED
        except (OSError, ChildProcessError):
            pass

        self._current_fg_job = None
        return True

    def background(self, job_id: Optional[int] = None) -> bool:
        """Continue a stopped job in background.

        Args:
            job_id: Job ID (or most recent stopped if None)

        Returns:
            True if job was continued
        """
        if job_id is None:
            # Find most recent stopped job
            for jid in sorted(self._jobs.keys(), reverse=True):
                job = self._jobs[jid]
                if job.state == JobState.STOPPED:
                    job_id = jid
                    break

        if job_id is None:
            print("bg: no current job")
            return False

        job = self._jobs.get(job_id)
        if job is None:
            print(f"bg: {job_id}: no such job")
            return False

        if job.state != JobState.STOPPED:
            print(f"bg: job {job_id} already in background")
            return False

        try:
            os.kill(job.pid, signal.SIGCONT)
            job.state = JobState.RUNNING
            print(f"[{job.job_id}]+ {job.command} &")
            return True
        except (OSError, ProcessLookupError):
            print(f"bg: job has terminated")
            return False

    def kill_job(self, job_id: int, sig: int = signal.SIGTERM) -> bool:
        """Kill a job.

        Args:
            job_id: Job ID
            sig: Signal to send (default SIGTERM)

        Returns:
            True if signal was sent
        """
        job = self._jobs.get(job_id)
        if job is None:
            return False

        try:
            os.kill(job.pid, sig)
            return True
        except (OSError, ProcessLookupError):
            return False

    def print_jobs(self) -> None:
        """Print job list (like 'jobs' command)."""
        jobs = self.list_jobs()
        if not jobs:
            return

        for job in jobs:
            if job.state in (JobState.DONE, JobState.TERMINATED):
                # Clean up completed jobs after displaying
                marker = "-"
            else:
                marker = "+"

            print(f"[{job.job_id}]{marker}  {job.status_str:<12}  {job.command}")

        # Remove completed jobs
        self._jobs = {
            jid: job for jid, job in self._jobs.items()
            if job.state not in (JobState.DONE, JobState.TERMINATED)
        }


# Global session manager
_session: Optional[SessionManager] = None


def get_session() -> SessionManager:
    """Get or create global session manager.

    Returns:
        SessionManager instance
    """
    global _session
    if _session is None:
        _session = SessionManager()
        _session.start()
    return _session


def cleanup_session() -> None:
    """Clean up global session."""
    global _session
    if _session is not None:
        _session.stop()
        _session = None
