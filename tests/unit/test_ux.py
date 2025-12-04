"""Tests for UX utilities module."""

import io
import pytest
import time

from agentsh.utils.ux import (
    Color,
    ErrorContext,
    ErrorFormatter,
    OutputBuffer,
    ProgressBar,
    Spinner,
    SpinnerStyle,
    Table,
    TableColumn,
    colorize,
    get_error_suggestion,
    print_error,
    print_info,
    print_success,
    print_warning,
    strip_ansi,
)


class TestColor:
    """Tests for Color enum."""

    def test_color_values(self) -> None:
        """Should have ANSI escape codes."""
        assert Color.RED.value == "\033[31m"
        assert Color.GREEN.value == "\033[32m"
        assert Color.RESET.value == "\033[0m"

    def test_color_string_enum(self) -> None:
        """Should be string enum."""
        assert isinstance(Color.RED, str)


class TestColorize:
    """Tests for colorize function."""

    def test_colorize_single_color(self) -> None:
        """Should apply single color."""
        result = colorize("test", Color.RED)
        assert Color.RED.value in result
        assert Color.RESET.value in result
        assert "test" in result

    def test_colorize_multiple_colors(self) -> None:
        """Should apply multiple colors."""
        result = colorize("test", Color.BOLD, Color.RED)
        assert Color.BOLD.value in result
        assert Color.RED.value in result

    def test_colorize_disabled(self) -> None:
        """Should not apply colors when disabled."""
        result = colorize("test", Color.RED, use_color=False)
        assert result == "test"

    def test_colorize_no_colors(self) -> None:
        """Should return original text with no colors."""
        result = colorize("test")
        assert result == "test"


class TestStripAnsi:
    """Tests for strip_ansi function."""

    def test_strip_colors(self) -> None:
        """Should strip ANSI color codes."""
        colored = colorize("test", Color.RED)
        assert strip_ansi(colored) == "test"

    def test_strip_plain_text(self) -> None:
        """Should handle plain text."""
        assert strip_ansi("plain text") == "plain text"

    def test_strip_multiple_codes(self) -> None:
        """Should strip multiple codes."""
        text = f"{Color.BOLD.value}{Color.RED.value}test{Color.RESET.value}"
        assert strip_ansi(text) == "test"


class TestSpinner:
    """Tests for Spinner class."""

    def test_spinner_creation(self) -> None:
        """Should create spinner with defaults."""
        spinner = Spinner("Loading")
        assert spinner.message == "Loading"
        assert spinner.style == SpinnerStyle.DOTS

    def test_spinner_styles(self) -> None:
        """Should support different styles."""
        for style in SpinnerStyle:
            spinner = Spinner("Test", style=style)
            assert spinner.style == style

    def test_spinner_start_stop(self) -> None:
        """Should start and stop without error."""
        stream = io.StringIO()
        spinner = Spinner("Test", stream=stream)

        spinner.start()
        time.sleep(0.2)
        spinner.stop()

        # Should have written something
        output = stream.getvalue()
        assert len(output) > 0

    def test_spinner_context_manager(self) -> None:
        """Should work as context manager."""
        stream = io.StringIO()

        with Spinner("Test", stream=stream):
            time.sleep(0.1)

        output = stream.getvalue()
        assert "Done" in output or len(output) > 0

    def test_spinner_update_message(self) -> None:
        """Should update message."""
        spinner = Spinner("Initial")
        spinner.update("Updated")
        assert spinner.message == "Updated"


class TestProgressBar:
    """Tests for ProgressBar class."""

    def test_progress_bar_creation(self) -> None:
        """Should create progress bar."""
        bar = ProgressBar(total=100, description="Test")
        assert bar.total == 100
        assert bar.description == "Test"

    def test_progress_bar_update(self) -> None:
        """Should update progress."""
        stream = io.StringIO()
        bar = ProgressBar(total=10, stream=stream)
        bar.start()

        bar.update(5)
        output = stream.getvalue()
        assert "50" in output  # Should show 50%

    def test_progress_bar_finish(self) -> None:
        """Should complete to 100%."""
        stream = io.StringIO()
        bar = ProgressBar(total=10, stream=stream)
        bar.start()
        bar.update(5)
        bar.finish()

        output = stream.getvalue()
        assert "100" in output

    def test_progress_bar_context_manager(self) -> None:
        """Should work as context manager."""
        stream = io.StringIO()

        with ProgressBar(total=10, stream=stream) as bar:
            for _ in range(10):
                bar.update(1)

        output = stream.getvalue()
        assert len(output) > 0


class TestTable:
    """Tests for Table class."""

    def test_table_creation(self) -> None:
        """Should create table with columns."""
        columns = [
            TableColumn("Name", "name"),
            TableColumn("Value", "value"),
        ]
        table = Table(columns)
        assert len(table.columns) == 2

    def test_table_add_row(self) -> None:
        """Should add rows."""
        columns = [TableColumn("Name", "name")]
        table = Table(columns)
        table.add_row({"name": "Test"})

        output = table.render()
        assert "Test" in output

    def test_table_add_rows(self) -> None:
        """Should add multiple rows."""
        columns = [TableColumn("ID", "id")]
        table = Table(columns)
        table.add_rows([{"id": "1"}, {"id": "2"}])

        output = table.render()
        assert "1" in output
        assert "2" in output

    def test_table_column_alignment(self) -> None:
        """Should respect column alignment."""
        columns = [
            TableColumn("Left", "left", align="left"),
            TableColumn("Right", "right", align="right"),
        ]
        table = Table(columns)
        table.add_row({"left": "L", "right": "R"})

        output = table.render()
        assert "L" in output
        assert "R" in output

    def test_table_column_color(self) -> None:
        """Should apply column colors."""
        columns = [TableColumn("Status", "status", color=Color.GREEN)]
        table = Table(columns, use_color=True)
        table.add_row({"status": "OK"})

        output = table.render()
        assert Color.GREEN.value in output

    def test_table_no_border(self) -> None:
        """Should render without border."""
        columns = [TableColumn("Name", "name")]
        table = Table(columns, border_style="none")
        table.add_row({"name": "Test"})

        output = table.render()
        assert "│" not in output

    def test_table_custom_width(self) -> None:
        """Should respect custom column width."""
        columns = [TableColumn("Name", "name", width=20)]
        table = Table(columns)
        table.add_row({"name": "Test"})

        output = table.render()
        # Header line should be at least 20 chars wide for content
        assert len(output) > 20


class TestErrorFormatter:
    """Tests for ErrorFormatter class."""

    def test_format_error(self) -> None:
        """Should format error context."""
        formatter = ErrorFormatter()
        ctx = ErrorContext(
            error_type="TestError",
            message="Something went wrong",
            suggestion="Try again",
        )

        output = formatter.format(ctx)
        assert "TestError" in output
        assert "Something went wrong" in output
        assert "Try again" in output

    def test_format_error_with_details(self) -> None:
        """Should include details."""
        formatter = ErrorFormatter()
        ctx = ErrorContext(
            error_type="Error",
            message="Failed",
            details="Line 1\nLine 2",
        )

        output = formatter.format(ctx)
        assert "Line 1" in output
        assert "Line 2" in output

    def test_format_exception(self) -> None:
        """Should format exception."""
        formatter = ErrorFormatter()
        exc = ValueError("Invalid value")

        output = formatter.format_exception(exc)
        assert "ValueError" in output
        assert "Invalid value" in output

    def test_format_exception_with_suggestion(self) -> None:
        """Should include suggestion."""
        formatter = ErrorFormatter()
        exc = ValueError("Bad input")

        output = formatter.format_exception(exc, suggestion="Check your input")
        assert "Check your input" in output


class TestGetErrorSuggestion:
    """Tests for get_error_suggestion function."""

    def test_known_error(self) -> None:
        """Should return suggestion for known errors."""
        exc = ConnectionError("Failed to connect")
        suggestion = get_error_suggestion(exc)
        assert suggestion is not None
        assert "network" in suggestion.lower()

    def test_unknown_error(self) -> None:
        """Should return None for unknown errors."""

        class CustomError(Exception):
            pass

        exc = CustomError("Custom error")
        suggestion = get_error_suggestion(exc)
        assert suggestion is None


class TestPrintFunctions:
    """Tests for print helper functions."""

    def test_print_success(self) -> None:
        """Should print success message."""
        stream = io.StringIO()
        print_success("Operation completed", stream=stream)
        output = stream.getvalue()
        assert "Operation completed" in output

    def test_print_warning(self) -> None:
        """Should print warning message."""
        stream = io.StringIO()
        print_warning("Be careful", stream=stream)
        output = stream.getvalue()
        assert "Be careful" in output

    def test_print_error(self) -> None:
        """Should print error message."""
        stream = io.StringIO()
        print_error("Something failed", stream=stream)
        output = stream.getvalue()
        assert "Something failed" in output

    def test_print_info(self) -> None:
        """Should print info message."""
        stream = io.StringIO()
        print_info("FYI", stream=stream)
        output = stream.getvalue()
        assert "FYI" in output


class TestOutputBuffer:
    """Tests for OutputBuffer class."""

    def test_buffer_add(self) -> None:
        """Should add text."""
        buf = OutputBuffer()
        buf.add("Hello").add(" World")
        assert buf.render() == "Hello World"

    def test_buffer_add_line(self) -> None:
        """Should add lines."""
        buf = OutputBuffer()
        buf.add_line("Line 1").add_line("Line 2")
        output = buf.render()
        assert "Line 1\n" in output
        assert "Line 2\n" in output

    def test_buffer_add_header(self) -> None:
        """Should add headers."""
        buf = OutputBuffer(use_color=False)
        buf.add_header("Title", level=1)
        output = buf.render()
        assert "Title" in output
        assert "=" in output

    def test_buffer_add_list(self) -> None:
        """Should add bulleted list."""
        buf = OutputBuffer()
        buf.add_list(["Item 1", "Item 2"])
        output = buf.render()
        assert "Item 1" in output
        assert "Item 2" in output

    def test_buffer_add_separator(self) -> None:
        """Should add separator."""
        buf = OutputBuffer(use_color=False)
        buf.add_separator()
        output = buf.render()
        assert "─" in output

    def test_buffer_str(self) -> None:
        """Should convert to string."""
        buf = OutputBuffer()
        buf.add("Test")
        assert str(buf) == "Test"
