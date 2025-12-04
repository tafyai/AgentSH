"""Shell toolset - Execute shell commands."""

import asyncio
import os
import shlex
import subprocess
from typing import TYPE_CHECKING, Any, Optional

from agentsh.plugins.base import Toolset
from agentsh.tools.base import RiskLevel, ToolResult

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry


class ShellToolset(Toolset):
    """Provides shell command execution tools.

    Tools:
    - shell.run: Execute a shell command
    - shell.explain: Explain what a command does
    - shell.which: Find location of an executable
    - shell.env: Get environment variable value
    """

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute shell commands and interact with the system"

    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register shell tools."""
        registry.register_tool(
            name="shell.run",
            handler=self.run_command,
            description="Execute a shell command and return the output. Use for running system commands, scripts, or interacting with the shell.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the command",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 30,
                    },
                },
                "required": ["command"],
            },
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=False,
            timeout_seconds=60,
            plugin_name=self.name,
            examples=[
                "shell.run(command='ls -la')",
                "shell.run(command='git status', cwd='/path/to/repo')",
            ],
        )

        registry.register_tool(
            name="shell.explain",
            handler=self.explain_command,
            description="Explain what a shell command does without executing it. Use to understand unfamiliar commands.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to explain",
                    },
                },
                "required": ["command"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="shell.which",
            handler=self.which,
            description="Find the location of an executable in PATH.",
            parameters={
                "type": "object",
                "properties": {
                    "program": {
                        "type": "string",
                        "description": "The program name to locate",
                    },
                },
                "required": ["program"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="shell.env",
            handler=self.get_env,
            description="Get the value of an environment variable.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The environment variable name",
                    },
                },
                "required": ["name"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> ToolResult:
        """Execute a shell command.

        Args:
            command: Shell command to execute
            cwd: Working directory (optional)
            timeout: Timeout in seconds

        Returns:
            ToolResult with command output
        """
        if not command.strip():
            return ToolResult(success=False, error="Empty command")

        # Resolve working directory
        working_dir = cwd or os.getcwd()
        if not os.path.isdir(working_dir):
            return ToolResult(
                success=False,
                error=f"Working directory does not exist: {working_dir}",
            )

        try:
            # Run command with subprocess
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            # Combine output
            output = stdout_str
            if stderr_str:
                if output:
                    output += f"\n\nSTDERR:\n{stderr_str}"
                else:
                    output = f"STDERR:\n{stderr_str}"

            # Check exit code
            if proc.returncode == 0:
                return ToolResult(
                    success=True,
                    output=output or "(no output)",
                    exit_code=0,
                )
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {proc.returncode}",
                    exit_code=proc.returncode,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute command: {str(e)}",
            )

    def explain_command(self, command: str) -> ToolResult:
        """Explain what a shell command does.

        Args:
            command: Command to explain

        Returns:
            ToolResult with explanation
        """
        if not command.strip():
            return ToolResult(success=False, error="Empty command")

        # Parse the command
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return ToolResult(
                success=False,
                error=f"Invalid command syntax: {e}",
            )

        if not parts:
            return ToolResult(success=False, error="No command found")

        # Get the base command
        base_cmd = parts[0]

        # Common command explanations
        explanations = {
            "ls": "List directory contents",
            "cd": "Change directory",
            "pwd": "Print working directory",
            "cat": "Concatenate and display file contents",
            "echo": "Display a line of text",
            "mkdir": "Create a directory",
            "rm": "Remove files or directories",
            "cp": "Copy files or directories",
            "mv": "Move or rename files",
            "chmod": "Change file permissions",
            "chown": "Change file ownership",
            "grep": "Search for patterns in files",
            "find": "Search for files",
            "sed": "Stream editor for text transformation",
            "awk": "Pattern scanning and processing",
            "curl": "Transfer data from/to a server",
            "wget": "Download files from the web",
            "tar": "Archive files",
            "gzip": "Compress files",
            "ssh": "Secure shell remote login",
            "scp": "Secure copy between hosts",
            "git": "Version control system",
            "docker": "Container management",
            "pip": "Python package installer",
            "npm": "Node.js package manager",
            "python": "Run Python interpreter",
            "node": "Run Node.js",
            "make": "Build automation tool",
            "sudo": "Execute command as superuser",
            "kill": "Terminate processes",
            "ps": "Report process status",
            "top": "Display system processes",
            "df": "Report disk space usage",
            "du": "Estimate file space usage",
            "head": "Output the first part of files",
            "tail": "Output the last part of files",
            "less": "View file contents with scrolling",
            "more": "View file contents page by page",
            "touch": "Create empty file or update timestamps",
            "ln": "Create links between files",
            "wc": "Word, line, character count",
            "sort": "Sort lines of text",
            "uniq": "Report or omit repeated lines",
            "cut": "Remove sections from lines",
            "paste": "Merge lines of files",
            "diff": "Compare files line by line",
            "patch": "Apply a diff file to an original",
            "xargs": "Build and execute command lines",
            "tee": "Read from stdin and write to stdout and files",
        }

        base_explanation = explanations.get(
            base_cmd,
            f"Execute the '{base_cmd}' command",
        )

        # Analyze flags and arguments
        flags = [p for p in parts[1:] if p.startswith("-")]
        args = [p for p in parts[1:] if not p.startswith("-")]

        explanation = f"Command: {base_cmd}\n"
        explanation += f"Description: {base_explanation}\n"

        if flags:
            explanation += f"Flags: {', '.join(flags)}\n"

        if args:
            explanation += f"Arguments: {', '.join(args)}\n"

        return ToolResult(success=True, output=explanation)

    def which(self, program: str) -> ToolResult:
        """Find the location of an executable.

        Args:
            program: Program name to locate

        Returns:
            ToolResult with path or error
        """
        if not program.strip():
            return ToolResult(success=False, error="Empty program name")

        try:
            result = subprocess.run(
                ["which", program],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout.strip())
            else:
                return ToolResult(
                    success=False,
                    error=f"Program '{program}' not found in PATH",
                )

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Command timed out")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to locate program: {str(e)}",
            )

    def get_env(self, name: str) -> ToolResult:
        """Get an environment variable.

        Args:
            name: Variable name

        Returns:
            ToolResult with value or error
        """
        if not name.strip():
            return ToolResult(success=False, error="Empty variable name")

        value = os.environ.get(name)

        if value is not None:
            return ToolResult(success=True, output=value)
        else:
            return ToolResult(
                success=False,
                error=f"Environment variable '{name}' is not set",
            )
