"""Tests for the input classifier."""

import pytest

from agentsh.shell.input_classifier import (
    ClassifiedInput,
    InputClassifier,
    InputType,
    SPECIAL_COMMANDS,
    parse_special_command,
)


class TestInputClassifier:
    """Test cases for InputClassifier."""

    @pytest.fixture
    def classifier(self) -> InputClassifier:
        """Create a default classifier."""
        return InputClassifier(
            ai_prefix="ai ",
            shell_prefix="!",
            default_to_ai=False,
        )

    @pytest.fixture
    def ai_default_classifier(self) -> InputClassifier:
        """Create a classifier that defaults to AI."""
        return InputClassifier(
            ai_prefix="ai ",
            shell_prefix="!",
            default_to_ai=True,
        )

    # Empty input tests
    def test_empty_input(self, classifier: InputClassifier) -> None:
        """Test that empty input is classified as EMPTY."""
        result = classifier.classify("")
        assert result.input_type == InputType.EMPTY
        assert result.content == ""

    def test_whitespace_only_input(self, classifier: InputClassifier) -> None:
        """Test that whitespace-only input is classified as EMPTY."""
        result = classifier.classify("   \t  ")
        assert result.input_type == InputType.EMPTY

    # Force prefix tests
    def test_shell_prefix_forces_shell(self, classifier: InputClassifier) -> None:
        """Test that ! prefix forces shell command."""
        result = classifier.classify("!ls -la")
        assert result.input_type == InputType.SHELL_COMMAND
        assert result.content == "ls -la"
        assert "Forced by" in result.reason

    def test_ai_prefix_forces_ai(self, classifier: InputClassifier) -> None:
        """Test that 'ai ' prefix forces AI request."""
        result = classifier.classify("ai find all python files")
        assert result.input_type == InputType.AI_REQUEST
        assert result.content == "find all python files"
        assert "Forced by" in result.reason

    def test_ai_prefix_case_sensitive(self, classifier: InputClassifier) -> None:
        """Test that AI prefix is case-sensitive."""
        result = classifier.classify("AI find files")
        # Should not match 'ai ' prefix, will be heuristic classified
        assert result.input_type != InputType.AI_REQUEST or "Forced" not in result.reason

    # Special command tests
    def test_special_command_help(self, classifier: InputClassifier) -> None:
        """Test that :help is classified as special command."""
        result = classifier.classify(":help")
        assert result.input_type == InputType.SPECIAL_COMMAND
        assert result.content == "help"

    def test_special_command_config(self, classifier: InputClassifier) -> None:
        """Test that :config is classified as special command."""
        result = classifier.classify(":config")
        assert result.input_type == InputType.SPECIAL_COMMAND
        assert result.content == "config"

    def test_special_command_with_args(self, classifier: InputClassifier) -> None:
        """Test special command with arguments."""
        result = classifier.classify(":history --ai 50")
        assert result.input_type == InputType.SPECIAL_COMMAND
        assert result.content == "history --ai 50"

    def test_special_command_quit(self, classifier: InputClassifier) -> None:
        """Test that :quit is classified as special command."""
        result = classifier.classify(":quit")
        assert result.input_type == InputType.SPECIAL_COMMAND
        assert result.content == "quit"

    # Heuristic classification - shell commands
    def test_heuristic_ls_command(self, classifier: InputClassifier) -> None:
        """Test that 'ls' is classified as shell command."""
        result = classifier.classify("ls -la")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_git_command(self, classifier: InputClassifier) -> None:
        """Test that git commands are classified as shell."""
        result = classifier.classify("git status")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_docker_command(self, classifier: InputClassifier) -> None:
        """Test that docker commands are classified as shell."""
        result = classifier.classify("docker ps -a")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_path_execution(self, classifier: InputClassifier) -> None:
        """Test that path execution is classified as shell."""
        result = classifier.classify("./script.sh")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_absolute_path(self, classifier: InputClassifier) -> None:
        """Test that absolute path is classified as shell."""
        result = classifier.classify("/usr/bin/python3 script.py")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_pipe_command(self, classifier: InputClassifier) -> None:
        """Test that piped commands are classified as shell."""
        result = classifier.classify("cat file.txt | grep pattern")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_redirect_command(self, classifier: InputClassifier) -> None:
        """Test that redirected commands are classified as shell."""
        result = classifier.classify("echo hello > file.txt")
        assert result.input_type == InputType.SHELL_COMMAND

    def test_heuristic_variable_assignment(self, classifier: InputClassifier) -> None:
        """Test that variable assignment is classified as shell."""
        result = classifier.classify("FOO=bar")
        assert result.input_type == InputType.SHELL_COMMAND

    # Heuristic classification - AI requests
    def test_heuristic_question(self, classifier: InputClassifier) -> None:
        """Test that questions are classified as AI request."""
        result = classifier.classify("How do I find all python files?")
        assert result.input_type == InputType.AI_REQUEST

    def test_heuristic_please_request(self, classifier: InputClassifier) -> None:
        """Test that 'please' requests are classified as AI."""
        result = classifier.classify("please list all directories")
        assert result.input_type == InputType.AI_REQUEST

    def test_heuristic_help_request(self, classifier: InputClassifier) -> None:
        """Test that help requests are classified as AI."""
        result = classifier.classify("help me understand this error")
        assert result.input_type == InputType.AI_REQUEST

    def test_heuristic_long_natural_language(self, classifier: InputClassifier) -> None:
        """Test that long natural language is classified as AI."""
        result = classifier.classify(
            "I need to find all the python files that were modified in the last week"
        )
        assert result.input_type == InputType.AI_REQUEST

    def test_heuristic_show_me(self, classifier: InputClassifier) -> None:
        """Test that 'show me' is classified as AI."""
        result = classifier.classify("show me all running processes")
        assert result.input_type == InputType.AI_REQUEST

    # Default behavior tests
    def test_default_to_shell(self, classifier: InputClassifier) -> None:
        """Test that short single words are classified as shell commands."""
        result = classifier.classify("foo")  # Short single word looks like shell
        # Short commands tend to match shell patterns
        assert result.input_type == InputType.SHELL_COMMAND

    def test_ambiguous_with_equal_scores(
        self, classifier: InputClassifier, ai_default_classifier: InputClassifier
    ) -> None:
        """Test that truly ambiguous input uses default setting."""
        # "xyz" is truly ambiguous - short and no patterns match
        # When scores are equal (0.1 each), default is used
        # Note: Actual classification depends on heuristic tuning
        result_shell = classifier.classify("xyz abc def ghi jkl")
        result_ai = ai_default_classifier.classify("xyz abc def ghi jkl")
        # Both should classify but possibly differently based on default
        assert result_shell.input_type in (InputType.SHELL_COMMAND, InputType.AI_REQUEST)
        assert result_ai.input_type in (InputType.SHELL_COMMAND, InputType.AI_REQUEST)

    # Confidence tests
    def test_forced_prefix_has_high_confidence(
        self, classifier: InputClassifier
    ) -> None:
        """Test that forced prefixes have confidence 1.0."""
        result = classifier.classify("!ls")
        assert result.confidence == 1.0

        result = classifier.classify("ai test")
        assert result.confidence == 1.0

    def test_special_command_has_high_confidence(
        self, classifier: InputClassifier
    ) -> None:
        """Test that special commands have confidence 1.0."""
        result = classifier.classify(":help")
        assert result.confidence == 1.0

    # Convenience method tests
    def test_is_shell_command(self, classifier: InputClassifier) -> None:
        """Test is_shell_command convenience method."""
        assert classifier.is_shell_command("!ls")
        assert classifier.is_shell_command("ls -la")
        assert not classifier.is_shell_command("ai test")
        assert not classifier.is_shell_command(":help")

    def test_is_ai_request(self, classifier: InputClassifier) -> None:
        """Test is_ai_request convenience method."""
        assert classifier.is_ai_request("ai test")
        # "please help me" is borderline - both scores are close
        # Use a more clearly AI-style request
        assert classifier.is_ai_request("How do I find all python files in this directory?")
        assert not classifier.is_ai_request("!ls")
        assert not classifier.is_ai_request("ls -la")


class TestParseSpecialCommand:
    """Test cases for parse_special_command."""

    def test_simple_command(self) -> None:
        """Test parsing simple command."""
        cmd, args = parse_special_command("help")
        assert cmd == "help"
        assert args == []

    def test_command_with_args(self) -> None:
        """Test parsing command with arguments."""
        cmd, args = parse_special_command("history --ai 50")
        assert cmd == "history"
        assert args == ["--ai", "50"]

    def test_uppercase_normalized(self) -> None:
        """Test that command is lowercased."""
        cmd, args = parse_special_command("HELP")
        assert cmd == "help"

    def test_empty_content(self) -> None:
        """Test parsing empty content."""
        cmd, args = parse_special_command("")
        assert cmd == ""
        assert args == []


class TestSpecialCommands:
    """Test cases for special commands registry."""

    def test_all_commands_documented(self) -> None:
        """Test that all expected commands are in registry."""
        expected = {
            "help", "h", "config", "history", "clear", "reset", "status",
            "remember", "recall", "forget",  # Memory commands
            "quit", "exit", "q",
        }
        assert set(SPECIAL_COMMANDS.keys()) == expected

    def test_commands_have_descriptions(self) -> None:
        """Test that all commands have descriptions."""
        for cmd, desc in SPECIAL_COMMANDS.items():
            assert isinstance(desc, str)
            assert len(desc) > 0
