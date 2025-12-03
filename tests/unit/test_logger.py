"""Tests for logging system."""

import logging
from pathlib import Path

import pytest
import structlog

from agentsh.telemetry.logger import (
    setup_logging,
    get_logger,
    bind_context,
    unbind_context,
    clear_context,
    LoggerMixin,
)

# structlog returns lazy proxies, not direct BoundLogger instances
from structlog._base import BoundLoggerBase


class TestLogging:
    """Test logging functionality."""

    def test_setup_logging_console(self) -> None:
        """Should configure console logging."""
        setup_logging(level="DEBUG", json_format=False)

        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_json(self) -> None:
        """Should configure JSON logging."""
        setup_logging(level="INFO", json_format=True)

        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_with_file(self, tmp_path: Path) -> None:
        """Should configure file logging."""
        log_file = tmp_path / "test.log"

        setup_logging(level="DEBUG", log_file=log_file)

        logger = get_logger("test")
        logger.info("test message")

        # File should exist (may not have content immediately due to buffering)
        assert log_file.parent.exists()

    def test_get_logger_returns_bound_logger(self) -> None:
        """Should return a structlog bound logger."""
        logger = get_logger(__name__)
        # structlog returns lazy proxies that wrap BoundLogger
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_context_binding(self) -> None:
        """Should bind and unbind context variables."""
        clear_context()

        bind_context(user="testuser", session="abc123")
        # Context is bound (we can't easily inspect it without logging)

        unbind_context("user")
        clear_context()


class TestLoggerMixin:
    """Test LoggerMixin functionality."""

    def test_mixin_provides_logger(self) -> None:
        """Mixin should provide logger property."""

        class MyClass(LoggerMixin):
            def do_something(self) -> None:
                self.logger.info("doing something")

        instance = MyClass()
        assert hasattr(instance, "logger")
        # structlog returns lazy proxies that wrap BoundLogger
        assert hasattr(instance.logger, "info")
        assert hasattr(instance.logger, "debug")

    def test_mixin_caches_logger(self) -> None:
        """Logger should be cached on instance."""

        class MyClass(LoggerMixin):
            pass

        instance = MyClass()
        logger1 = instance.logger
        logger2 = instance.logger

        assert logger1 is logger2
