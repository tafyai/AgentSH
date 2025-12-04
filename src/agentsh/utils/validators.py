"""Input validation and sanitization utilities.

Provides security-focused validation for user input, paths,
commands, and other data entering the system.
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Pattern
from urllib.parse import urlparse

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
        """
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        valid: Whether validation passed
        message: Error message if invalid
        sanitized: Sanitized value (if applicable)
    """

    valid: bool
    message: Optional[str] = None
    sanitized: Optional[Any] = None


class InputSanitizer:
    """Sanitize user input to prevent injection attacks.

    Provides methods to clean and validate various types of input
    that could be used in injection attacks.
    """

    # Dangerous shell characters
    SHELL_METACHARACTERS = set(';&|`$(){}[]<>\\"\'\n\r\t')

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('|\")\s*(OR|AND)\s*('|\")?\s*\d+\s*=\s*\d+",
        r"--\s*$",
        r";\s*DROP\s+TABLE",
        r";\s*DELETE\s+FROM",
        r";\s*INSERT\s+INTO",
        r";\s*UPDATE\s+.*\s+SET",
        r"UNION\s+SELECT",
        r"INTO\s+OUTFILE",
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"\$\([^)]+\)",  # $(command)
        r"`[^`]+`",  # `command`
        r"\|\s*\w+",  # | command
        r";\s*\w+",  # ; command
        r"&&\s*\w+",  # && command
        r"\|\|\s*\w+",  # || command
        r">\s*[\w/]+",  # > file
        r"<\s*[\w/]+",  # < file
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # ../
        r"\.\.\\",  # ..\
        r"\.\.$",  # ends with ..
        r"^/etc/",  # /etc/
        r"^/proc/",  # /proc/
        r"^/sys/",  # /sys/
        r"^/dev/",  # /dev/
    ]

    def __init__(self, strict: bool = False) -> None:
        """Initialize sanitizer.

        Args:
            strict: Use strict mode (reject more inputs)
        """
        self.strict = strict
        self._sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._cmd_patterns = [re.compile(p) for p in self.COMMAND_INJECTION_PATTERNS]
        self._path_patterns = [re.compile(p) for p in self.PATH_TRAVERSAL_PATTERNS]

    def sanitize_string(
        self,
        value: str,
        max_length: int = 10000,
        allow_newlines: bool = True,
        allow_unicode: bool = True,
    ) -> ValidationResult:
        """Sanitize a general string input.

        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            allow_newlines: Whether to allow newlines
            allow_unicode: Whether to allow non-ASCII characters

        Returns:
            ValidationResult with sanitized string
        """
        if not isinstance(value, str):
            return ValidationResult(False, "Value must be a string")

        # Check length
        if len(value) > max_length:
            return ValidationResult(False, f"String exceeds maximum length of {max_length}")

        sanitized = value

        # Normalize unicode
        if allow_unicode:
            sanitized = unicodedata.normalize("NFC", sanitized)
        else:
            # Remove non-ASCII
            sanitized = sanitized.encode("ascii", "ignore").decode("ascii")

        # Handle newlines
        if not allow_newlines:
            sanitized = sanitized.replace("\n", " ").replace("\r", " ")

        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")

        # Remove control characters (except newline/tab if allowed)
        allowed_controls = {"\n", "\r", "\t"} if allow_newlines else set()
        sanitized = "".join(
            c for c in sanitized
            if not unicodedata.category(c).startswith("C") or c in allowed_controls
        )

        return ValidationResult(True, sanitized=sanitized)

    def sanitize_shell_arg(self, value: str) -> ValidationResult:
        """Sanitize a value for use as a shell argument.

        This is for values that will be passed to shell commands.
        Use proper shell escaping in addition to this.

        Args:
            value: Value to sanitize

        Returns:
            ValidationResult with sanitized value
        """
        if not isinstance(value, str):
            return ValidationResult(False, "Value must be a string")

        # Check for shell metacharacters in strict mode
        if self.strict:
            dangerous = set(value) & self.SHELL_METACHARACTERS
            if dangerous:
                return ValidationResult(
                    False,
                    f"Input contains dangerous characters: {dangerous}",
                )

        # Check for command injection patterns
        for pattern in self._cmd_patterns:
            if pattern.search(value):
                return ValidationResult(
                    False,
                    "Input contains potential command injection",
                )

        # Escape shell metacharacters
        # Use shlex.quote for actual shell usage
        sanitized = value
        for char in self.SHELL_METACHARACTERS:
            if char in sanitized:
                sanitized = sanitized.replace(char, f"\\{char}")

        return ValidationResult(True, sanitized=sanitized)

    def sanitize_path(
        self,
        value: str,
        base_dir: Optional[Path] = None,
        allow_absolute: bool = True,
    ) -> ValidationResult:
        """Sanitize a file path.

        Args:
            value: Path string to sanitize
            base_dir: Base directory to constrain paths to
            allow_absolute: Whether to allow absolute paths

        Returns:
            ValidationResult with sanitized path
        """
        if not isinstance(value, str):
            return ValidationResult(False, "Path must be a string")

        # Check for path traversal
        for pattern in self._path_patterns:
            if pattern.search(value):
                return ValidationResult(
                    False,
                    "Path contains potential traversal attack",
                )

        # Normalize the path
        try:
            path = Path(value).resolve()
        except (ValueError, OSError) as e:
            return ValidationResult(False, f"Invalid path: {e}")

        # Check if absolute paths are allowed
        if not allow_absolute and path.is_absolute():
            return ValidationResult(False, "Absolute paths are not allowed")

        # Check if within base directory
        if base_dir:
            base = base_dir.resolve()
            try:
                path.relative_to(base)
            except ValueError:
                return ValidationResult(
                    False,
                    f"Path must be within {base_dir}",
                )

        return ValidationResult(True, sanitized=str(path))

    def sanitize_sql_value(self, value: str) -> ValidationResult:
        """Sanitize a value for SQL queries.

        Note: Always use parameterized queries instead of string
        interpolation. This is a defense-in-depth measure.

        Args:
            value: Value to sanitize

        Returns:
            ValidationResult with sanitized value
        """
        if not isinstance(value, str):
            return ValidationResult(False, "Value must be a string")

        # Check for SQL injection patterns
        for pattern in self._sql_patterns:
            if pattern.search(value):
                return ValidationResult(
                    False,
                    "Input contains potential SQL injection",
                )

        # Escape single quotes
        sanitized = value.replace("'", "''")

        return ValidationResult(True, sanitized=sanitized)

    def sanitize_url(
        self,
        value: str,
        allowed_schemes: Optional[set[str]] = None,
    ) -> ValidationResult:
        """Sanitize a URL.

        Args:
            value: URL to sanitize
            allowed_schemes: Set of allowed URL schemes

        Returns:
            ValidationResult with sanitized URL
        """
        if not isinstance(value, str):
            return ValidationResult(False, "URL must be a string")

        if allowed_schemes is None:
            allowed_schemes = {"http", "https"}

        try:
            parsed = urlparse(value)
        except ValueError as e:
            return ValidationResult(False, f"Invalid URL: {e}")

        # Check scheme
        if parsed.scheme.lower() not in allowed_schemes:
            return ValidationResult(
                False,
                f"URL scheme must be one of: {allowed_schemes}",
            )

        # Check for dangerous characters in hostname
        if parsed.hostname:
            # Remove any control characters
            clean_host = "".join(
                c for c in parsed.hostname
                if not unicodedata.category(c).startswith("C")
            )
            if clean_host != parsed.hostname:
                return ValidationResult(
                    False,
                    "URL hostname contains invalid characters",
                )

        return ValidationResult(True, sanitized=value)

    def check_for_secrets(self, value: str) -> list[str]:
        """Check if a string appears to contain secrets.

        Args:
            value: String to check

        Returns:
            List of potential secret types found
        """
        secrets_found = []

        # Common secret patterns
        patterns = {
            "API Key": r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?[\w-]{20,}",
            "AWS Key": r"(?i)AKIA[0-9A-Z]{16}",
            "AWS Secret": r"(?i)aws[_-]?secret[_-]?access[_-]?key",
            "Private Key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            "Password": r"(?i)(password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?[^\s]{8,}",
            "Token": r"(?i)(token|bearer)['\"]?\s*[:=]\s*['\"]?[\w-]{20,}",
            "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36}",
            "Slack Token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}",
        }

        for secret_type, pattern in patterns.items():
            if re.search(pattern, value):
                secrets_found.append(secret_type)

        return secrets_found


class CommandValidator:
    """Validate shell commands for safety."""

    # Dangerous commands that should be blocked
    BLOCKED_COMMANDS = {
        # Destructive
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf .",
        # System modification
        "mkfs",
        "dd if=/dev/zero",
        "dd if=/dev/random",
        # Fork bombs
        ":(){ :|:& };:",
        # Password/shadow access
        "cat /etc/shadow",
        "cat /etc/passwd",
    }

    # Commands that need careful review
    SENSITIVE_COMMANDS = {
        "sudo",
        "su",
        "chmod",
        "chown",
        "chgrp",
        "rm",
        "mv",
        "cp",
        "dd",
        "mkfs",
        "mount",
        "umount",
        "kill",
        "killall",
        "reboot",
        "shutdown",
        "halt",
        "poweroff",
        "systemctl",
        "service",
        "useradd",
        "userdel",
        "usermod",
        "passwd",
        "visudo",
        "crontab",
    }

    def __init__(self, blocked_patterns: Optional[list[str]] = None) -> None:
        """Initialize validator.

        Args:
            blocked_patterns: Additional patterns to block
        """
        self.blocked_patterns = blocked_patterns or []
        self._blocked_re = [re.compile(p) for p in self.blocked_patterns]

    def validate(self, command: str) -> ValidationResult:
        """Validate a command for safety.

        Args:
            command: Command string to validate

        Returns:
            ValidationResult indicating safety
        """
        # Check exact blocked commands
        if command.strip() in self.BLOCKED_COMMANDS:
            return ValidationResult(False, "Command is blocked for safety")

        # Check blocked patterns
        for pattern in self._blocked_re:
            if pattern.search(command):
                return ValidationResult(False, "Command matches blocked pattern")

        # Check for dangerous patterns
        sanitizer = InputSanitizer()

        # Check for command injection in arguments
        parts = command.split()
        for i, part in enumerate(parts[1:], 1):  # Skip the command itself
            result = sanitizer.sanitize_shell_arg(part)
            if not result.valid:
                return ValidationResult(False, f"Argument {i} is invalid: {result.message}")

        # Check for sensitive commands
        if parts:
            cmd = parts[0]
            if cmd in self.SENSITIVE_COMMANDS:
                return ValidationResult(
                    True,
                    message=f"Command '{cmd}' requires careful review",
                    sanitized=command,
                )

        return ValidationResult(True, sanitized=command)


class PathValidator:
    """Validate file paths for safety."""

    # Sensitive directories that shouldn't be modified
    PROTECTED_DIRS = {
        "/",
        "/bin",
        "/sbin",
        "/usr/bin",
        "/usr/sbin",
        "/etc",
        "/boot",
        "/sys",
        "/proc",
        "/dev",
        "/root",
    }

    def __init__(
        self,
        allowed_roots: Optional[list[Path]] = None,
        blocked_paths: Optional[list[Path]] = None,
    ) -> None:
        """Initialize validator.

        Args:
            allowed_roots: Paths that operations are allowed under
            blocked_paths: Paths that are always blocked
        """
        self.allowed_roots = allowed_roots or [Path.home(), Path.cwd()]
        self.blocked_paths = blocked_paths or []

    def validate(
        self,
        path: str,
        operation: str = "read",
    ) -> ValidationResult:
        """Validate a path for an operation.

        Args:
            path: Path to validate
            operation: Operation type (read, write, delete)

        Returns:
            ValidationResult indicating safety
        """
        try:
            resolved = Path(path).resolve()
        except (ValueError, OSError) as e:
            return ValidationResult(False, f"Invalid path: {e}")

        # Check blocked paths
        for blocked in self.blocked_paths:
            if resolved == blocked.resolve() or blocked.resolve() in resolved.parents:
                return ValidationResult(False, f"Access to {blocked} is blocked")

        # Check protected directories for write/delete
        if operation in ("write", "delete"):
            str_path = str(resolved)
            for protected in self.PROTECTED_DIRS:
                if str_path == protected or str_path.startswith(f"{protected}/"):
                    return ValidationResult(
                        False,
                        f"Cannot {operation} in protected directory: {protected}",
                    )

        # Check allowed roots
        if self.allowed_roots:
            in_allowed = False
            for root in self.allowed_roots:
                try:
                    resolved.relative_to(root.resolve())
                    in_allowed = True
                    break
                except ValueError:
                    continue

            if not in_allowed:
                return ValidationResult(
                    False,
                    "Path is outside allowed directories",
                )

        return ValidationResult(True, sanitized=str(resolved))


def validate_and_sanitize(
    value: Any,
    value_type: str,
    **kwargs: Any,
) -> ValidationResult:
    """Convenience function for validation and sanitization.

    Args:
        value: Value to validate
        value_type: Type of validation (string, path, command, url, shell_arg)
        **kwargs: Additional arguments for the validator

    Returns:
        ValidationResult
    """
    sanitizer = InputSanitizer()

    if value_type == "string":
        return sanitizer.sanitize_string(value, **kwargs)
    elif value_type == "path":
        return sanitizer.sanitize_path(value, **kwargs)
    elif value_type == "shell_arg":
        return sanitizer.sanitize_shell_arg(value)
    elif value_type == "sql":
        return sanitizer.sanitize_sql_value(value)
    elif value_type == "url":
        return sanitizer.sanitize_url(value, **kwargs)
    elif value_type == "command":
        validator = CommandValidator()
        return validator.validate(value)
    else:
        return ValidationResult(False, f"Unknown validation type: {value_type}")


def redact_secrets(text: str, replacement: str = "***REDACTED***") -> str:
    """Redact potential secrets from text.

    Args:
        text: Text to redact
        replacement: Replacement string for secrets

    Returns:
        Text with secrets redacted
    """
    patterns = [
        # API keys and tokens
        (r'(?i)(api[_-]?key|apikey|token|bearer|secret|password|passwd|pwd)[\'"]?\s*[:=]\s*[\'"]?([^\s\'"]{8,})', r'\1=***REDACTED***'),
        # AWS keys
        (r'AKIA[0-9A-Z]{16}', replacement),
        # Private keys
        (r'-----BEGIN[^-]+PRIVATE KEY-----[\s\S]*?-----END[^-]+PRIVATE KEY-----', replacement),
        # GitHub tokens
        (r'gh[pousr]_[A-Za-z0-9_]{36}', replacement),
        # Generic long hex strings (potential secrets)
        (r'(?<![a-zA-Z0-9])[a-f0-9]{32,}(?![a-zA-Z0-9])', replacement),
    ]

    result = text
    for pattern, repl in patterns:
        result = re.sub(pattern, repl, result)

    return result
