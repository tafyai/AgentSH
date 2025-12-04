"""Shell wrapper and user I/O handling."""

from agentsh.shell.history import HistoryEntry, HistoryManager, ReadlineHistory
from agentsh.shell.input_classifier import (
    ClassifiedInput,
    InputClassifier,
    InputType,
    SPECIAL_COMMANDS,
    parse_special_command,
)
from agentsh.shell.prompt import (
    AgentStatus,
    Colors,
    PromptContext,
    PromptRenderer,
    PromptStyle,
    strip_ansi,
)
from agentsh.shell.pty_manager import PTYManager
from agentsh.shell.wrapper import ShellWrapper

__all__ = [
    # Wrapper
    "ShellWrapper",
    # PTY Manager
    "PTYManager",
    # Input Classifier
    "ClassifiedInput",
    "InputClassifier",
    "InputType",
    "SPECIAL_COMMANDS",
    "parse_special_command",
    # Prompt
    "AgentStatus",
    "Colors",
    "PromptContext",
    "PromptRenderer",
    "PromptStyle",
    "strip_ansi",
    # History
    "HistoryEntry",
    "HistoryManager",
    "ReadlineHistory",
]
