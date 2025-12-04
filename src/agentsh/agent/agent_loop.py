"""Agent Loop - Core reasoning and tool execution loop."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agentsh.agent.prompts import build_system_prompt
from agentsh.security.classifier import RiskLevel
from agentsh.security.controller import (
    SecurityContext,
    SecurityController,
    SecurityDecision,
    ValidationResult,
)
from agentsh.security.rbac import Role, User
from agentsh.telemetry.logger import get_logger, LoggerMixin
from agentsh.tools.base import Tool, ToolResult
from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the agent loop.

    Attributes:
        max_steps: Maximum tool execution steps per request
        temperature: LLM sampling temperature
        max_tokens: Maximum tokens per LLM response
        timeout: Timeout per tool execution in seconds
    """

    max_steps: int = 10
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: float = 30.0


@dataclass
class AgentContext:
    """Context for agent execution.

    Attributes:
        cwd: Current working directory
        env: Environment variables
        history: Recent command history
        user_id: User identifier for audit
    """

    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    user_id: str = ""


@dataclass
class AgentResult:
    """Result of an agent invocation.

    Attributes:
        response: Final text response to user
        tool_calls_made: List of tools that were called
        total_steps: Number of loop iterations
        input_tokens: Total input tokens used
        output_tokens: Total output tokens generated
        success: Whether the agent completed successfully
        error: Error message if failed
    """

    response: str
    tool_calls_made: list[str] = field(default_factory=list)
    total_steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error: Optional[str] = None


class AgentLoop(LoggerMixin):
    """Main agent reasoning and execution loop.

    The agent loop:
    1. Receives a user request
    2. Builds a conversation with system prompt
    3. Calls the LLM
    4. If LLM requests tool calls, executes them with security checks
    5. Appends tool results and loops
    6. Returns final response when done

    Example:
        agent = AgentLoop(llm_client, tool_registry, config)
        result = await agent.invoke("List all Python files")
        print(result.response)

    With security:
        security = SecurityController()
        agent = AgentLoop(llm_client, tool_registry, config, security_controller=security)
        result = await agent.invoke("List all Python files", context)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        config: Optional[AgentConfig] = None,
        security_controller: Optional[SecurityController] = None,
    ) -> None:
        """Initialize the agent loop.

        Args:
            llm_client: LLM client for inference
            tool_registry: Registry of available tools
            config: Agent configuration
            security_controller: Optional security controller for command validation
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config or AgentConfig()
        self.security_controller = security_controller

        self.logger.info(
            "AgentLoop initialized",
            provider=llm_client.provider,
            model=llm_client.model,
            max_steps=self.config.max_steps,
            security_enabled=security_controller is not None,
        )

    async def invoke(
        self,
        request: str,
        context: Optional[AgentContext] = None,
    ) -> AgentResult:
        """Invoke the agent with a user request.

        Args:
            request: User's natural language request
            context: Execution context

        Returns:
            AgentResult with response and metadata
        """
        context = context or AgentContext()

        # Build tool definitions for LLM
        tool_defs = self._build_tool_definitions()

        # Build initial messages
        system_prompt = build_system_prompt(
            available_tools=[f"{t.name}: {t.description}" for t in self.tool_registry.list_tools()],
            cwd=context.cwd,
            recent_history=context.history,
        )

        messages = [
            Message.system(system_prompt),
            Message.user(request),
        ]

        total_input_tokens = 0
        total_output_tokens = 0
        tool_calls_made: list[str] = []
        step = 0

        self.logger.info("Starting agent loop", request=request[:100])

        while step < self.config.max_steps:
            step += 1

            try:
                # Call LLM
                response = await self.llm_client.invoke(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

                total_input_tokens += response.input_tokens
                total_output_tokens += response.output_tokens

                self.logger.debug(
                    "LLM response received",
                    step=step,
                    has_tool_calls=response.has_tool_calls,
                    stop_reason=response.stop_reason.value,
                )

                # If no tool calls, we're done
                if not response.has_tool_calls:
                    return AgentResult(
                        response=response.content,
                        tool_calls_made=tool_calls_made,
                        total_steps=step,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                    )

                # Execute tool calls
                messages.append(
                    Message.assistant(response.content, response.tool_calls)
                )

                for tool_call in response.tool_calls:
                    tool_calls_made.append(tool_call.name)

                    result = await self._execute_tool(tool_call, context)

                    messages.append(
                        Message.tool_result(
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                            content=result,
                        )
                    )

            except Exception as e:
                self.logger.error("Agent loop error", step=step, error=str(e))
                return AgentResult(
                    response=f"Error during execution: {str(e)}",
                    tool_calls_made=tool_calls_made,
                    total_steps=step,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    success=False,
                    error=str(e),
                )

        # Hit max steps
        self.logger.warning("Max steps reached", steps=step)
        return AgentResult(
            response="I reached the maximum number of steps. Here's what I was able to accomplish:\n\n"
            + (messages[-1].content if messages else "No progress made."),
            tool_calls_made=tool_calls_made,
            total_steps=step,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            success=False,
            error="Max steps reached",
        )

    def _build_security_context(self, context: AgentContext) -> SecurityContext:
        """Build a SecurityContext from AgentContext.

        Args:
            context: Agent execution context

        Returns:
            SecurityContext for security checks
        """
        # Create user from context or use default
        user = User(
            id=context.user_id or "agent",
            name=context.user_id or "agent",
            role=Role.OPERATOR,  # Default to operator role
        )

        return SecurityContext(
            user=user,
            cwd=context.cwd or None,
            env=context.env or None,
            interactive=True,
        )

    def _check_command_security(
        self,
        command: str,
        context: AgentContext,
    ) -> tuple[bool, str]:
        """Check if a command is allowed by security policy.

        Args:
            command: Command to check
            context: Execution context

        Returns:
            Tuple of (allowed, message)
        """
        if not self.security_controller:
            return True, "Security checks disabled"

        security_context = self._build_security_context(context)
        decision = self.security_controller.validate_and_approve(command, security_context)

        if decision.result == ValidationResult.ALLOW:
            return True, decision.reason
        elif decision.result == ValidationResult.BLOCKED:
            return False, f"Command blocked: {decision.reason}"
        else:  # NEED_APPROVAL but we already ran validate_and_approve
            return False, f"Approval required: {decision.reason}"

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        context: AgentContext,
    ) -> str:
        """Execute a single tool call.

        Args:
            tool_call: Tool call to execute
            context: Execution context

        Returns:
            Tool result as string
        """
        tool = self.tool_registry.get_tool(tool_call.name)

        if not tool:
            return f"Error: Unknown tool '{tool_call.name}'"

        self.logger.info(
            "Executing tool",
            tool=tool_call.name,
            arguments=list(tool_call.arguments.keys()),
        )

        # Check security for shell/command execution tools
        if self.security_controller and tool.name in ("shell", "bash", "execute", "run_command"):
            command = tool_call.arguments.get("command", "")
            if command:
                allowed, message = self._check_command_security(command, context)
                if not allowed:
                    self.logger.warning(
                        "Tool execution blocked by security",
                        tool=tool_call.name,
                        command=command[:100],
                        reason=message,
                    )
                    return f"Security: {message}"

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._run_tool(tool, tool_call.arguments, context),
                timeout=self.config.timeout,
            )

            if result.success:
                return result.output or "Tool executed successfully (no output)."
            else:
                return f"Tool error: {result.error}"

        except asyncio.TimeoutError:
            return f"Tool '{tool_call.name}' timed out after {self.config.timeout}s"
        except Exception as e:
            return f"Tool execution error: {str(e)}"

    async def _run_tool(
        self,
        tool: Tool,
        arguments: dict[str, Any],
        context: AgentContext,
    ) -> ToolResult:
        """Run a tool with its arguments.

        Args:
            tool: Tool to run
            arguments: Tool arguments
            context: Execution context

        Returns:
            ToolResult
        """
        # Add context to arguments if tool expects it
        if "context" in tool.parameters.get("properties", {}):
            arguments["context"] = context

        # Execute the tool
        if asyncio.iscoroutinefunction(tool.handler):
            result = await tool.handler(**arguments)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: tool.handler(**arguments)
            )

        # Normalize result to ToolResult
        if isinstance(result, ToolResult):
            return result
        elif isinstance(result, str):
            return ToolResult(success=True, output=result)
        elif isinstance(result, dict):
            return ToolResult(success=True, output=json.dumps(result, indent=2))
        else:
            return ToolResult(success=True, output=str(result))

    def _build_tool_definitions(self) -> list[ToolDefinition]:
        """Build tool definitions for LLM.

        Returns:
            List of ToolDefinition objects
        """
        definitions = []

        for tool in self.tool_registry.list_tools():
            definitions.append(
                ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters.get("properties", {}),
                    required=tool.parameters.get("required", []),
                )
            )

        return definitions


class StreamingAgentLoop(AgentLoop):
    """Agent loop with streaming response support.

    Provides token-by-token streaming for real-time output.
    """

    async def stream(
        self,
        request: str,
        context: Optional[AgentContext] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
    ) -> AgentResult:
        """Stream agent response with callbacks.

        Args:
            request: User request
            context: Execution context
            on_token: Callback for each token
            on_tool_call: Callback when tool is called

        Returns:
            Final AgentResult
        """
        context = context or AgentContext()
        tool_defs = self._build_tool_definitions()

        system_prompt = build_system_prompt(
            available_tools=[f"{t.name}: {t.description}" for t in self.tool_registry.list_tools()],
            cwd=context.cwd,
            recent_history=context.history,
        )

        messages = [
            Message.system(system_prompt),
            Message.user(request),
        ]

        collected_response = ""
        tool_calls_made: list[str] = []
        step = 0

        while step < self.config.max_steps:
            step += 1

            # Stream tokens
            async for token in self.llm_client.stream(
                messages=messages,
                tools=tool_defs if tool_defs else None,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            ):
                collected_response += token
                if on_token:
                    on_token(token)

            # For streaming, we need to check if there are pending tool calls
            # This is simplified - real implementation would parse the stream
            # For now, just return the streamed response
            break

        return AgentResult(
            response=collected_response,
            tool_calls_made=tool_calls_made,
            total_steps=step,
        )
