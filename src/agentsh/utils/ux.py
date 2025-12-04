"""UX utilities for AgentSH.

Provides user experience enhancements including:
- Progress indicators and spinners
- Output formatting with colors and tables
- Markdown rendering for terminal
- User-friendly error messages
"""

import asyncio
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generator, Iterator, Optional, TextIO


class Color(str, Enum):
    """ANSI color codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def colorize(text: str, *colors: Color, use_color: bool = True) -> str:
    """Apply ANSI colors to text.

    Args:
        text: Text to colorize
        *colors: Colors to apply
        use_color: Whether to actually apply colors

    Returns:
        Colorized text string
    """
    if not use_color or not colors:
        return text
    color_codes = "".join(c.value for c in colors)
    return f"{color_codes}{text}{Color.RESET.value}"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Text with potential ANSI codes

    Returns:
        Plain text without ANSI codes
    """
    import re

    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class SpinnerStyle(str, Enum):
    """Spinner animation styles."""

    DOTS = "dots"
    LINE = "line"
    ARROWS = "arrows"
    BOUNCE = "bounce"
    BRAILLE = "braille"


SPINNER_FRAMES = {
    SpinnerStyle.DOTS: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    SpinnerStyle.LINE: ["-", "\\", "|", "/"],
    SpinnerStyle.ARROWS: ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    SpinnerStyle.BOUNCE: ["⠁", "⠂", "⠄", "⠂"],
    SpinnerStyle.BRAILLE: ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
}


class Spinner:
    """Animated spinner for indicating progress.

    Example:
        with Spinner("Loading..."):
            time.sleep(2)

        # Or manual control:
        spinner = Spinner("Processing")
        spinner.start()
        # ... do work ...
        spinner.stop()
    """

    def __init__(
        self,
        message: str = "",
        style: SpinnerStyle = SpinnerStyle.DOTS,
        stream: TextIO = sys.stderr,
        use_color: bool = True,
    ) -> None:
        """Initialize spinner.

        Args:
            message: Message to display alongside spinner
            style: Spinner animation style
            stream: Output stream
            use_color: Whether to use colors
        """
        self.message = message
        self.style = style
        self.stream = stream
        self.use_color = use_color

        self._frames = SPINNER_FRAMES[style]
        self._frame_idx = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = 0.1  # 100ms per frame

    def start(self) -> "Spinner":
        """Start the spinner animation."""
        if self._running:
            return self

        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def stop(self, final_message: Optional[str] = None) -> None:
        """Stop the spinner animation.

        Args:
            final_message: Optional message to display when stopped
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Clear the spinner line
        self._clear_line()

        if final_message:
            self.stream.write(f"{final_message}\n")
            self.stream.flush()

    def update(self, message: str) -> None:
        """Update the spinner message.

        Args:
            message: New message to display
        """
        self.message = message

    def _animate(self) -> None:
        """Animation loop running in thread."""
        while self._running:
            frame = self._frames[self._frame_idx]
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)

            spinner_text = colorize(frame, Color.CYAN, use_color=self.use_color)
            line = f"\r{spinner_text} {self.message}"

            self.stream.write(line)
            self.stream.flush()

            time.sleep(self._interval)

    def _clear_line(self) -> None:
        """Clear the current line."""
        self.stream.write("\r\033[K")
        self.stream.flush()

    def __enter__(self) -> "Spinner":
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if exc_type:
            self.stop(colorize("✗ Error", Color.RED, use_color=self.use_color))
        else:
            self.stop(colorize("✓ Done", Color.GREEN, use_color=self.use_color))


class ProgressBar:
    """Progress bar for tracking completion.

    Example:
        with ProgressBar(total=100, description="Processing") as bar:
            for i in range(100):
                do_work(i)
                bar.update(1)
    """

    def __init__(
        self,
        total: int,
        description: str = "",
        width: int = 40,
        stream: TextIO = sys.stderr,
        use_color: bool = True,
    ) -> None:
        """Initialize progress bar.

        Args:
            total: Total number of items
            description: Description to show
            width: Bar width in characters
            stream: Output stream
            use_color: Whether to use colors
        """
        self.total = total
        self.description = description
        self.width = width
        self.stream = stream
        self.use_color = use_color

        self._current = 0
        self._start_time: Optional[float] = None

    def start(self) -> "ProgressBar":
        """Start the progress bar."""
        self._start_time = time.time()
        self._render()
        return self

    def update(self, n: int = 1) -> None:
        """Update progress by n items.

        Args:
            n: Number of items completed
        """
        self._current = min(self._current + n, self.total)
        self._render()

    def finish(self) -> None:
        """Complete the progress bar."""
        self._current = self.total
        self._render()
        self.stream.write("\n")
        self.stream.flush()

    def _render(self) -> None:
        """Render the progress bar."""
        if self.total <= 0:
            return

        progress = self._current / self.total
        filled = int(self.width * progress)
        empty = self.width - filled

        bar = "█" * filled + "░" * empty
        percent = f"{progress * 100:5.1f}%"

        # Calculate ETA
        eta = ""
        if self._start_time and progress > 0:
            elapsed = time.time() - self._start_time
            estimated_total = elapsed / progress
            remaining = estimated_total - elapsed
            if remaining > 0:
                eta = f" ETA: {self._format_time(remaining)}"

        # Build line
        desc = f"{self.description}: " if self.description else ""
        count = f" {self._current}/{self.total}"

        bar_colored = colorize(bar, Color.CYAN, use_color=self.use_color)
        line = f"\r{desc}|{bar_colored}| {percent}{count}{eta}"

        self.stream.write(line)
        self.stream.flush()

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:.0f}m{secs:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h{minutes:.0f}m"

    def __enter__(self) -> "ProgressBar":
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.finish()


@dataclass
class TableColumn:
    """Column definition for table formatting."""

    header: str
    key: str
    width: Optional[int] = None
    align: str = "left"  # left, right, center
    color: Optional[Color] = None


class Table:
    """ASCII table formatter.

    Example:
        table = Table([
            TableColumn("Name", "name", width=20),
            TableColumn("Status", "status"),
        ])
        table.add_row({"name": "Server 1", "status": "Running"})
        print(table.render())
    """

    def __init__(
        self,
        columns: list[TableColumn],
        use_color: bool = True,
        border_style: str = "single",  # single, double, none
    ) -> None:
        """Initialize table.

        Args:
            columns: Column definitions
            use_color: Whether to use colors
            border_style: Border style
        """
        self.columns = columns
        self.use_color = use_color
        self.border_style = border_style
        self._rows: list[dict[str, Any]] = []

    def add_row(self, data: dict[str, Any]) -> None:
        """Add a row to the table.

        Args:
            data: Row data as dictionary
        """
        self._rows.append(data)

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        """Add multiple rows.

        Args:
            rows: List of row data dictionaries
        """
        self._rows.extend(rows)

    def render(self) -> str:
        """Render the table as string.

        Returns:
            Formatted table string
        """
        if not self.columns:
            return ""

        # Calculate column widths
        widths = self._calculate_widths()

        # Build table parts
        lines: list[str] = []

        # Header
        if self.border_style != "none":
            lines.append(self._render_separator(widths, "top"))
        lines.append(self._render_row({c.key: c.header for c in self.columns}, widths, is_header=True))
        if self.border_style != "none":
            lines.append(self._render_separator(widths, "middle"))

        # Rows
        for row in self._rows:
            lines.append(self._render_row(row, widths))

        # Bottom border
        if self.border_style != "none":
            lines.append(self._render_separator(widths, "bottom"))

        return "\n".join(lines)

    def _calculate_widths(self) -> list[int]:
        """Calculate column widths based on content."""
        widths = []
        for col in self.columns:
            if col.width:
                widths.append(col.width)
            else:
                # Calculate from content
                max_width = len(col.header)
                for row in self._rows:
                    value = str(row.get(col.key, ""))
                    max_width = max(max_width, len(strip_ansi(value)))
                widths.append(max_width)
        return widths

    def _render_separator(self, widths: list[int], position: str) -> str:
        """Render a separator line."""
        if self.border_style == "double":
            chars = {"top": ("╔", "═", "╤", "╗"), "middle": ("╟", "─", "┼", "╢"), "bottom": ("╚", "═", "╧", "╝")}
        else:  # single
            chars = {"top": ("┌", "─", "┬", "┐"), "middle": ("├", "─", "┼", "┤"), "bottom": ("└", "─", "┴", "┘")}

        left, line, cross, right = chars[position]
        parts = [line * (w + 2) for w in widths]
        return left + cross.join(parts) + right

    def _render_row(self, data: dict[str, Any], widths: list[int], is_header: bool = False) -> str:
        """Render a single row."""
        if self.border_style == "double":
            sep = "║"
        elif self.border_style == "single":
            sep = "│"
        else:
            sep = " "

        cells = []
        for col, width in zip(self.columns, widths):
            value = str(data.get(col.key, ""))

            # Apply color
            if col.color and self.use_color and not is_header:
                value = colorize(value, col.color, use_color=self.use_color)

            # Pad to width
            plain_len = len(strip_ansi(value))
            padding = width - plain_len

            if col.align == "right":
                value = " " * padding + value
            elif col.align == "center":
                left_pad = padding // 2
                right_pad = padding - left_pad
                value = " " * left_pad + value + " " * right_pad
            else:  # left
                value = value + " " * padding

            cells.append(f" {value} ")

        return sep + sep.join(cells) + sep

    def __str__(self) -> str:
        """String representation."""
        return self.render()


@dataclass
class ErrorContext:
    """Context for user-friendly error messages."""

    error_type: str
    message: str
    suggestion: Optional[str] = None
    details: Optional[str] = None
    help_url: Optional[str] = None


class ErrorFormatter:
    """Format errors in a user-friendly way.

    Example:
        formatter = ErrorFormatter()
        print(formatter.format(ErrorContext(
            error_type="ConnectionError",
            message="Failed to connect to API",
            suggestion="Check your network connection and API key",
        )))
    """

    def __init__(self, use_color: bool = True) -> None:
        """Initialize error formatter.

        Args:
            use_color: Whether to use colors
        """
        self.use_color = use_color

    def format(self, ctx: ErrorContext) -> str:
        """Format an error context.

        Args:
            ctx: Error context to format

        Returns:
            Formatted error string
        """
        lines: list[str] = []

        # Error header
        header = colorize(f"✗ {ctx.error_type}", Color.RED, Color.BOLD, use_color=self.use_color)
        lines.append(header)
        lines.append("")

        # Message
        lines.append(f"  {ctx.message}")
        lines.append("")

        # Details
        if ctx.details:
            lines.append(colorize("  Details:", Color.DIM, use_color=self.use_color))
            for line in ctx.details.split("\n"):
                lines.append(colorize(f"    {line}", Color.DIM, use_color=self.use_color))
            lines.append("")

        # Suggestion
        if ctx.suggestion:
            suggestion = colorize("  Suggestion: ", Color.YELLOW, use_color=self.use_color)
            lines.append(f"{suggestion}{ctx.suggestion}")
            lines.append("")

        # Help URL
        if ctx.help_url:
            help_text = colorize("  More info: ", Color.BLUE, use_color=self.use_color)
            lines.append(f"{help_text}{ctx.help_url}")
            lines.append("")

        return "\n".join(lines)

    def format_exception(
        self,
        exc: Exception,
        suggestion: Optional[str] = None,
    ) -> str:
        """Format an exception.

        Args:
            exc: Exception to format
            suggestion: Optional suggestion for fixing

        Returns:
            Formatted error string
        """
        ctx = ErrorContext(
            error_type=type(exc).__name__,
            message=str(exc),
            suggestion=suggestion,
        )
        return self.format(ctx)


# Common error suggestions
ERROR_SUGGESTIONS = {
    "ConnectionError": "Check your network connection and try again.",
    "TimeoutError": "The operation timed out. Try again or increase the timeout.",
    "PermissionError": "You don't have permission to perform this action. Try with sudo or check file permissions.",
    "FileNotFoundError": "The specified file or directory does not exist. Check the path and try again.",
    "AuthenticationError": "Authentication failed. Check your API key or credentials.",
    "RateLimitError": "Rate limit exceeded. Wait a moment and try again.",
    "ValueError": "Invalid input provided. Check the format and try again.",
    "ImportError": "A required module is not installed. Install it with pip.",
}


def get_error_suggestion(exc: Exception) -> Optional[str]:
    """Get a suggestion for an exception type.

    Args:
        exc: Exception to get suggestion for

    Returns:
        Suggestion string or None
    """
    return ERROR_SUGGESTIONS.get(type(exc).__name__)


def print_success(message: str, stream: TextIO = sys.stdout, use_color: bool = True) -> None:
    """Print a success message.

    Args:
        message: Message to print
        stream: Output stream
        use_color: Whether to use colors
    """
    prefix = colorize("✓", Color.GREEN, use_color=use_color)
    stream.write(f"{prefix} {message}\n")
    stream.flush()


def print_warning(message: str, stream: TextIO = sys.stderr, use_color: bool = True) -> None:
    """Print a warning message.

    Args:
        message: Message to print
        stream: Output stream
        use_color: Whether to use colors
    """
    prefix = colorize("⚠", Color.YELLOW, use_color=use_color)
    stream.write(f"{prefix} {message}\n")
    stream.flush()


def print_error(message: str, stream: TextIO = sys.stderr, use_color: bool = True) -> None:
    """Print an error message.

    Args:
        message: Message to print
        stream: Output stream
        use_color: Whether to use colors
    """
    prefix = colorize("✗", Color.RED, use_color=use_color)
    stream.write(f"{prefix} {message}\n")
    stream.flush()


def print_info(message: str, stream: TextIO = sys.stdout, use_color: bool = True) -> None:
    """Print an info message.

    Args:
        message: Message to print
        stream: Output stream
        use_color: Whether to use colors
    """
    prefix = colorize("ℹ", Color.BLUE, use_color=use_color)
    stream.write(f"{prefix} {message}\n")
    stream.flush()


@contextmanager
def status(
    message: str,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    stream: TextIO = sys.stderr,
    use_color: bool = True,
) -> Generator[Spinner, None, None]:
    """Context manager for status indication with spinner.

    Args:
        message: Initial status message
        success_message: Message on success (default: "Done")
        error_message: Message on error (default: "Failed")
        stream: Output stream
        use_color: Whether to use colors

    Yields:
        Spinner instance for updating status

    Example:
        with status("Connecting to server") as s:
            connect()
            s.update("Fetching data")
            fetch_data()
    """
    spinner = Spinner(message, stream=stream, use_color=use_color)
    spinner.start()

    try:
        yield spinner
        final = success_message or colorize("✓ Done", Color.GREEN, use_color=use_color)
        spinner.stop(final)
    except Exception:
        final = error_message or colorize("✗ Failed", Color.RED, use_color=use_color)
        spinner.stop(final)
        raise


class OutputBuffer:
    """Buffer for collecting and formatting output.

    Useful for building complex output with multiple sections.
    """

    def __init__(self, use_color: bool = True) -> None:
        """Initialize buffer.

        Args:
            use_color: Whether to use colors
        """
        self.use_color = use_color
        self._parts: list[str] = []

    def add(self, text: str) -> "OutputBuffer":
        """Add text to buffer."""
        self._parts.append(text)
        return self

    def add_line(self, text: str = "") -> "OutputBuffer":
        """Add a line to buffer."""
        self._parts.append(f"{text}\n")
        return self

    def add_header(self, text: str, level: int = 1) -> "OutputBuffer":
        """Add a header.

        Args:
            text: Header text
            level: Header level (1-3)
        """
        if level == 1:
            colored = colorize(text, Color.BOLD, Color.CYAN, use_color=self.use_color)
            self._parts.append(f"\n{colored}\n{'=' * len(text)}\n")
        elif level == 2:
            colored = colorize(text, Color.BOLD, use_color=self.use_color)
            self._parts.append(f"\n{colored}\n{'-' * len(text)}\n")
        else:
            colored = colorize(text, Color.BOLD, use_color=self.use_color)
            self._parts.append(f"\n{colored}\n")
        return self

    def add_list(self, items: list[str], bullet: str = "•") -> "OutputBuffer":
        """Add a bulleted list.

        Args:
            items: List items
            bullet: Bullet character
        """
        for item in items:
            self._parts.append(f"  {bullet} {item}\n")
        return self

    def add_table(self, table: Table) -> "OutputBuffer":
        """Add a table.

        Args:
            table: Table to add
        """
        self._parts.append(f"{table.render()}\n")
        return self

    def add_separator(self, char: str = "─", width: int = 40) -> "OutputBuffer":
        """Add a separator line.

        Args:
            char: Separator character
            width: Separator width
        """
        sep = colorize(char * width, Color.DIM, use_color=self.use_color)
        self._parts.append(f"{sep}\n")
        return self

    def render(self) -> str:
        """Render the buffer contents."""
        return "".join(self._parts)

    def __str__(self) -> str:
        """String representation."""
        return self.render()
