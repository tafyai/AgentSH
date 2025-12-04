"""Input Classifier - Routes user input to shell or AI."""

import re
import shlex
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class InputType(Enum):
    """Classification of user input."""

    SHELL_COMMAND = auto()  # Execute directly in shell
    AI_REQUEST = auto()  # Send to AI agent
    SPECIAL_COMMAND = auto()  # Internal AgentSH command
    EMPTY = auto()  # Empty input


@dataclass
class ClassifiedInput:
    """Result of input classification."""

    input_type: InputType
    content: str  # The processed content (prefix removed if applicable)
    original: str  # Original input
    confidence: float = 1.0  # Classification confidence (0-1)
    reason: Optional[str] = None  # Why this classification was chosen


class InputClassifier:
    """Classifies user input to determine routing.

    Routing rules:
    1. Force shell: Input starts with shell_prefix (default: "!")
    2. Force AI: Input starts with ai_prefix (default: "ai ")
    3. Special commands: Input starts with ":" (e.g., :help, :config)
    4. Heuristic classification based on input characteristics

    Examples:
        classifier = InputClassifier(ai_prefix="ai ", shell_prefix="!")

        # Force shell
        classifier.classify("!ls -la")  # -> SHELL_COMMAND

        # Force AI
        classifier.classify("ai list all python files")  # -> AI_REQUEST

        # Special command
        classifier.classify(":help")  # -> SPECIAL_COMMAND

        # Heuristic (looks like a command)
        classifier.classify("ls -la")  # -> SHELL_COMMAND

        # Heuristic (natural language)
        classifier.classify("find all files modified today")  # -> AI_REQUEST
    """

    # Common shell command patterns
    SHELL_COMMAND_PATTERNS = [
        r"^(ls|cd|pwd|mkdir|rm|cp|mv|cat|head|tail|less|more|grep|find|chmod|chown)\b",
        r"^(git|docker|kubectl|npm|yarn|pip|uv|cargo|make|cmake)\b",
        r"^(python|python3|node|ruby|perl|php|java|go|rust)\b",
        r"^(vim|nvim|nano|emacs|code|subl)\b",
        r"^(curl|wget|ssh|scp|rsync|tar|zip|unzip)\b",
        r"^(ps|top|htop|kill|pkill|sudo|su|which|whereis|type)\b",
        r"^(echo|printf|read|export|source|alias|unalias)\b",
        r"^(apt|apt-get|brew|yum|dnf|pacman)\b",
        r"^(systemctl|service|journalctl)\b",
        r"^(\./|/|~)",  # Paths
        r"^[a-z_][a-z0-9_]*=",  # Variable assignment
    ]

    # Patterns suggesting natural language (AI request)
    NATURAL_LANGUAGE_PATTERNS = [
        r"\b(please|help|how|what|why|when|where|which|can you|could you)\b",
        r"\b(find|show|list|display|get|give|tell|explain)\s+me\b",
        r"\b(i want|i need|i'd like|let's|let me)\b",
        r"\?$",  # Ends with question mark
        r"\b(all|every|any)\s+\w+\s+(files?|folders?|directories?)\b",
    ]

    # Special command prefix
    SPECIAL_PREFIX = ":"

    def __init__(
        self,
        ai_prefix: str = "ai ",
        shell_prefix: str = "!",
        default_to_ai: bool = False,
    ) -> None:
        """Initialize the classifier.

        Args:
            ai_prefix: Prefix to force AI routing
            shell_prefix: Prefix to force shell routing
            default_to_ai: If True, route ambiguous input to AI. Otherwise shell.
        """
        self.ai_prefix = ai_prefix
        self.shell_prefix = shell_prefix
        self.default_to_ai = default_to_ai

        # Compile patterns for efficiency
        self._shell_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SHELL_COMMAND_PATTERNS
        ]
        self._nl_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.NATURAL_LANGUAGE_PATTERNS
        ]

    def classify(self, input_text: str) -> ClassifiedInput:
        """Classify user input.

        Args:
            input_text: Raw user input

        Returns:
            ClassifiedInput with type and processed content
        """
        original = input_text
        stripped = input_text.strip()

        # Empty input
        if not stripped:
            return ClassifiedInput(
                input_type=InputType.EMPTY,
                content="",
                original=original,
                reason="Empty input",
            )

        # Check for force prefixes first
        if stripped.startswith(self.shell_prefix):
            content = stripped[len(self.shell_prefix) :].strip()
            return ClassifiedInput(
                input_type=InputType.SHELL_COMMAND,
                content=content,
                original=original,
                reason=f"Forced by '{self.shell_prefix}' prefix",
            )

        if stripped.startswith(self.ai_prefix):
            content = stripped[len(self.ai_prefix) :].strip()
            return ClassifiedInput(
                input_type=InputType.AI_REQUEST,
                content=content,
                original=original,
                reason=f"Forced by '{self.ai_prefix}' prefix",
            )

        # Check for special commands
        if stripped.startswith(self.SPECIAL_PREFIX):
            content = stripped[len(self.SPECIAL_PREFIX) :].strip()
            return ClassifiedInput(
                input_type=InputType.SPECIAL_COMMAND,
                content=content,
                original=original,
                reason="Special command prefix",
            )

        # Heuristic classification
        return self._heuristic_classify(stripped, original)

    def _heuristic_classify(self, text: str, original: str) -> ClassifiedInput:
        """Use heuristics to classify ambiguous input.

        Args:
            text: Stripped input text
            original: Original input

        Returns:
            ClassifiedInput based on heuristics
        """
        shell_score = self._shell_likelihood(text)
        nl_score = self._natural_language_likelihood(text)

        logger.debug(
            "Heuristic scores",
            input=text[:50],
            shell_score=shell_score,
            nl_score=nl_score,
        )

        # Determine classification based on scores
        if shell_score > nl_score:
            confidence = min(1.0, shell_score / (shell_score + nl_score + 0.1))
            return ClassifiedInput(
                input_type=InputType.SHELL_COMMAND,
                content=text,
                original=original,
                confidence=confidence,
                reason=f"Looks like shell command (score: {shell_score:.2f})",
            )
        elif nl_score > shell_score:
            confidence = min(1.0, nl_score / (shell_score + nl_score + 0.1))
            return ClassifiedInput(
                input_type=InputType.AI_REQUEST,
                content=text,
                original=original,
                confidence=confidence,
                reason=f"Looks like natural language (score: {nl_score:.2f})",
            )
        else:
            # Ambiguous - use default
            input_type = InputType.AI_REQUEST if self.default_to_ai else InputType.SHELL_COMMAND
            return ClassifiedInput(
                input_type=input_type,
                content=text,
                original=original,
                confidence=0.5,
                reason=f"Ambiguous, using default ({input_type.name})",
            )

    def _shell_likelihood(self, text: str) -> float:
        """Calculate likelihood that input is a shell command.

        Args:
            text: Input text

        Returns:
            Score from 0 to 1
        """
        score = 0.0

        # Check shell command patterns
        for pattern in self._shell_patterns:
            if pattern.search(text):
                score += 0.3

        # Check if it's valid shell syntax
        try:
            tokens = shlex.split(text)
            if tokens:
                # First token looks like a command
                first = tokens[0]
                if first.startswith(("./", "/", "~")) or not " " in first:
                    score += 0.2

                # Has flags (starts with -)
                if any(t.startswith("-") for t in tokens[1:]):
                    score += 0.2

                # Has pipe, redirect, or other shell operators
                if any(op in text for op in ["|", ">", "<", "&&", "||", ";"]):
                    score += 0.3

        except ValueError:
            # Invalid shell syntax
            pass

        # Short commands are more likely shell
        if len(text.split()) <= 3:
            score += 0.1

        return min(1.0, score)

    def _natural_language_likelihood(self, text: str) -> float:
        """Calculate likelihood that input is natural language.

        Args:
            text: Input text

        Returns:
            Score from 0 to 1
        """
        score = 0.0

        # Check natural language patterns
        for pattern in self._nl_patterns:
            if pattern.search(text):
                score += 0.3

        # Long text with spaces is more likely natural language
        word_count = len(text.split())
        if word_count >= 5:
            score += 0.2
        if word_count >= 8:
            score += 0.2

        # Contains punctuation typical of natural language
        if any(p in text for p in [".", ",", "?", "!"]):
            score += 0.1

        # Starts with capital letter (sentence-like)
        if text and text[0].isupper():
            score += 0.1

        return min(1.0, score)

    def is_shell_command(self, input_text: str) -> bool:
        """Quick check if input is a shell command.

        Args:
            input_text: User input

        Returns:
            True if classified as shell command
        """
        result = self.classify(input_text)
        return result.input_type == InputType.SHELL_COMMAND

    def is_ai_request(self, input_text: str) -> bool:
        """Quick check if input is an AI request.

        Args:
            input_text: User input

        Returns:
            True if classified as AI request
        """
        result = self.classify(input_text)
        return result.input_type == InputType.AI_REQUEST


# Special commands registry
SPECIAL_COMMANDS = {
    "help": "Show help information",
    "h": "Show help information (alias)",
    "config": "Show current configuration",
    "history": "Show AI conversation history",
    "clear": "Clear the screen",
    "reset": "Reset AI conversation context",
    "status": "Show system status",
    "quit": "Exit AgentSH",
    "exit": "Exit AgentSH",
    "q": "Exit AgentSH (alias)",
}


def parse_special_command(content: str) -> tuple[str, list[str]]:
    """Parse a special command into command name and arguments.

    Args:
        content: Command content (without : prefix)

    Returns:
        Tuple of (command_name, arguments)
    """
    parts = content.split(maxsplit=1)
    command = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    return command, args
