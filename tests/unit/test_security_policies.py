"""Tests for security policies module."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from agentsh.security.classifier import RiskLevel
from agentsh.security.policies import (
    DevicePolicy,
    PolicyManager,
    SecurityMode,
    SecurityPolicy,
)


class TestSecurityMode:
    """Tests for SecurityMode enum."""

    def test_values(self) -> None:
        """Should have expected values."""
        assert SecurityMode.PERMISSIVE.value == "permissive"
        assert SecurityMode.STANDARD.value == "standard"
        assert SecurityMode.STRICT.value == "strict"
        assert SecurityMode.PARANOID.value == "paranoid"

    def test_all_modes_exist(self) -> None:
        """Should have all expected modes."""
        modes = list(SecurityMode)
        assert len(modes) == 4


class TestSecurityPolicy:
    """Tests for SecurityPolicy dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        policy = SecurityPolicy()

        assert policy.name == "default"
        assert policy.mode == SecurityMode.STANDARD
        assert policy.max_command_length == 10000
        assert policy.allow_sudo is False
        assert policy.allow_network is True
        assert policy.timeout == 30.0

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        policy = SecurityPolicy(
            name="custom",
            mode=SecurityMode.STRICT,
            allow_sudo=True,
            max_command_length=5000,
        )

        assert policy.name == "custom"
        assert policy.mode == SecurityMode.STRICT
        assert policy.allow_sudo is True
        assert policy.max_command_length == 5000

    def test_default_blocked_paths(self) -> None:
        """Should have default blocked paths."""
        policy = SecurityPolicy()

        assert "/etc/*" in policy.blocked_paths
        assert "/usr/*" in policy.blocked_paths
        assert "/bin/*" in policy.blocked_paths

    def test_default_require_approval_levels(self) -> None:
        """Should require approval for HIGH by default."""
        policy = SecurityPolicy()

        assert RiskLevel.HIGH in policy.require_approval_levels


class TestSecurityPolicyRequiresApproval:
    """Tests for SecurityPolicy.requires_approval method."""

    def test_permissive_never_requires(self) -> None:
        """Permissive mode should never require approval."""
        policy = SecurityPolicy(mode=SecurityMode.PERMISSIVE)

        assert policy.requires_approval(RiskLevel.SAFE) is False
        assert policy.requires_approval(RiskLevel.LOW) is False
        assert policy.requires_approval(RiskLevel.MEDIUM) is False
        assert policy.requires_approval(RiskLevel.HIGH) is False
        assert policy.requires_approval(RiskLevel.CRITICAL) is False

    def test_paranoid_requires_low_and_above(self) -> None:
        """Paranoid mode should require approval for LOW and above."""
        policy = SecurityPolicy(mode=SecurityMode.PARANOID)

        assert policy.requires_approval(RiskLevel.SAFE) is False
        assert policy.requires_approval(RiskLevel.LOW) is True
        assert policy.requires_approval(RiskLevel.MEDIUM) is True
        assert policy.requires_approval(RiskLevel.HIGH) is True

    def test_strict_requires_medium_and_above(self) -> None:
        """Strict mode should require approval for MEDIUM and above."""
        policy = SecurityPolicy(mode=SecurityMode.STRICT)

        assert policy.requires_approval(RiskLevel.SAFE) is False
        assert policy.requires_approval(RiskLevel.LOW) is False
        assert policy.requires_approval(RiskLevel.MEDIUM) is True
        assert policy.requires_approval(RiskLevel.HIGH) is True

    def test_standard_requires_high_and_above(self) -> None:
        """Standard mode should require approval for HIGH and above."""
        policy = SecurityPolicy(mode=SecurityMode.STANDARD)

        assert policy.requires_approval(RiskLevel.SAFE) is False
        assert policy.requires_approval(RiskLevel.LOW) is False
        assert policy.requires_approval(RiskLevel.MEDIUM) is False
        assert policy.requires_approval(RiskLevel.HIGH) is True

    def test_standard_respects_custom_levels(self) -> None:
        """Standard mode should respect custom approval levels."""
        policy = SecurityPolicy(
            mode=SecurityMode.STANDARD,
            require_approval_levels=[RiskLevel.MEDIUM],
        )

        assert policy.requires_approval(RiskLevel.LOW) is False
        assert policy.requires_approval(RiskLevel.MEDIUM) is True
        assert policy.requires_approval(RiskLevel.HIGH) is True


class TestSecurityPolicyIsBlockedByMode:
    """Tests for SecurityPolicy.is_blocked_by_mode method."""

    def test_critical_always_blocked(self) -> None:
        """Critical risk should always be blocked."""
        for mode in SecurityMode:
            policy = SecurityPolicy(mode=mode)
            assert policy.is_blocked_by_mode(RiskLevel.CRITICAL) is True

    def test_paranoid_blocks_medium_and_above(self) -> None:
        """Paranoid mode should block MEDIUM and above."""
        policy = SecurityPolicy(mode=SecurityMode.PARANOID)

        assert policy.is_blocked_by_mode(RiskLevel.SAFE) is False
        assert policy.is_blocked_by_mode(RiskLevel.LOW) is False
        assert policy.is_blocked_by_mode(RiskLevel.MEDIUM) is True
        assert policy.is_blocked_by_mode(RiskLevel.HIGH) is True

    def test_strict_blocks_high_and_above(self) -> None:
        """Strict mode should block HIGH and above."""
        policy = SecurityPolicy(mode=SecurityMode.STRICT)

        assert policy.is_blocked_by_mode(RiskLevel.SAFE) is False
        assert policy.is_blocked_by_mode(RiskLevel.LOW) is False
        assert policy.is_blocked_by_mode(RiskLevel.MEDIUM) is False
        assert policy.is_blocked_by_mode(RiskLevel.HIGH) is True

    def test_standard_only_blocks_critical(self) -> None:
        """Standard mode should only block CRITICAL."""
        policy = SecurityPolicy(mode=SecurityMode.STANDARD)

        assert policy.is_blocked_by_mode(RiskLevel.SAFE) is False
        assert policy.is_blocked_by_mode(RiskLevel.LOW) is False
        assert policy.is_blocked_by_mode(RiskLevel.MEDIUM) is False
        assert policy.is_blocked_by_mode(RiskLevel.HIGH) is False
        assert policy.is_blocked_by_mode(RiskLevel.CRITICAL) is True

    def test_permissive_only_blocks_critical(self) -> None:
        """Permissive mode should only block CRITICAL."""
        policy = SecurityPolicy(mode=SecurityMode.PERMISSIVE)

        assert policy.is_blocked_by_mode(RiskLevel.HIGH) is False
        assert policy.is_blocked_by_mode(RiskLevel.CRITICAL) is True


class TestSecurityPolicyFactories:
    """Tests for SecurityPolicy factory methods."""

    def test_permissive_factory(self) -> None:
        """Should create permissive policy."""
        policy = SecurityPolicy.permissive()

        assert policy.name == "permissive"
        assert policy.mode == SecurityMode.PERMISSIVE
        assert policy.allow_sudo is True
        assert policy.require_approval_levels == []

    def test_standard_factory(self) -> None:
        """Should create standard policy."""
        policy = SecurityPolicy.standard()

        assert policy.name == "standard"
        assert policy.mode == SecurityMode.STANDARD
        assert policy.allow_sudo is False
        assert RiskLevel.HIGH in policy.require_approval_levels

    def test_strict_factory(self) -> None:
        """Should create strict policy."""
        policy = SecurityPolicy.strict()

        assert policy.name == "strict"
        assert policy.mode == SecurityMode.STRICT
        assert policy.allow_sudo is False
        assert policy.allow_network is False
        assert RiskLevel.MEDIUM in policy.require_approval_levels
        assert RiskLevel.HIGH in policy.require_approval_levels

    def test_paranoid_factory(self) -> None:
        """Should create paranoid policy."""
        policy = SecurityPolicy.paranoid()

        assert policy.name == "paranoid"
        assert policy.mode == SecurityMode.PARANOID
        assert policy.allow_sudo is False
        assert policy.allow_network is False
        assert "/tmp/*" in policy.blocked_paths
        assert "/var/*" in policy.blocked_paths


class TestDevicePolicy:
    """Tests for DevicePolicy dataclass."""

    def test_create(self) -> None:
        """Should create device policy."""
        policy = SecurityPolicy.strict()
        device_policy = DevicePolicy(
            device_id="robot-1",
            policy=policy,
            allowed_commands=["status", "ping"],
            blocked_commands=["reboot"],
        )

        assert device_policy.device_id == "robot-1"
        assert device_policy.policy is policy
        assert "status" in device_policy.allowed_commands
        assert "reboot" in device_policy.blocked_commands

    def test_default_lists(self) -> None:
        """Should have empty default lists."""
        device_policy = DevicePolicy(
            device_id="server-1",
            policy=SecurityPolicy(),
        )

        assert device_policy.allowed_commands == []
        assert device_policy.blocked_commands == []


class TestPolicyManager:
    """Tests for PolicyManager class."""

    def test_default_initialization(self) -> None:
        """Should initialize with standard policy."""
        manager = PolicyManager()

        policy = manager.get_policy()
        assert policy.name == "standard"
        assert policy.mode == SecurityMode.STANDARD

    def test_custom_default_policy(self) -> None:
        """Should use custom default policy."""
        custom = SecurityPolicy.strict()
        manager = PolicyManager(default_policy=custom)

        policy = manager.get_policy()
        assert policy.name == "strict"

    def test_get_policy_without_device(self) -> None:
        """Should return default policy when no device specified."""
        manager = PolicyManager()

        policy = manager.get_policy()
        assert policy is not None

    def test_get_policy_with_unknown_device(self) -> None:
        """Should return default policy for unknown device."""
        manager = PolicyManager()

        policy = manager.get_policy(device_id="unknown")
        assert policy.name == "standard"

    def test_get_policy_with_device(self) -> None:
        """Should return device-specific policy."""
        manager = PolicyManager()
        strict = SecurityPolicy.strict()
        device_policy = DevicePolicy(device_id="robot-1", policy=strict)
        manager.add_device_policy(device_policy)

        policy = manager.get_policy(device_id="robot-1")
        assert policy.name == "strict"

    def test_get_device_policy(self) -> None:
        """Should return full device policy."""
        manager = PolicyManager()
        device_policy = DevicePolicy(
            device_id="robot-1",
            policy=SecurityPolicy.strict(),
            allowed_commands=["status"],
        )
        manager.add_device_policy(device_policy)

        result = manager.get_device_policy("robot-1")
        assert result is not None
        assert result.device_id == "robot-1"
        assert "status" in result.allowed_commands

    def test_get_device_policy_not_found(self) -> None:
        """Should return None for unknown device."""
        manager = PolicyManager()

        result = manager.get_device_policy("unknown")
        assert result is None

    def test_set_default_policy(self) -> None:
        """Should update default policy."""
        manager = PolicyManager()
        new_policy = SecurityPolicy.paranoid()

        manager.set_default_policy(new_policy)

        policy = manager.get_policy()
        assert policy.name == "paranoid"

    def test_add_device_policy(self) -> None:
        """Should add device policy."""
        manager = PolicyManager()
        device_policy = DevicePolicy(
            device_id="server-1",
            policy=SecurityPolicy.strict(),
        )

        manager.add_device_policy(device_policy)

        result = manager.get_device_policy("server-1")
        assert result is not None


class TestPolicyManagerConfigLoading:
    """Tests for PolicyManager config loading."""

    def test_load_config_from_yaml(self, tmp_path: Path) -> None:
        """Should load config from YAML file."""
        config_content = """
default_policy:
  name: loaded
  mode: strict
  allow_sudo: false
  allow_network: false
  require_approval_levels:
    - medium
    - high

devices:
  - id: robot-1
    policy:
      name: robot-policy
      mode: paranoid
    allowed_commands:
      - status
      - ping
"""
        config_file = tmp_path / "policies.yaml"
        config_file.write_text(config_content)

        manager = PolicyManager(config_path=config_file)

        # Check default policy was loaded
        default = manager.get_policy()
        assert default.name == "loaded"
        assert default.mode == SecurityMode.STRICT

        # Check device policy was loaded
        robot_policy = manager.get_policy(device_id="robot-1")
        assert robot_policy.name == "robot-policy"

    def test_load_config_nonexistent_file(self, tmp_path: Path) -> None:
        """Should handle nonexistent config file."""
        manager = PolicyManager(config_path=tmp_path / "missing.yaml")

        # Should use default policy
        policy = manager.get_policy()
        assert policy.name == "standard"

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Should handle empty config file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        manager = PolicyManager(config_path=config_file)

        # Should use default policy
        policy = manager.get_policy()
        assert policy.name == "standard"

    def test_load_config_invalid_yaml(self, tmp_path: Path) -> None:
        """Should handle invalid YAML gracefully."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("not: valid: yaml: {{{{")

        # Should not raise
        manager = PolicyManager(config_path=config_file)

        # Should use default policy
        policy = manager.get_policy()
        assert policy.name == "standard"

    def test_parse_policy_with_all_fields(self) -> None:
        """Should parse policy with all fields."""
        manager = PolicyManager()
        config = {
            "name": "custom",
            "mode": "strict",
            "blocked_patterns": ["rm -rf"],
            "allowed_patterns": ["ls"],
            "require_approval_levels": ["medium", "high"],
            "max_command_length": 5000,
            "allow_sudo": True,
            "allow_network": False,
            "allowed_paths": ["/home/*"],
            "blocked_paths": ["/etc/*"],
            "timeout": 60.0,
        }

        policy = manager._parse_policy(config)

        assert policy.name == "custom"
        assert policy.mode == SecurityMode.STRICT
        assert "rm -rf" in policy.blocked_patterns
        assert policy.max_command_length == 5000
        assert policy.allow_sudo is True
        assert policy.allow_network is False
        assert policy.timeout == 60.0

    def test_parse_policy_with_defaults(self) -> None:
        """Should use defaults for missing fields."""
        manager = PolicyManager()
        policy = manager._parse_policy({})

        assert policy.name == "custom"
        assert policy.mode == SecurityMode.STANDARD
        assert policy.max_command_length == 10000

    def test_parse_policy_invalid_approval_level(self) -> None:
        """Should ignore invalid approval levels."""
        manager = PolicyManager()
        config = {
            "require_approval_levels": ["invalid", "high"],
        }

        policy = manager._parse_policy(config)

        # Only valid level should be in list
        assert RiskLevel.HIGH in policy.require_approval_levels
        assert len(policy.require_approval_levels) == 1


class TestPolicyManagerDevicePolicies:
    """Tests for device policy management."""

    def test_multiple_device_policies(self) -> None:
        """Should manage multiple device policies."""
        manager = PolicyManager()

        manager.add_device_policy(DevicePolicy(
            device_id="robot-1",
            policy=SecurityPolicy.paranoid(),
        ))
        manager.add_device_policy(DevicePolicy(
            device_id="server-1",
            policy=SecurityPolicy.strict(),
        ))

        robot_policy = manager.get_policy(device_id="robot-1")
        server_policy = manager.get_policy(device_id="server-1")

        assert robot_policy.name == "paranoid"
        assert server_policy.name == "strict"

    def test_update_device_policy(self) -> None:
        """Should update existing device policy."""
        manager = PolicyManager()

        manager.add_device_policy(DevicePolicy(
            device_id="robot-1",
            policy=SecurityPolicy.strict(),
        ))

        # Update with new policy
        manager.add_device_policy(DevicePolicy(
            device_id="robot-1",
            policy=SecurityPolicy.paranoid(),
        ))

        policy = manager.get_policy(device_id="robot-1")
        assert policy.name == "paranoid"
