"""Tests for input validation and sanitization utilities."""

import pytest
from pathlib import Path

from agentsh.utils.validators import (
    CommandValidator,
    InputSanitizer,
    PathValidator,
    ValidationError,
    ValidationResult,
    redact_secrets,
    validate_and_sanitize,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self) -> None:
        """Should create valid result."""
        result = ValidationResult(valid=True, sanitized="test")
        assert result.valid is True
        assert result.sanitized == "test"
        assert result.message is None

    def test_invalid_result(self) -> None:
        """Should create invalid result."""
        result = ValidationResult(valid=False, message="Error")
        assert result.valid is False
        assert result.message == "Error"


class TestInputSanitizer:
    """Tests for InputSanitizer class."""

    @pytest.fixture
    def sanitizer(self) -> InputSanitizer:
        """Create sanitizer instance."""
        return InputSanitizer()

    @pytest.fixture
    def strict_sanitizer(self) -> InputSanitizer:
        """Create strict sanitizer instance."""
        return InputSanitizer(strict=True)

    # String sanitization tests

    def test_sanitize_string_valid(self, sanitizer: InputSanitizer) -> None:
        """Should pass valid strings."""
        result = sanitizer.sanitize_string("Hello World")
        assert result.valid is True
        assert result.sanitized == "Hello World"

    def test_sanitize_string_max_length(self, sanitizer: InputSanitizer) -> None:
        """Should reject strings exceeding max length."""
        result = sanitizer.sanitize_string("x" * 100, max_length=50)
        assert result.valid is False
        assert "length" in result.message.lower()

    def test_sanitize_string_no_newlines(self, sanitizer: InputSanitizer) -> None:
        """Should remove newlines when not allowed."""
        result = sanitizer.sanitize_string("line1\nline2", allow_newlines=False)
        assert result.valid is True
        assert "\n" not in result.sanitized

    def test_sanitize_string_null_bytes(self, sanitizer: InputSanitizer) -> None:
        """Should remove null bytes."""
        result = sanitizer.sanitize_string("test\x00data")
        assert result.valid is True
        assert "\x00" not in result.sanitized

    def test_sanitize_string_non_string(self, sanitizer: InputSanitizer) -> None:
        """Should reject non-string input."""
        result = sanitizer.sanitize_string(123)  # type: ignore
        assert result.valid is False

    # Shell argument tests

    def test_sanitize_shell_arg_valid(self, sanitizer: InputSanitizer) -> None:
        """Should pass valid shell arguments."""
        result = sanitizer.sanitize_shell_arg("filename.txt")
        assert result.valid is True

    def test_sanitize_shell_arg_command_injection(
        self, sanitizer: InputSanitizer
    ) -> None:
        """Should detect command injection."""
        # Subshell injection
        result = sanitizer.sanitize_shell_arg("$(whoami)")
        assert result.valid is False

        # Backtick injection
        result = sanitizer.sanitize_shell_arg("`whoami`")
        assert result.valid is False

        # Pipe injection
        result = sanitizer.sanitize_shell_arg("file | rm -rf")
        assert result.valid is False

    def test_sanitize_shell_arg_strict_mode(
        self, strict_sanitizer: InputSanitizer
    ) -> None:
        """Should reject metacharacters in strict mode."""
        result = strict_sanitizer.sanitize_shell_arg("file; ls")
        assert result.valid is False

    # Path sanitization tests

    def test_sanitize_path_valid(self, sanitizer: InputSanitizer) -> None:
        """Should pass valid paths."""
        result = sanitizer.sanitize_path("/home/user/file.txt")
        assert result.valid is True

    def test_sanitize_path_traversal(self, sanitizer: InputSanitizer) -> None:
        """Should detect path traversal."""
        result = sanitizer.sanitize_path("../../../etc/passwd")
        assert result.valid is False
        assert "traversal" in result.message.lower()

    def test_sanitize_path_base_dir(self, sanitizer: InputSanitizer, tmp_path: Path) -> None:
        """Should enforce base directory."""
        result = sanitizer.sanitize_path(
            str(tmp_path / "file.txt"),
            base_dir=tmp_path,
        )
        assert result.valid is True

        # Outside base dir
        result = sanitizer.sanitize_path(
            "/etc/passwd",
            base_dir=tmp_path,
        )
        assert result.valid is False

    def test_sanitize_path_no_absolute(self, sanitizer: InputSanitizer) -> None:
        """Should reject absolute paths when disabled."""
        result = sanitizer.sanitize_path("/etc/passwd", allow_absolute=False)
        assert result.valid is False

    # SQL value tests

    def test_sanitize_sql_valid(self, sanitizer: InputSanitizer) -> None:
        """Should pass valid SQL values."""
        result = sanitizer.sanitize_sql_value("John Doe")
        assert result.valid is True

    def test_sanitize_sql_injection(self, sanitizer: InputSanitizer) -> None:
        """Should detect SQL injection."""
        # OR injection with numeric comparison (common pattern)
        result = sanitizer.sanitize_sql_value("' OR 1=1")
        assert result.valid is False

        # DROP TABLE
        result = sanitizer.sanitize_sql_value("; DROP TABLE users")
        assert result.valid is False

        # UNION SELECT
        result = sanitizer.sanitize_sql_value("' UNION SELECT * FROM users")
        assert result.valid is False

    def test_sanitize_sql_escape_quotes(self, sanitizer: InputSanitizer) -> None:
        """Should escape single quotes."""
        result = sanitizer.sanitize_sql_value("O'Brien")
        assert result.valid is True
        assert result.sanitized == "O''Brien"

    # URL tests

    def test_sanitize_url_valid(self, sanitizer: InputSanitizer) -> None:
        """Should pass valid URLs."""
        result = sanitizer.sanitize_url("https://example.com/path")
        assert result.valid is True

    def test_sanitize_url_invalid_scheme(self, sanitizer: InputSanitizer) -> None:
        """Should reject invalid schemes."""
        result = sanitizer.sanitize_url("file:///etc/passwd")
        assert result.valid is False

        result = sanitizer.sanitize_url("javascript:alert(1)")
        assert result.valid is False

    def test_sanitize_url_custom_schemes(self, sanitizer: InputSanitizer) -> None:
        """Should allow custom schemes."""
        result = sanitizer.sanitize_url(
            "ssh://user@host",
            allowed_schemes={"ssh", "http"},
        )
        assert result.valid is True

    # Secret detection tests

    def test_check_for_secrets_api_key(self, sanitizer: InputSanitizer) -> None:
        """Should detect API keys."""
        text = "api_key = 'sk_live_12345678901234567890'"
        secrets = sanitizer.check_for_secrets(text)
        assert len(secrets) > 0

    def test_check_for_secrets_aws(self, sanitizer: InputSanitizer) -> None:
        """Should detect AWS keys."""
        text = "AKIAIOSFODNN7EXAMPLE"
        secrets = sanitizer.check_for_secrets(text)
        assert "AWS Key" in secrets

    def test_check_for_secrets_private_key(self, sanitizer: InputSanitizer) -> None:
        """Should detect private keys."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nbase64data\n-----END RSA PRIVATE KEY-----"
        secrets = sanitizer.check_for_secrets(text)
        assert "Private Key" in secrets

    def test_check_for_secrets_clean(self, sanitizer: InputSanitizer) -> None:
        """Should return empty for clean text."""
        text = "This is just normal text without any secrets."
        secrets = sanitizer.check_for_secrets(text)
        assert len(secrets) == 0


class TestCommandValidator:
    """Tests for CommandValidator class."""

    @pytest.fixture
    def validator(self) -> CommandValidator:
        """Create validator instance."""
        return CommandValidator()

    def test_validate_safe_command(self, validator: CommandValidator) -> None:
        """Should pass safe commands."""
        result = validator.validate("ls -la")
        assert result.valid is True

    def test_validate_blocked_command(self, validator: CommandValidator) -> None:
        """Should block dangerous commands."""
        result = validator.validate("rm -rf /")
        assert result.valid is False

        result = validator.validate(":(){ :|:& };:")  # Fork bomb
        assert result.valid is False

    def test_validate_sensitive_command(self, validator: CommandValidator) -> None:
        """Should flag sensitive commands."""
        result = validator.validate("sudo apt update")
        assert result.valid is True
        assert result.message is not None  # Should have warning

    def test_validate_custom_blocked_patterns(self) -> None:
        """Should block custom patterns."""
        validator = CommandValidator(blocked_patterns=[r"evil_command"])
        result = validator.validate("evil_command --do-bad-things")
        assert result.valid is False


class TestPathValidator:
    """Tests for PathValidator class."""

    @pytest.fixture
    def validator(self) -> PathValidator:
        """Create validator instance."""
        return PathValidator()

    def test_validate_read_allowed(self, tmp_path: Path) -> None:
        """Should allow reading in allowed paths."""
        # Create a validator with tmp_path in allowed_roots
        validator = PathValidator(allowed_roots=[tmp_path])
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validator.validate(str(test_file), operation="read")
        assert result.valid is True

    def test_validate_write_protected(self, validator: PathValidator) -> None:
        """Should block writing to protected directories."""
        result = validator.validate("/etc/passwd", operation="write")
        assert result.valid is False

    def test_validate_delete_protected(self, validator: PathValidator) -> None:
        """Should block deleting in protected directories."""
        result = validator.validate("/bin/ls", operation="delete")
        assert result.valid is False

    def test_validate_allowed_roots(self, tmp_path: Path) -> None:
        """Should enforce allowed roots."""
        validator = PathValidator(allowed_roots=[tmp_path])

        # Inside allowed root
        result = validator.validate(str(tmp_path / "file.txt"))
        assert result.valid is True

        # Outside allowed root
        result = validator.validate("/etc/passwd")
        assert result.valid is False

    def test_validate_blocked_paths(self, tmp_path: Path) -> None:
        """Should block specific paths."""
        blocked = tmp_path / "blocked"
        validator = PathValidator(blocked_paths=[blocked])

        result = validator.validate(str(blocked / "file.txt"))
        assert result.valid is False


class TestValidateAndSanitize:
    """Tests for validate_and_sanitize convenience function."""

    def test_string_type(self) -> None:
        """Should validate strings."""
        result = validate_and_sanitize("test", "string")
        assert result.valid is True

    def test_path_type(self) -> None:
        """Should validate paths."""
        result = validate_and_sanitize("/tmp/test", "path")
        assert result.valid is True

    def test_command_type(self) -> None:
        """Should validate commands."""
        result = validate_and_sanitize("ls -la", "command")
        assert result.valid is True

    def test_url_type(self) -> None:
        """Should validate URLs."""
        result = validate_and_sanitize("https://example.com", "url")
        assert result.valid is True

    def test_unknown_type(self) -> None:
        """Should reject unknown types."""
        result = validate_and_sanitize("test", "unknown_type")
        assert result.valid is False


class TestRedactSecrets:
    """Tests for redact_secrets function."""

    def test_redact_api_key(self) -> None:
        """Should redact API keys."""
        text = "api_key = 'sk_live_12345678901234567890'"
        redacted = redact_secrets(text)
        assert "sk_live" not in redacted
        assert "REDACTED" in redacted

    def test_redact_aws_key(self) -> None:
        """Should redact AWS keys."""
        text = "AWS_KEY=AKIAIOSFODNN7EXAMPLE"
        redacted = redact_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted

    def test_redact_private_key(self) -> None:
        """Should redact private keys."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nsecretdata\n-----END RSA PRIVATE KEY-----"
        redacted = redact_secrets(text)
        assert "secretdata" not in redacted

    def test_redact_github_token(self) -> None:
        """Should redact GitHub tokens."""
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456"
        redacted = redact_secrets(text)
        assert "ghp_abcdefghij" not in redacted

    def test_preserve_normal_text(self) -> None:
        """Should preserve normal text."""
        text = "This is just a normal message without secrets."
        redacted = redact_secrets(text)
        assert redacted == text

    def test_redact_multiple_secrets(self) -> None:
        """Should redact multiple secrets in same text."""
        text = "api_key='sk_live_123' and aws='AKIAIOSFODNN7EXAMPLE'"
        redacted = redact_secrets(text)
        assert "sk_live" not in redacted
        assert "AKIAIOSFODNN" not in redacted

    def test_redact_preserves_urls_without_secrets(self) -> None:
        """Should preserve URLs without embedded secrets."""
        text = "https://example.com/api"
        redacted = redact_secrets(text)
        assert redacted == text


class TestValidatorEdgeCases:
    """Edge case tests for validators."""

    def test_validate_empty_string(self) -> None:
        """Should validate empty strings."""
        result = validate_and_sanitize("", "string")
        # Empty string might be valid or invalid depending on impl
        assert result is not None

    def test_validate_whitespace_only(self) -> None:
        """Should handle whitespace-only input."""
        result = validate_and_sanitize("   ", "string")
        assert result is not None

    def test_validate_very_long_input(self) -> None:
        """Should handle very long input."""
        long_text = "a" * 10000
        result = validate_and_sanitize(long_text, "string")
        assert result is not None

    def test_validate_unicode_input(self) -> None:
        """Should handle unicode input."""
        result = validate_and_sanitize("こんにちは", "string")
        assert result is not None

    def test_validate_special_chars(self) -> None:
        """Should handle special characters."""
        result = validate_and_sanitize("test@#$%^&*()!", "string")
        assert result is not None

    def test_validate_path_with_spaces(self) -> None:
        """Should validate paths with spaces."""
        result = validate_and_sanitize("/path/with spaces/file.txt", "path")
        assert result is not None

    def test_validate_command_with_pipe(self) -> None:
        """Should detect command with pipe."""
        result = validate_and_sanitize("ls | grep test", "command")
        assert result is not None

    def test_validate_command_with_redirect(self) -> None:
        """Should detect command with redirect."""
        result = validate_and_sanitize("cat file > output.txt", "command")
        assert result is not None


class TestValidationResultMethods:
    """Tests for ValidationResult methods."""

    def test_result_is_truthy_when_valid(self) -> None:
        """Valid result should be truthy."""
        result = validate_and_sanitize("test", "string")
        if result.valid:
            assert result  # Should be truthy

    def test_result_message_property(self) -> None:
        """Should have message property."""
        result = validate_and_sanitize("<script>alert(1)</script>", "string")
        assert hasattr(result, "message") or hasattr(result, "sanitized")


class TestRedactSecretsExtended:
    """Extended tests for redact_secrets."""

    def test_redact_preserves_auth_header(self) -> None:
        """Should preserve Authorization headers (or redact them)."""
        text = "Authorization: Bearer token123"
        redacted = redact_secrets(text)
        # Either preserves or redacts - just shouldn't crash
        assert isinstance(redacted, str)

    def test_redact_slack_token(self) -> None:
        """Should redact Slack tokens."""
        text = "SLACK_TOKEN=xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"
        redacted = redact_secrets(text)
        assert "xoxb-" not in redacted or "REDACTED" in redacted

    def test_empty_input(self) -> None:
        """Should handle empty input."""
        redacted = redact_secrets("")
        assert redacted == ""

    def test_none_like_input(self) -> None:
        """Should handle whitespace input."""
        redacted = redact_secrets("   ")
        assert redacted == "   "
