"""Shell Wrapper - Main REPL interface for AgentSH."""

import os
import select
import sys
import termios
import tty
from typing import TYPE_CHECKING, Callable, Optional

from agentsh.shell.help import show_help
from agentsh.shell.history import HistoryManager, ReadlineHistory
from agentsh.shell.memory import (
    format_memory_list,
    get_memory_store,
)
from agentsh.shell.input_classifier import (
    ClassifiedInput,
    InputClassifier,
    InputType,
    SPECIAL_COMMANDS,
    parse_special_command,
)
from agentsh.shell.prompt import AgentStatus, PromptRenderer, PromptStyle
from agentsh.shell.pty_manager import PTYManager
from agentsh.telemetry.logger import get_logger, LoggerMixin

if TYPE_CHECKING:
    from agentsh.config.schemas import AgentSHConfig

logger = get_logger(__name__)


class ShellWrapper(LoggerMixin):
    """Wraps the user's shell with AI capabilities.

    This class provides:
    - PTY-based shell wrapping for transparent shell access
    - Input classification to route between shell and AI
    - Custom prompt rendering with status indicators
    - Command history management
    - Integration with AI agent (Phase 2)

    The shell operates in two modes:
    1. Pass-through mode: Direct PTY I/O for shell commands
    2. AI mode: Captures input for AI processing

    Example:
        config = AgentSHConfig()
        shell = ShellWrapper(config)
        shell.run()
    """

    def __init__(self, config: "AgentSHConfig") -> None:
        """Initialize the shell wrapper.

        Args:
            config: AgentSH configuration
        """
        self.config = config
        self._running = False
        self._agent_status = AgentStatus.IDLE
        self._last_exit_code = 0

        # Initialize components
        self._pty: Optional[PTYManager] = None
        self._classifier = InputClassifier(
            ai_prefix=config.shell.ai_prefix,
            shell_prefix=config.shell.shell_prefix,
            default_to_ai=config.shell.default_to_ai,
        )
        self._prompt = PromptRenderer(
            style=PromptStyle.STANDARD,
            use_color=True,
            use_emoji=False,
        )
        self._history = HistoryManager(
            max_entries=config.shell.history_size,
        )

        # AI handler callback (set in Phase 2)
        self._ai_handler: Optional[Callable[[str], str]] = None

        self.logger.info(
            "ShellWrapper initialized",
            shell=config.shell.backend,
            ai_prefix=config.shell.ai_prefix,
        )

    def set_ai_handler(self, handler: Callable[[str], str]) -> None:
        """Set the AI request handler.

        Args:
            handler: Function that takes AI request and returns response
        """
        self._ai_handler = handler

    def run(self) -> None:
        """Run the interactive shell REPL.

        This is the main entry point for interactive mode.
        """
        self._running = True
        self.logger.info("Starting AgentSH shell")

        # Load history
        self._history.load()
        readline_history = ReadlineHistory(self._history)
        readline_history.setup()

        try:
            self._run_repl()
        finally:
            # Save history
            self._history.save()
            readline_history.save()
            self._running = False
            self.logger.info("Shell session ended")

    def _run_repl(self) -> None:
        """Main REPL loop."""
        self._print_welcome()

        while self._running:
            try:
                # Render prompt
                prompt = self._prompt.render_ps1(
                    agent_status=self._agent_status,
                    last_exit_code=self._last_exit_code,
                )

                # Get input
                try:
                    user_input = input(prompt)
                except EOFError:
                    # Ctrl+D
                    print()
                    break

                # Process input
                self._process_input(user_input)

            except KeyboardInterrupt:
                # Ctrl+C - print newline and continue
                print()
                self._last_exit_code = 130
                continue

    def _process_input(self, user_input: str) -> None:
        """Process user input and route appropriately.

        Args:
            user_input: Raw user input
        """
        # Classify input
        classified = self._classifier.classify(user_input)

        self.logger.debug(
            "Input classified",
            input_type=classified.input_type.name,
            content=classified.content[:50] if classified.content else "",
            confidence=classified.confidence,
        )

        if classified.input_type == InputType.EMPTY:
            return

        elif classified.input_type == InputType.SPECIAL_COMMAND:
            self._handle_special_command(classified)

        elif classified.input_type == InputType.AI_REQUEST:
            self._handle_ai_request(classified)

        elif classified.input_type == InputType.SHELL_COMMAND:
            self._handle_shell_command(classified)

    def _handle_special_command(self, classified: ClassifiedInput) -> None:
        """Handle special AgentSH commands.

        Args:
            classified: Classified input
        """
        command, args = parse_special_command(classified.content)

        if command in ("help", "h"):
            # Show help - optionally for a specific topic
            topic = args[0] if args else None
            print(show_help(topic))
        elif command == "config":
            self._show_config()
        elif command == "history":
            self._show_history(args)
        elif command == "clear":
            os.system("clear" if os.name != "nt" else "cls")
        elif command == "reset":
            self._reset_context()
        elif command == "status":
            self._show_status()
        elif command == "remember":
            self._handle_remember(args)
        elif command == "recall":
            self._handle_recall(args)
        elif command == "forget":
            self._handle_forget(args)
        elif command in ("quit", "exit", "q"):
            self._running = False
            print("Goodbye!")
        else:
            print(f"Unknown command: {command}")
            print("Type :help for available commands")

    def _handle_remember(self, args: list[str]) -> None:
        """Handle :remember command.

        Args:
            args: Command arguments (the note to remember)
        """
        if not args:
            print("Usage: :remember <note>")
            print("Example: :remember Deploy to production on Friday")
            return

        content = " ".join(args)
        store = get_memory_store()
        entry_id = store.remember(content)
        print(f"Remembered! (ID: {entry_id})")

    def _handle_recall(self, args: list[str]) -> None:
        """Handle :recall command.

        Args:
            args: Search query (optional)
        """
        query = " ".join(args) if args else None
        store = get_memory_store()
        entries = store.recall(query, limit=10)
        print(format_memory_list(entries))

    def _handle_forget(self, args: list[str]) -> None:
        """Handle :forget command.

        Args:
            args: Memory ID to forget
        """
        if not args:
            print("Usage: :forget <id>")
            print("Use :recall to see memory IDs")
            return

        try:
            entry_id = int(args[0])
        except ValueError:
            print(f"Invalid ID: {args[0]}")
            return

        store = get_memory_store()
        if store.forget(entry_id):
            print(f"Forgot memory {entry_id}")
        else:
            print(f"Memory {entry_id} not found")

    def _handle_ai_request(self, classified: ClassifiedInput) -> None:
        """Handle AI request.

        Args:
            classified: Classified input
        """
        request = classified.content

        # Add to history
        self._history.add(request, is_ai_request=True)

        if self._ai_handler:
            self._agent_status = AgentStatus.THINKING
            try:
                response = self._ai_handler(request)
                print(response)
                self._agent_status = AgentStatus.IDLE
                self._last_exit_code = 0
            except Exception as e:
                self._agent_status = AgentStatus.ERROR
                print(f"AI Error: {e}")
                self._last_exit_code = 1
        else:
            # AI not yet implemented
            self._show_ai_placeholder(request)

    def _handle_shell_command(self, classified: ClassifiedInput) -> None:
        """Handle shell command execution.

        Args:
            classified: Classified input
        """
        command = classified.content

        # Add to history
        self._history.add(command, is_ai_request=False)

        # Execute command using subprocess for simplicity
        # Full PTY integration comes in a later phase
        import subprocess

        try:
            result = subprocess.run(
                command,
                shell=True,
                executable=self.config.shell.backend,
            )
            self._last_exit_code = result.returncode
            self._history.add(command, is_ai_request=False, exit_code=result.returncode)
        except Exception as e:
            print(f"Error: {e}")
            self._last_exit_code = 1

    def _print_welcome(self) -> None:
        """Print welcome message."""
        print("=" * 60)
        print("  AgentSH - AI-Enhanced Terminal Shell")
        print("=" * 60)
        print()
        print("  Commands:")
        print(f"    {self.config.shell.ai_prefix}<request>  Send request to AI")
        print(f"    {self.config.shell.shell_prefix}<command>   Force shell execution")
        print("    :help               Show help")
        print("    :quit               Exit AgentSH")
        print()


    def _show_config(self) -> None:
        """Show current configuration."""
        print("\nCurrent Configuration")
        print("=" * 40)
        print(f"Shell:        {self.config.shell.backend}")
        print(f"AI Prefix:    '{self.config.shell.ai_prefix}'")
        print(f"Shell Prefix: '{self.config.shell.shell_prefix}'")
        print(f"LLM Provider: {self.config.llm.provider.value}")
        print(f"LLM Model:    {self.config.llm.model}")
        print(f"Security:     {self.config.security.mode.value}")
        print()

    def _show_history(self, args: list[str]) -> None:
        """Show command history.

        Args:
            args: Command arguments
        """
        # Parse arguments
        show_ai = True
        show_shell = True
        count = 20

        for arg in args:
            if arg == "--ai":
                show_shell = False
            elif arg == "--shell":
                show_ai = False
            elif arg.isdigit():
                count = int(arg)

        entries = self._history.get_recent(
            n=count,
            include_ai=show_ai,
            include_shell=show_shell,
        )

        print(f"\nRecent History ({len(entries)} entries)")
        print("=" * 40)
        for entry in entries:
            prefix = "[AI]" if entry.is_ai_request else "[SH]"
            time_str = entry.timestamp.strftime("%H:%M:%S")
            print(f"{prefix} {time_str} {entry.command}")
        print()

    def _show_status(self) -> None:
        """Show system status."""
        from agentsh.telemetry.health import HealthChecker

        print("\nAgentSH Status")
        print("=" * 40)

        checker = HealthChecker()
        status = checker.check_all()

        for component, result in status.items():
            icon = "✓" if result.healthy else "✗"
            print(f"{icon} {component}: {result.status.value}")
            if result.message:
                print(f"  └─ {result.message}")

        print()
        print(f"History entries: {len(self._history)}")
        print(f"Agent status: {self._agent_status.value}")
        print()

    def _reset_context(self) -> None:
        """Reset AI conversation context."""
        self._history.clear_ai_history()
        print("AI context reset.")

    def _show_ai_placeholder(self, request: str) -> None:
        """Show placeholder for AI functionality.

        Args:
            request: The AI request
        """
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " AI Response (Coming in Phase 2)".ljust(58) + "│")
        print("├" + "─" * 58 + "┤")
        print("│" + f" Request: {request[:45]}...".ljust(58) + "│")
        print("│" + " ".ljust(58) + "│")
        print("│" + " The AI agent will:".ljust(58) + "│")
        print("│" + "   • Understand your request".ljust(58) + "│")
        print("│" + "   • Plan necessary steps".ljust(58) + "│")
        print("│" + "   • Execute tools safely".ljust(58) + "│")
        print("│" + "   • Report results".ljust(58) + "│")
        print("└" + "─" * 58 + "┘")
        print()

    def stop(self) -> None:
        """Stop the shell session."""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if shell is running."""
        return self._running
