"""Risk Classifier - Analyzes commands for security risks."""

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class RiskLevel(IntEnum):
    """Risk level classification for commands.

    Uses IntEnum for easy comparison (CRITICAL > HIGH > MEDIUM > etc.)
    """

    SAFE = 0  # Read-only, no side effects
    LOW = 1  # Minor side effects, easily reversible
    MEDIUM = 2  # Moderate risk, may need approval
    HIGH = 3  # Significant risk, requires approval
    CRITICAL = 4  # System-threatening, always blocked


@dataclass
class RiskPattern:
    """A pattern that indicates a certain risk level."""

    pattern: str
    risk_level: RiskLevel
    description: str
    is_regex: bool = True

    def matches(self, command: str) -> bool:
        """Check if pattern matches the command."""
        if self.is_regex:
            return bool(re.search(self.pattern, command, re.IGNORECASE))
        return self.pattern.lower() in command.lower()


@dataclass
class CommandRiskAssessment:
    """Result of command risk analysis.

    Attributes:
        command: The analyzed command
        risk_level: Overall risk level
        reasons: List of reasons for the risk assessment
        matched_patterns: Patterns that matched
        is_blocked: Whether command should be blocked
        requires_approval: Whether command needs human approval
    """

    command: str
    risk_level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    is_blocked: bool = False
    requires_approval: bool = False

    @property
    def is_safe(self) -> bool:
        """Check if command is safe to execute."""
        return self.risk_level <= RiskLevel.LOW and not self.is_blocked


class RiskClassifier:
    """Classifies command risk levels based on patterns.

    This classifier analyzes shell commands to determine their risk level
    and whether they require approval or should be blocked.

    Example:
        classifier = RiskClassifier()
        result = classifier.classify("rm -rf /")
        print(result.risk_level)  # RiskLevel.CRITICAL
        print(result.is_blocked)  # True
    """

    # CRITICAL patterns - Always blocked
    CRITICAL_PATTERNS = [
        RiskPattern(
            r"rm\s+(-[rfRF]+\s+)*(/|/\*|\"\s*/\s*\"|'\s*/\s*')(\s|$)",
            RiskLevel.CRITICAL,
            "Recursive delete of root filesystem",
        ),
        RiskPattern(
            r"rm\s+(-[rfRF]+\s+)*~(\s|$|/)",
            RiskLevel.CRITICAL,
            "Recursive delete of home directory",
        ),
        RiskPattern(
            r"mkfs\.",
            RiskLevel.CRITICAL,
            "Filesystem format command",
        ),
        RiskPattern(
            r"dd\s+.*of=/dev/(sd|hd|nvme|vd)[a-z]",
            RiskLevel.CRITICAL,
            "Direct disk write",
        ),
        RiskPattern(
            r":\(\)\s*\{\s*:\|\:\s*&\s*\}\s*;",
            RiskLevel.CRITICAL,
            "Fork bomb pattern",
        ),
        RiskPattern(
            r"\>\s*/dev/(sd|hd|nvme|vd)[a-z]",
            RiskLevel.CRITICAL,
            "Redirect to disk device",
        ),
        RiskPattern(
            r"chmod\s+(-[rR]+\s+)*777\s+/(\s|$)",
            RiskLevel.CRITICAL,
            "Set world-writable permissions on root",
        ),
        RiskPattern(
            r"chown\s+(-[rR]+\s+)*\S+:\S+\s+/(\s|$)",
            RiskLevel.CRITICAL,
            "Change ownership of root filesystem",
        ),
    ]

    # HIGH risk patterns - Require approval
    HIGH_PATTERNS = [
        RiskPattern(
            r"rm\s+(-[rfRF]+)",
            RiskLevel.HIGH,
            "Recursive/force delete",
        ),
        RiskPattern(
            r"^sudo\s+",
            RiskLevel.HIGH,
            "Privileged command execution",
        ),
        RiskPattern(
            r"(useradd|userdel|usermod)\s+",
            RiskLevel.HIGH,
            "User account modification",
        ),
        RiskPattern(
            r"(groupadd|groupdel|groupmod)\s+",
            RiskLevel.HIGH,
            "Group modification",
        ),
        RiskPattern(
            r"systemctl\s+(stop|disable|mask)\s+",
            RiskLevel.HIGH,
            "Service stop/disable",
        ),
        RiskPattern(
            r"service\s+\S+\s+(stop|restart)",
            RiskLevel.HIGH,
            "Service management",
        ),
        RiskPattern(
            r"iptables\s+",
            RiskLevel.HIGH,
            "Firewall modification",
        ),
        RiskPattern(
            r"ufw\s+(disable|delete|reset)",
            RiskLevel.HIGH,
            "Firewall modification",
        ),
        RiskPattern(
            r"chmod\s+(-[rR]+\s+)*777\s+",
            RiskLevel.HIGH,
            "Set world-writable permissions",
        ),
        RiskPattern(
            r">\s*/etc/",
            RiskLevel.HIGH,
            "Write to system config",
        ),
        RiskPattern(
            r"kill\s+-9\s+",
            RiskLevel.HIGH,
            "Force kill process",
        ),
        RiskPattern(
            r"pkill\s+-9\s+",
            RiskLevel.HIGH,
            "Force kill processes by name",
        ),
        RiskPattern(
            r"shutdown|reboot|poweroff|halt",
            RiskLevel.HIGH,
            "System shutdown/reboot",
        ),
    ]

    # MEDIUM risk patterns - May need approval based on policy
    MEDIUM_PATTERNS = [
        RiskPattern(
            r"(apt|apt-get|yum|dnf|pacman|brew)\s+(install|remove|purge)",
            RiskLevel.MEDIUM,
            "Package management",
        ),
        RiskPattern(
            r"pip\s+install\s+",
            RiskLevel.MEDIUM,
            "Python package installation",
        ),
        RiskPattern(
            r"npm\s+(install|uninstall)\s+(-g|--global)",
            RiskLevel.MEDIUM,
            "Global npm package management",
        ),
        RiskPattern(
            r"\|\s*(bash|sh|zsh|python|perl|ruby)",
            RiskLevel.MEDIUM,
            "Pipe to shell interpreter",
        ),
        RiskPattern(
            r"curl\s+.*\|\s*",
            RiskLevel.MEDIUM,
            "Download and pipe",
        ),
        RiskPattern(
            r"wget\s+.*\|\s*",
            RiskLevel.MEDIUM,
            "Download and pipe",
        ),
        RiskPattern(
            r"eval\s+",
            RiskLevel.MEDIUM,
            "Dynamic command evaluation",
        ),
        RiskPattern(
            r"crontab\s+",
            RiskLevel.MEDIUM,
            "Cron job modification",
        ),
        RiskPattern(
            r"ssh\s+",
            RiskLevel.MEDIUM,
            "Remote shell access",
        ),
        RiskPattern(
            r"scp\s+",
            RiskLevel.MEDIUM,
            "Remote file transfer",
        ),
        RiskPattern(
            r"rsync\s+.*:",
            RiskLevel.MEDIUM,
            "Remote sync",
        ),
        RiskPattern(
            r"git\s+push\s+",
            RiskLevel.MEDIUM,
            "Push to remote repository",
        ),
        RiskPattern(
            r"git\s+push\s+.*--force",
            RiskLevel.HIGH,
            "Force push to repository",
        ),
        RiskPattern(
            r"docker\s+rm\s+",
            RiskLevel.MEDIUM,
            "Docker container removal",
        ),
        RiskPattern(
            r"docker\s+system\s+prune",
            RiskLevel.MEDIUM,
            "Docker system cleanup",
        ),
    ]

    # LOW risk patterns - Generally safe but have side effects
    LOW_PATTERNS = [
        RiskPattern(
            r"^(touch|mkdir|cp|mv)\s+",
            RiskLevel.LOW,
            "File/directory creation or move",
        ),
        RiskPattern(
            r"git\s+(add|commit|checkout|branch|merge)",
            RiskLevel.LOW,
            "Git local operations",
        ),
        RiskPattern(
            r"npm\s+install(\s|$)",
            RiskLevel.LOW,
            "Local npm install",
        ),
        RiskPattern(
            r"pip\s+install\s+.*-e\s+\.",
            RiskLevel.LOW,
            "Local pip editable install",
        ),
        RiskPattern(
            r"echo\s+.*>",
            RiskLevel.LOW,
            "Write to file",
        ),
    ]

    # SAFE patterns - Read-only operations
    SAFE_PATTERNS = [
        RiskPattern(
            r"^(ls|dir|pwd|whoami|hostname|date|cal|uptime)",
            RiskLevel.SAFE,
            "Read-only system info",
        ),
        RiskPattern(
            r"^(cat|head|tail|less|more|bat)\s+",
            RiskLevel.SAFE,
            "File viewing",
        ),
        RiskPattern(
            r"^(grep|rg|ag|ack|find|fd|locate)\s+",
            RiskLevel.SAFE,
            "Search operations",
        ),
        RiskPattern(
            r"^(wc|sort|uniq|diff|comm)\s+",
            RiskLevel.SAFE,
            "Text processing",
        ),
        RiskPattern(
            r"^(ps|top|htop|pgrep|lsof)",
            RiskLevel.SAFE,
            "Process viewing",
        ),
        RiskPattern(
            r"^(df|du|free|vmstat|iostat)",
            RiskLevel.SAFE,
            "System monitoring",
        ),
        RiskPattern(
            r"^(git\s+(status|log|diff|show|branch))",
            RiskLevel.SAFE,
            "Git read operations",
        ),
        RiskPattern(
            r"^(docker\s+(ps|images|logs))",
            RiskLevel.SAFE,
            "Docker read operations",
        ),
        RiskPattern(
            r"^(python|python3|node|ruby)\s+.*--version",
            RiskLevel.SAFE,
            "Version check",
        ),
        RiskPattern(
            r"^echo\s+[^>]*$",
            RiskLevel.SAFE,
            "Echo without redirect",
        ),
        RiskPattern(
            r"^(which|whereis|type|file)\s+",
            RiskLevel.SAFE,
            "Command lookup",
        ),
        RiskPattern(
            r"^man\s+",
            RiskLevel.SAFE,
            "Manual page",
        ),
        RiskPattern(
            r"^(env|printenv|set)(\s|$)",
            RiskLevel.SAFE,
            "Environment listing",
        ),
    ]

    def __init__(
        self,
        additional_patterns: Optional[list[RiskPattern]] = None,
        blocked_commands: Optional[list[str]] = None,
    ) -> None:
        """Initialize the risk classifier.

        Args:
            additional_patterns: Extra patterns to include
            blocked_commands: Specific commands to always block
        """
        self._patterns: list[RiskPattern] = []
        self._blocked_commands: set[str] = set(blocked_commands or [])

        # Add patterns in order of severity (check critical first)
        self._patterns.extend(self.CRITICAL_PATTERNS)
        self._patterns.extend(self.HIGH_PATTERNS)
        self._patterns.extend(self.MEDIUM_PATTERNS)
        self._patterns.extend(self.LOW_PATTERNS)
        self._patterns.extend(self.SAFE_PATTERNS)

        if additional_patterns:
            self._patterns.extend(additional_patterns)

        logger.info(
            "RiskClassifier initialized",
            pattern_count=len(self._patterns),
            blocked_count=len(self._blocked_commands),
        )

    def classify(self, command: str) -> CommandRiskAssessment:
        """Classify the risk level of a command.

        Args:
            command: Shell command to analyze

        Returns:
            CommandRiskAssessment with risk details
        """
        command = command.strip()

        if not command:
            return CommandRiskAssessment(
                command=command,
                risk_level=RiskLevel.SAFE,
                reasons=["Empty command"],
            )

        # Check explicit blocklist
        if command in self._blocked_commands:
            return CommandRiskAssessment(
                command=command,
                risk_level=RiskLevel.CRITICAL,
                reasons=["Command is explicitly blocked"],
                is_blocked=True,
            )

        # Analyze command
        matched_reasons: list[str] = []
        matched_pattern_names: list[str] = []
        max_risk = RiskLevel.SAFE

        for pattern in self._patterns:
            if pattern.matches(command):
                matched_reasons.append(pattern.description)
                matched_pattern_names.append(pattern.pattern)

                if pattern.risk_level > max_risk:
                    max_risk = pattern.risk_level

                # For efficiency, stop after finding CRITICAL
                if pattern.risk_level == RiskLevel.CRITICAL:
                    break

        # Determine blocking and approval requirements
        is_blocked = max_risk >= RiskLevel.CRITICAL
        requires_approval = max_risk >= RiskLevel.HIGH

        result = CommandRiskAssessment(
            command=command,
            risk_level=max_risk,
            reasons=matched_reasons if matched_reasons else ["No known risk patterns"],
            matched_patterns=matched_pattern_names,
            is_blocked=is_blocked,
            requires_approval=requires_approval,
        )

        logger.debug(
            "Command classified",
            command=command[:50],
            risk_level=max_risk.name,
            is_blocked=is_blocked,
            requires_approval=requires_approval,
        )

        return result

    def add_pattern(self, pattern: RiskPattern) -> None:
        """Add a custom risk pattern.

        Args:
            pattern: Pattern to add
        """
        self._patterns.append(pattern)

    def block_command(self, command: str) -> None:
        """Add a command to the blocklist.

        Args:
            command: Exact command to block
        """
        self._blocked_commands.add(command)

    def is_safe(self, command: str) -> bool:
        """Quick check if command is safe.

        Args:
            command: Command to check

        Returns:
            True if command is safe to execute
        """
        return self.classify(command).is_safe
