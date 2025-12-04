"""Audit Logging - Security event logging for compliance."""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from agentsh.security.classifier import RiskLevel
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """Types of auditable actions."""

    COMMAND_EXECUTED = "command_executed"
    COMMAND_BLOCKED = "command_blocked"
    COMMAND_APPROVED = "command_approved"
    COMMAND_DENIED = "command_denied"
    COMMAND_EDITED = "command_edited"
    APPROVAL_TIMEOUT = "approval_timeout"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TOOL_INVOKED = "tool_invoked"
    TOOL_FAILED = "tool_failed"
    CONFIG_CHANGED = "config_changed"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class AuditEvent:
    """A security audit event.

    Attributes:
        timestamp: When the event occurred
        action: Type of action
        user: User who initiated the action
        command: Command or action details
        risk_level: Risk level if applicable
        result: Outcome of the action
        approver: Who approved (if applicable)
        device_id: Target device (if applicable)
        session_id: Session identifier
        metadata: Additional context
    """

    timestamp: datetime
    action: AuditAction
    user: str
    command: str
    risk_level: Optional[RiskLevel] = None
    result: Optional[str] = None
    approver: Optional[str] = None
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "user": self.user,
            "command": self.command,
        }

        if self.risk_level is not None:
            d["risk_level"] = self.risk_level.name

        if self.result is not None:
            d["result"] = self.result

        if self.approver is not None:
            d["approver"] = self.approver

        if self.device_id is not None:
            d["device_id"] = self.device_id

        if self.session_id is not None:
            d["session_id"] = self.session_id

        if self.metadata:
            d["metadata"] = self.metadata

        return d

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=AuditAction(data["action"]),
            user=data["user"],
            command=data["command"],
            risk_level=RiskLevel[data["risk_level"]] if "risk_level" in data else None,
            result=data.get("result"),
            approver=data.get("approver"),
            device_id=data.get("device_id"),
            session_id=data.get("session_id"),
            metadata=data.get("metadata"),
        )


class AuditLogger:
    """Logs security events for compliance and analysis.

    Maintains an append-only audit log of all security-relevant events.

    Example:
        audit = AuditLogger(log_path=Path("~/.agentsh/audit.log"))

        # Log a command execution
        audit.log_command_executed(
            command="ls -la",
            user="alice",
            risk_level=RiskLevel.SAFE,
        )

        # Query recent events
        events = audit.get_recent(n=10)
    """

    def __init__(
        self,
        log_path: Optional[Path] = None,
        session_id: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    ) -> None:
        """Initialize the audit logger.

        Args:
            log_path: Path to audit log file
            session_id: Current session identifier
            max_file_size: Maximum log file size before rotation
        """
        self.log_path = log_path or self._default_path()
        self.session_id = session_id or self._generate_session_id()
        self.max_file_size = max_file_size

        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "AuditLogger initialized",
            log_path=str(self.log_path),
            session_id=self.session_id,
        )

    def _default_path(self) -> Path:
        """Get default audit log path."""
        return Path.home() / ".agentsh" / "audit.log"

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid

        return str(uuid.uuid4())[:8]

    def _get_user(self) -> str:
        """Get current user."""
        return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    def log(self, event: AuditEvent) -> None:
        """Log an audit event.

        Args:
            event: Event to log
        """
        # Set session ID if not set
        if event.session_id is None:
            event.session_id = self.session_id

        # Check file size and rotate if needed
        self._check_rotation()

        # Append to log file
        try:
            with open(self.log_path, "a") as f:
                f.write(event.to_json() + "\n")

            logger.debug(
                "Audit event logged",
                action=event.action.value,
                user=event.user,
            )
        except Exception as e:
            logger.error("Failed to write audit log", error=str(e))

    def _check_rotation(self) -> None:
        """Check if log file needs rotation."""
        if self.log_path.exists():
            if self.log_path.stat().st_size >= self.max_file_size:
                self._rotate()

    def _rotate(self) -> None:
        """Rotate the audit log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_path = self.log_path.with_suffix(f".{timestamp}.log")

        try:
            self.log_path.rename(rotated_path)
            logger.info("Audit log rotated", new_path=str(rotated_path))
        except Exception as e:
            logger.error("Failed to rotate audit log", error=str(e))

    # Convenience methods for common events

    def log_command_executed(
        self,
        command: str,
        user: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.SAFE,
        device_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log a command execution.

        Args:
            command: Command that was executed
            user: User who executed it
            risk_level: Risk level of command
            device_id: Target device
            metadata: Additional context
        """
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.COMMAND_EXECUTED,
                user=user or self._get_user(),
                command=command,
                risk_level=risk_level,
                result="success",
                device_id=device_id,
                metadata=metadata,
            )
        )

    def log_command_blocked(
        self,
        command: str,
        reason: str,
        user: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        """Log a blocked command.

        Args:
            command: Command that was blocked
            reason: Why it was blocked
            user: User who attempted it
            risk_level: Risk level
        """
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.COMMAND_BLOCKED,
                user=user or self._get_user(),
                command=command,
                risk_level=risk_level,
                result=reason,
            )
        )

    def log_command_approved(
        self,
        command: str,
        approver: str,
        user: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        """Log an approved command.

        Args:
            command: Command that was approved
            approver: Who approved it
            user: User who requested it
            risk_level: Risk level
        """
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.COMMAND_APPROVED,
                user=user or self._get_user(),
                command=command,
                risk_level=risk_level,
                approver=approver,
            )
        )

    def log_command_denied(
        self,
        command: str,
        reason: str,
        user: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        """Log a denied command.

        Args:
            command: Command that was denied
            reason: Why it was denied
            user: User who requested it
            risk_level: Risk level
        """
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.COMMAND_DENIED,
                user=user or self._get_user(),
                command=command,
                risk_level=risk_level,
                result=reason,
            )
        )

    def log_session_start(self, metadata: Optional[dict] = None) -> None:
        """Log session start."""
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.SESSION_START,
                user=self._get_user(),
                command="session_start",
                metadata=metadata,
            )
        )

    def log_session_end(self, metadata: Optional[dict] = None) -> None:
        """Log session end."""
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.SESSION_END,
                user=self._get_user(),
                command="session_end",
                metadata=metadata,
            )
        )

    def log_security_violation(
        self,
        description: str,
        command: str,
        user: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log a security violation.

        Args:
            description: Description of the violation
            command: Related command
            user: User involved
            metadata: Additional context
        """
        self.log(
            AuditEvent(
                timestamp=datetime.now(),
                action=AuditAction.SECURITY_VIOLATION,
                user=user or self._get_user(),
                command=command,
                risk_level=RiskLevel.CRITICAL,
                result=description,
                metadata=metadata,
            )
        )

    def get_recent(self, n: int = 100) -> list[AuditEvent]:
        """Get recent audit events.

        Args:
            n: Number of events to return

        Returns:
            List of recent events (newest first)
        """
        events = []

        if not self.log_path.exists():
            return events

        try:
            with open(self.log_path) as f:
                lines = f.readlines()

            for line in reversed(lines[-n:]):
                try:
                    data = json.loads(line.strip())
                    events.append(AuditEvent.from_dict(data))
                except (json.JSONDecodeError, KeyError):
                    continue

        except Exception as e:
            logger.error("Failed to read audit log", error=str(e))

        return events

    def get_by_user(self, user: str, limit: int = 100) -> list[AuditEvent]:
        """Get events for a specific user.

        Args:
            user: User to filter by
            limit: Maximum events to return

        Returns:
            List of events for the user
        """
        all_events = self.get_recent(limit * 10)  # Read more to filter
        return [e for e in all_events if e.user == user][:limit]

    def get_by_action(self, action: AuditAction, limit: int = 100) -> list[AuditEvent]:
        """Get events of a specific action type.

        Args:
            action: Action type to filter by
            limit: Maximum events to return

        Returns:
            List of events of that action type
        """
        all_events = self.get_recent(limit * 10)
        return [e for e in all_events if e.action == action][:limit]
