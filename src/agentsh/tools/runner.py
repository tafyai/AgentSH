"""Tool Runner - Executes tools with security, timeout, and retry handling."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

from agentsh.security.classifier import RiskLevel as SecurityRiskLevel
from agentsh.security.controller import (
    SecurityContext,
    SecurityController,
    ValidationResult,
)
from agentsh.security.rbac import Role, User
from agentsh.telemetry.logger import get_logger, LoggerMixin
from agentsh.tools.base import Tool, ToolResult
from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


@dataclass
class ExecutionContext:
    """Context for tool execution.

    Attributes:
        user_id: User identifier
        cwd: Current working directory
        env: Environment variables
        device_id: Target device (for remote execution)
        interactive: Whether running interactively
    """

    user_id: str = ""
    cwd: str = ""
    env: dict[str, str] | None = None
    device_id: str | None = None
    interactive: bool = True


class ToolRunner(LoggerMixin):
    """Executes tools with security checks, timeouts, and retries.

    The ToolRunner:
    1. Validates tool arguments
    2. Checks security via SecurityController
    3. Executes tool with timeout
    4. Handles retries on failure
    5. Returns formatted results

    Example:
        runner = ToolRunner(registry, security_controller)
        result = await runner.execute(
            "shell.run",
            {"command": "ls -la"},
            context
        )
    """

    def __init__(
        self,
        registry: ToolRegistry,
        security_controller: Optional[SecurityController] = None,
        default_timeout: float = 30.0,
    ) -> None:
        """Initialize the tool runner.

        Args:
            registry: Tool registry
            security_controller: Optional security controller
            default_timeout: Default timeout in seconds
        """
        self.registry = registry
        self.security_controller = security_controller
        self.default_timeout = default_timeout

        self.logger.info(
            "ToolRunner initialized",
            security_enabled=security_controller is not None,
            default_timeout=default_timeout,
        )

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ToolResult:
        """Execute a tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            context: Execution context

        Returns:
            ToolResult with output or error
        """
        context = context or ExecutionContext()
        start_time = time.time()

        # Get the tool
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        self.logger.info(
            "Executing tool",
            tool=tool_name,
            arguments=list(arguments.keys()),
            risk_level=tool.risk_level.value,
        )

        # Validate arguments
        validation_error = self._validate_arguments(tool, arguments)
        if validation_error:
            return ToolResult(
                success=False,
                error=validation_error,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # Check security for command-executing tools
        if self.security_controller and self._is_command_tool(tool_name):
            command = arguments.get("command", "")
            if command:
                security_result = self._check_security(command, context)
                if not security_result.success:
                    return security_result

        # Execute with retries
        timeout = tool.timeout_seconds or self.default_timeout
        last_error = None

        for attempt in range(tool.max_retries + 1):
            try:
                result = await self._execute_with_timeout(
                    tool, arguments, timeout
                )

                # Calculate duration
                result.duration_ms = int((time.time() - start_time) * 1000)

                if result.success:
                    self.logger.debug(
                        "Tool executed successfully",
                        tool=tool_name,
                        duration_ms=result.duration_ms,
                    )
                    return result

                # If failed, save error for potential retry
                last_error = result.error

                if attempt < tool.max_retries:
                    self.logger.debug(
                        "Tool execution failed, retrying",
                        tool=tool_name,
                        attempt=attempt + 1,
                        error=result.error,
                    )
                    # Brief delay before retry
                    await asyncio.sleep(0.5 * (attempt + 1))

            except asyncio.TimeoutError:
                last_error = f"Tool timed out after {timeout}s"
                self.logger.warning(
                    "Tool execution timed out",
                    tool=tool_name,
                    timeout=timeout,
                )
                break

            except Exception as e:
                last_error = str(e)
                self.logger.error(
                    "Tool execution error",
                    tool=tool_name,
                    error=str(e),
                )
                if attempt >= tool.max_retries:
                    break

        # All retries exhausted
        return ToolResult(
            success=False,
            error=last_error or "Unknown error",
            duration_ms=int((time.time() - start_time) * 1000),
        )

    def _validate_arguments(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> Optional[str]:
        """Validate tool arguments against schema.

        Args:
            tool: Tool definition
            arguments: Arguments to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        schema = tool.parameters

        # Check required parameters
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for param in required:
            if param not in arguments:
                return f"Missing required parameter: {param}"

        # Basic type checking
        for param, value in arguments.items():
            if param in properties:
                expected_type = properties[param].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    return f"Invalid type for '{param}': expected {expected_type}"

        return None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON schema type.

        Args:
            value: Value to check
            expected_type: Expected type string

        Returns:
            True if type matches
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_map.get(expected_type)
        if python_type is None:
            return True  # Unknown type, accept any

        return isinstance(value, python_type)

    def _is_command_tool(self, tool_name: str) -> bool:
        """Check if tool executes shell commands.

        Args:
            tool_name: Tool name

        Returns:
            True if tool can execute commands
        """
        command_tools = {
            "shell.run",
            "shell.execute",
            "bash",
            "execute",
            "run_command",
        }
        return tool_name in command_tools

    def _check_security(
        self,
        command: str,
        context: ExecutionContext,
    ) -> ToolResult:
        """Check if command is allowed by security policy.

        Args:
            command: Command to check
            context: Execution context

        Returns:
            ToolResult with success=True if allowed, error otherwise
        """
        if not self.security_controller:
            return ToolResult(success=True)

        # Build security context
        user = User(
            id=context.user_id or "agent",
            name=context.user_id or "agent",
            role=Role.OPERATOR,
        )

        security_context = SecurityContext(
            user=user,
            device_id=context.device_id,
            cwd=context.cwd,
            env=context.env,
            interactive=context.interactive,
        )

        # Check with security controller
        decision = self.security_controller.validate_and_approve(
            command, security_context
        )

        if decision.result == ValidationResult.ALLOW:
            return ToolResult(success=True)
        elif decision.result == ValidationResult.BLOCKED:
            return ToolResult(
                success=False,
                error=f"Security: {decision.reason}",
            )
        else:
            return ToolResult(
                success=False,
                error=f"Approval required: {decision.reason}",
            )

    async def _execute_with_timeout(
        self,
        tool: Tool,
        arguments: dict[str, Any],
        timeout: float,
    ) -> ToolResult:
        """Execute a tool with timeout.

        Args:
            tool: Tool to execute
            arguments: Arguments to pass
            timeout: Timeout in seconds

        Returns:
            ToolResult from tool execution
        """
        # Check if handler is async
        if asyncio.iscoroutinefunction(tool.handler):
            result = await asyncio.wait_for(
                tool.handler(**arguments),
                timeout=timeout,
            )
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool.handler(**arguments)),
                timeout=timeout,
            )

        # Normalize result to ToolResult
        if isinstance(result, ToolResult):
            return result
        elif isinstance(result, str):
            return ToolResult(success=True, output=result)
        elif isinstance(result, dict):
            # Check for error key
            if "error" in result:
                return ToolResult(
                    success=False,
                    error=result["error"],
                    output=result.get("output", ""),
                )
            import json
            return ToolResult(success=True, output=json.dumps(result, indent=2))
        elif result is None:
            return ToolResult(success=True, output="")
        else:
            return ToolResult(success=True, output=str(result))

    async def execute_batch(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        context: Optional[ExecutionContext] = None,
        parallel: bool = False,
    ) -> list[ToolResult]:
        """Execute multiple tool calls.

        Args:
            calls: List of (tool_name, arguments) tuples
            context: Execution context
            parallel: Whether to execute in parallel

        Returns:
            List of ToolResults
        """
        if parallel:
            tasks = [
                self.execute(name, args, context)
                for name, args in calls
            ]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for name, args in calls:
                result = await self.execute(name, args, context)
                results.append(result)
            return results
