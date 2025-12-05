"""Tests for environment utilities."""

import os
from unittest.mock import patch

import pytest

from agentsh.utils.env import (
    get_env,
    get_env_bool,
    get_env_int,
    get_env_or_fail,
)


class TestGetEnv:
    """Tests for get_env function."""

    def test_get_existing_env(self) -> None:
        """Should get existing environment variable."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = get_env("TEST_VAR")
            assert result == "test_value"

    def test_get_missing_env_returns_none(self) -> None:
        """Should return None for missing variable."""
        result = get_env("NONEXISTENT_VAR_12345")
        assert result is None

    def test_get_missing_env_with_default(self) -> None:
        """Should return default for missing variable."""
        result = get_env("NONEXISTENT_VAR_12345", "default")
        assert result == "default"

    def test_get_env_empty_string(self) -> None:
        """Should return empty string if set to empty."""
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            result = get_env("EMPTY_VAR", "default")
            assert result == ""


class TestGetEnvOrFail:
    """Tests for get_env_or_fail function."""

    def test_get_existing_env(self) -> None:
        """Should get existing environment variable."""
        with patch.dict(os.environ, {"REQUIRED_VAR": "required_value"}):
            result = get_env_or_fail("REQUIRED_VAR")
            assert result == "required_value"

    def test_fail_on_missing_env(self) -> None:
        """Should raise EnvironmentError for missing variable."""
        with pytest.raises(EnvironmentError) as exc_info:
            get_env_or_fail("NONEXISTENT_VAR_12345")

        assert "NONEXISTENT_VAR_12345" in str(exc_info.value)
        assert "not set" in str(exc_info.value)


class TestGetEnvBool:
    """Tests for get_env_bool function."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("Yes", True),
            ("YES", True),
            ("1", True),
            ("on", True),
            ("On", True),
            ("ON", True),
        ],
    )
    def test_truthy_values(self, value: str, expected: bool) -> None:
        """Should recognize truthy values."""
        with patch.dict(os.environ, {"BOOL_VAR": value}):
            result = get_env_bool("BOOL_VAR")
            assert result == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("no", False),
            ("No", False),
            ("NO", False),
            ("0", False),
            ("off", False),
            ("Off", False),
            ("OFF", False),
            ("random", False),
            ("", False),
        ],
    )
    def test_falsy_values(self, value: str, expected: bool) -> None:
        """Should recognize falsy values."""
        with patch.dict(os.environ, {"BOOL_VAR": value}):
            result = get_env_bool("BOOL_VAR")
            assert result == expected

    def test_missing_returns_default_false(self) -> None:
        """Should return False by default for missing variable."""
        result = get_env_bool("NONEXISTENT_VAR_12345")
        assert result is False

    def test_missing_returns_custom_default(self) -> None:
        """Should return custom default for missing variable."""
        result = get_env_bool("NONEXISTENT_VAR_12345", default=True)
        assert result is True


class TestGetEnvInt:
    """Tests for get_env_int function."""

    def test_valid_integer(self) -> None:
        """Should parse valid integer."""
        with patch.dict(os.environ, {"INT_VAR": "42"}):
            result = get_env_int("INT_VAR")
            assert result == 42

    def test_negative_integer(self) -> None:
        """Should parse negative integer."""
        with patch.dict(os.environ, {"INT_VAR": "-10"}):
            result = get_env_int("INT_VAR")
            assert result == -10

    def test_zero(self) -> None:
        """Should parse zero."""
        with patch.dict(os.environ, {"INT_VAR": "0"}):
            result = get_env_int("INT_VAR")
            assert result == 0

    def test_invalid_returns_default(self) -> None:
        """Should return default for invalid value."""
        with patch.dict(os.environ, {"INT_VAR": "not_a_number"}):
            result = get_env_int("INT_VAR", default=99)
            assert result == 99

    def test_float_returns_default(self) -> None:
        """Should return default for float value."""
        with patch.dict(os.environ, {"INT_VAR": "3.14"}):
            result = get_env_int("INT_VAR", default=0)
            assert result == 0

    def test_missing_returns_default_zero(self) -> None:
        """Should return 0 by default for missing variable."""
        result = get_env_int("NONEXISTENT_VAR_12345")
        assert result == 0

    def test_missing_returns_custom_default(self) -> None:
        """Should return custom default for missing variable."""
        result = get_env_int("NONEXISTENT_VAR_12345", default=100)
        assert result == 100

    def test_empty_string_returns_default(self) -> None:
        """Should return default for empty string."""
        with patch.dict(os.environ, {"INT_VAR": ""}):
            result = get_env_int("INT_VAR", default=50)
            assert result == 50
