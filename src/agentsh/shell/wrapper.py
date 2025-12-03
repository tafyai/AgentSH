"""Shell wrapper - Main REPL interface.

This is a placeholder implementation for Phase 0.
Full implementation comes in Phase 1.
"""

from typing import TYPE_CHECKING

from agentsh.telemetry.logger import get_logger

if TYPE_CHECKING:
    from agentsh.config.schemas import AgentSHConfig

logger = get_logger(__name__)


class ShellWrapper:
    """Wraps the user's shell with AI capabilities.

    This class provides:
    - PTY-based shell wrapping
    - Input classification (shell vs AI)
    - Custom prompt rendering
    - Integration with AI agent

    Phase 0: Placeholder implementation
    Phase 1: Full implementation
    """

    def __init__(self, config: "AgentSHConfig") -> None:
        """Initialize the shell wrapper.

        Args:
            config: AgentSH configuration
        """
        self.config = config
        self._running = False
        logger.info(
            "ShellWrapper initialized",
            shell=config.shell.backend,
            ai_prefix=config.shell.ai_prefix,
        )

    def run(self) -> None:
        """Run the interactive shell REPL.

        This is the main entry point for interactive mode.
        """
        self._running = True
        logger.info("Starting interactive shell")

        print("=" * 60)
        print("AgentSH - AI-Enhanced Terminal Shell")
        print("=" * 60)
        print()
        print("Phase 0 Implementation - Basic shell functionality coming in Phase 1")
        print()
        print("Features coming soon:")
        print("  - PTY-based shell wrapping")
        print("  - Natural language to command translation")
        print("  - Multi-step task execution")
        print("  - Security with human-in-the-loop")
        print()
        print(f"Current configuration:")
        print(f"  Shell: {self.config.shell.backend}")
        print(f"  LLM Provider: {self.config.llm.provider.value}")
        print(f"  LLM Model: {self.config.llm.model}")
        print(f"  AI Prefix: '{self.config.shell.ai_prefix}'")
        print(f"  Shell Prefix: '{self.config.shell.shell_prefix}'")
        print()
        print("Type 'exit' or Ctrl+D to quit.")
        print()

        try:
            while self._running:
                try:
                    user_input = input("[AS] $ ")

                    if user_input.lower() in ("exit", "quit"):
                        break

                    if user_input.startswith(self.config.shell.ai_prefix):
                        # AI request
                        request = user_input[len(self.config.shell.ai_prefix):]
                        print(f"[AI Request] {request}")
                        print("AI functionality coming in Phase 2")
                    elif user_input.startswith(self.config.shell.shell_prefix):
                        # Force shell
                        command = user_input[len(self.config.shell.shell_prefix):]
                        print(f"[Shell] Would execute: {command}")
                        print("Shell execution coming in Phase 1")
                    else:
                        # Default handling
                        print(f"Input: {user_input}")
                        print("Input classification coming in Phase 1")

                except EOFError:
                    break

        except KeyboardInterrupt:
            print()

        self._running = False
        logger.info("Shell session ended")
        print("Goodbye!")

    def stop(self) -> None:
        """Stop the shell session."""
        self._running = False
