"""Security Policies - Configurable security rules."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

from agentsh.security.classifier import RiskLevel
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class SecurityMode(Enum):
    """Security enforcement mode."""

    PERMISSIVE = "permissive"  # Log warnings but allow
    STANDARD = "standard"  # Require approval for high risk
    STRICT = "strict"  # Block high risk, approve medium
    PARANOID = "paranoid"  # Block medium+, approve low


@dataclass
class SecurityPolicy:
    """Security policy configuration.

    Defines what commands are allowed, blocked, and which require approval.

    Attributes:
        name: Policy name for identification
        mode: Overall security mode
        blocked_patterns: Regex patterns to always block
        allowed_patterns: Regex patterns to always allow (override blocks)
        require_approval_levels: Risk levels that need human approval
        max_command_length: Maximum allowed command length
        allow_sudo: Whether sudo commands are allowed
        allow_network: Whether network operations are allowed
        allowed_paths: Paths the agent can modify (glob patterns)
        blocked_paths: Paths the agent cannot touch
        timeout: Default approval timeout in seconds
    """

    name: str = "default"
    mode: SecurityMode = SecurityMode.STANDARD

    blocked_patterns: list[str] = field(default_factory=list)
    allowed_patterns: list[str] = field(default_factory=list)

    require_approval_levels: list[RiskLevel] = field(
        default_factory=lambda: [RiskLevel.HIGH]
    )

    max_command_length: int = 10000
    allow_sudo: bool = False
    allow_network: bool = True

    allowed_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(
        default_factory=lambda: [
            "/etc/*",
            "/usr/*",
            "/bin/*",
            "/sbin/*",
            "/boot/*",
            "/root/*",
        ]
    )

    timeout: float = 30.0

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Check if a risk level requires approval.

        Args:
            risk_level: Risk level to check

        Returns:
            True if approval is required
        """
        if self.mode == SecurityMode.PERMISSIVE:
            return False
        elif self.mode == SecurityMode.PARANOID:
            return risk_level >= RiskLevel.LOW
        elif self.mode == SecurityMode.STRICT:
            return risk_level >= RiskLevel.MEDIUM
        else:  # STANDARD
            return risk_level in self.require_approval_levels or risk_level >= RiskLevel.HIGH

    def is_blocked_by_mode(self, risk_level: RiskLevel) -> bool:
        """Check if a risk level is blocked by the security mode.

        Args:
            risk_level: Risk level to check

        Returns:
            True if blocked
        """
        if risk_level >= RiskLevel.CRITICAL:
            return True

        if self.mode == SecurityMode.PARANOID:
            return risk_level >= RiskLevel.MEDIUM
        elif self.mode == SecurityMode.STRICT:
            return risk_level >= RiskLevel.HIGH

        return False

    @classmethod
    def permissive(cls) -> "SecurityPolicy":
        """Create a permissive policy (for development)."""
        return cls(
            name="permissive",
            mode=SecurityMode.PERMISSIVE,
            allow_sudo=True,
            require_approval_levels=[],
        )

    @classmethod
    def standard(cls) -> "SecurityPolicy":
        """Create a standard policy (balanced security)."""
        return cls(
            name="standard",
            mode=SecurityMode.STANDARD,
            allow_sudo=False,
            require_approval_levels=[RiskLevel.HIGH],
        )

    @classmethod
    def strict(cls) -> "SecurityPolicy":
        """Create a strict policy (high security)."""
        return cls(
            name="strict",
            mode=SecurityMode.STRICT,
            allow_sudo=False,
            allow_network=False,
            require_approval_levels=[RiskLevel.MEDIUM, RiskLevel.HIGH],
        )

    @classmethod
    def paranoid(cls) -> "SecurityPolicy":
        """Create a paranoid policy (maximum security)."""
        return cls(
            name="paranoid",
            mode=SecurityMode.PARANOID,
            allow_sudo=False,
            allow_network=False,
            require_approval_levels=[RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH],
            blocked_paths=[
                "/etc/*",
                "/usr/*",
                "/bin/*",
                "/sbin/*",
                "/boot/*",
                "/root/*",
                "/var/*",
                "/tmp/*",
            ],
        )


@dataclass
class DevicePolicy:
    """Per-device security policy override.

    Allows different security settings for specific devices.
    """

    device_id: str
    policy: SecurityPolicy
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)


class PolicyManager:
    """Manages security policies.

    Loads policies from configuration and provides policy lookup.

    Example:
        manager = PolicyManager()
        policy = manager.get_policy()  # Default policy
        policy = manager.get_policy(device_id="robot-1")  # Device-specific
    """

    def __init__(
        self,
        default_policy: Optional[SecurityPolicy] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        """Initialize the policy manager.

        Args:
            default_policy: Default policy to use
            config_path: Path to policy configuration file
        """
        self._default_policy = default_policy or SecurityPolicy.standard()
        self._device_policies: dict[str, DevicePolicy] = {}
        self._config_path = config_path

        if config_path and config_path.exists():
            self._load_config(config_path)

        logger.info(
            "PolicyManager initialized",
            default_policy=self._default_policy.name,
            device_policies=len(self._device_policies),
        )

    def _load_config(self, path: Path) -> None:
        """Load policies from configuration file.

        Args:
            path: Path to YAML configuration
        """
        try:
            with open(path) as f:
                config = yaml.safe_load(f)

            if not config:
                return

            # Load default policy
            if "default_policy" in config:
                self._default_policy = self._parse_policy(config["default_policy"])

            # Load device policies
            for device_config in config.get("devices", []):
                device_id = device_config.get("id")
                if device_id:
                    policy = self._parse_policy(device_config.get("policy", {}))
                    self._device_policies[device_id] = DevicePolicy(
                        device_id=device_id,
                        policy=policy,
                        allowed_commands=device_config.get("allowed_commands", []),
                        blocked_commands=device_config.get("blocked_commands", []),
                    )

            logger.info("Loaded policies from config", path=str(path))

        except Exception as e:
            logger.error("Failed to load policy config", path=str(path), error=str(e))

    def _parse_policy(self, config: dict[str, Any]) -> SecurityPolicy:
        """Parse a policy from configuration dict.

        Args:
            config: Policy configuration

        Returns:
            SecurityPolicy instance
        """
        mode_str = config.get("mode", "standard")
        mode = SecurityMode(mode_str) if mode_str else SecurityMode.STANDARD

        approval_levels = []
        for level_str in config.get("require_approval_levels", ["high"]):
            try:
                approval_levels.append(RiskLevel[level_str.upper()])
            except KeyError:
                pass

        return SecurityPolicy(
            name=config.get("name", "custom"),
            mode=mode,
            blocked_patterns=config.get("blocked_patterns", []),
            allowed_patterns=config.get("allowed_patterns", []),
            require_approval_levels=approval_levels,
            max_command_length=config.get("max_command_length", 10000),
            allow_sudo=config.get("allow_sudo", False),
            allow_network=config.get("allow_network", True),
            allowed_paths=config.get("allowed_paths", []),
            blocked_paths=config.get("blocked_paths", []),
            timeout=config.get("timeout", 30.0),
        )

    def get_policy(self, device_id: Optional[str] = None) -> SecurityPolicy:
        """Get the security policy for a device.

        Args:
            device_id: Device identifier (uses default if not specified)

        Returns:
            SecurityPolicy for the device
        """
        if device_id and device_id in self._device_policies:
            return self._device_policies[device_id].policy
        return self._default_policy

    def get_device_policy(self, device_id: str) -> Optional[DevicePolicy]:
        """Get the full device policy including overrides.

        Args:
            device_id: Device identifier

        Returns:
            DevicePolicy or None if not configured
        """
        return self._device_policies.get(device_id)

    def set_default_policy(self, policy: SecurityPolicy) -> None:
        """Set the default policy.

        Args:
            policy: New default policy
        """
        self._default_policy = policy
        logger.info("Default policy updated", policy=policy.name)

    def add_device_policy(self, device_policy: DevicePolicy) -> None:
        """Add or update a device policy.

        Args:
            device_policy: Device policy to add
        """
        self._device_policies[device_policy.device_id] = device_policy
        logger.info("Device policy added", device_id=device_policy.device_id)
