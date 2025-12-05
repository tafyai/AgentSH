"""LangGraph node implementations for agent workflows."""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional

from agentsh.agent.llm_client import LLMClient, Message, ToolCall, ToolDefinition
from agentsh.agent.prompts import build_system_prompt
from agentsh.security.approval import ApprovalFlow, ApprovalResult
from agentsh.security.classifier import RiskLevel
from agentsh.security.controller import (
    SecurityContext,
    SecurityController,
    ValidationResult,
)
from agentsh.security.rbac import Role, User
from agentsh.telemetry.logger import get_logger
from agentsh.tools.base import Tool, ToolResult
from agentsh.tools.registry import ToolRegistry
from agentsh.workflows.states import (
    AgentState,
    ApprovalRequest,
    ToolCallRecord,
)

logger = get_logger(__name__)


class AgentNode:
    """Node that calls the LLM agent.

    This node:
    1. Builds the message history with system prompt
    2. Calls the LLM with available tools
    3. Parses the response for tool calls
    4. Updates state with new messages and pending tool calls
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize agent node.

        Args:
            llm_client: LLM client for inference
            tool_registry: Registry of available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute the agent node.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        logger.info(
            "Agent node executing",
            step=state.get("step_count", 0),
            goal=state.get("goal", "")[:50],
        )

        # Build tool definitions
        tool_defs = self._build_tool_definitions()

        # Build messages if empty
        messages = state.get("messages", [])
        if not messages:
            system_prompt = build_system_prompt(
                available_tools=[
                    f"{t.name}: {t.description}"
                    for t in self.tool_registry.list_tools()
                ],
                cwd=state.get("context", {}).get("cwd", ""),
                recent_history=state.get("context", {}).get("history", []),
            )
            messages = [
                Message.system(system_prompt),
                Message.user(state.get("goal", "")),
            ]

        try:
            # Call LLM
            response = await self.llm_client.invoke(
                messages=messages,
                tools=tool_defs if tool_defs else None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Update messages with assistant response
            new_messages = messages.copy()
            new_messages.append(
                Message.assistant(response.content, response.tool_calls)
            )

            # Check if we have tool calls
            if response.has_tool_calls:
                return {
                    "messages": new_messages,
                    "pending_tool_calls": response.tool_calls,
                    "step_count": state.get("step_count", 0) + 1,
                }
            else:
                # No tool calls - we're done
                return {
                    "messages": new_messages,
                    "pending_tool_calls": [],
                    "is_terminal": True,
                    "final_result": response.content,
                    "step_count": state.get("step_count", 0) + 1,
                }

        except Exception as e:
            logger.error("Agent node error", error=str(e))
            return {
                "is_terminal": True,
                "error": str(e),
                "final_result": f"Error: {str(e)}",
            }

    def _build_tool_definitions(self) -> list[ToolDefinition]:
        """Build tool definitions for LLM."""
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


class ToolNode:
    """Node that executes pending tool calls.

    This node:
    1. Gets pending tool calls from state
    2. Executes each tool
    3. Records results and updates messages
    4. Clears pending tool calls
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        timeout: float = 30.0,
    ) -> None:
        """Initialize tool node.

        Args:
            tool_registry: Registry of available tools
            timeout: Timeout per tool execution
        """
        self.tool_registry = tool_registry
        self.timeout = timeout

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute the tool node.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        pending_calls = state.get("pending_tool_calls", [])
        if not pending_calls:
            return {}

        logger.info(
            "Tool node executing",
            tool_count=len(pending_calls),
        )

        messages = state.get("messages", []).copy()
        tools_used = state.get("tools_used", []).copy()

        for tool_call in pending_calls:
            start_time = time.time()

            tool = self.tool_registry.get_tool(tool_call.name)
            if not tool:
                result_str = f"Error: Unknown tool '{tool_call.name}'"
                success = False
            else:
                try:
                    result = await self._execute_tool(tool, tool_call.arguments)
                    result_str = result.output if result.success else f"Error: {result.error}"
                    success = result.success
                except asyncio.TimeoutError:
                    result_str = f"Tool '{tool_call.name}' timed out"
                    success = False
                except Exception as e:
                    result_str = f"Tool execution error: {str(e)}"
                    success = False

            duration_ms = int((time.time() - start_time) * 1000)

            # Record the tool call
            tools_used.append(
                ToolCallRecord(
                    name=tool_call.name,
                    arguments=tool_call.arguments,
                    result=result_str,
                    success=success,
                    duration_ms=duration_ms,
                    timestamp=datetime.now(),
                    risk_level=tool.risk_level if tool else RiskLevel.SAFE,
                )
            )

            # Add tool result to messages
            messages.append(
                Message.tool_result(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=result_str,
                )
            )

            logger.debug(
                "Tool executed",
                tool=tool_call.name,
                success=success,
                duration_ms=duration_ms,
            )

        return {
            "messages": messages,
            "tools_used": tools_used,
            "pending_tool_calls": [],
        }

    async def _execute_tool(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a single tool.

        Args:
            tool: Tool to execute
            arguments: Tool arguments

        Returns:
            ToolResult
        """
        if asyncio.iscoroutinefunction(tool.handler):
            result = await asyncio.wait_for(
                tool.handler(**arguments),
                timeout=self.timeout,
            )
        else:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool.handler(**arguments)),
                timeout=self.timeout,
            )

        if isinstance(result, ToolResult):
            return result
        elif isinstance(result, str):
            return ToolResult(success=True, output=result)
        elif isinstance(result, dict):
            import json
            return ToolResult(success=True, output=json.dumps(result, indent=2))
        else:
            return ToolResult(success=True, output=str(result) if result else "")


class ApprovalNode:
    """Node that handles approval requests for high-risk operations.

    This node:
    1. Checks pending tool calls for high-risk operations
    2. Requests user approval for each
    3. Updates state based on approval result
    """

    def __init__(
        self,
        security_controller: Optional[SecurityController] = None,
        approval_flow: Optional[ApprovalFlow] = None,
        auto_approve_safe: bool = True,
    ) -> None:
        """Initialize approval node.

        Args:
            security_controller: Security controller for risk assessment
            approval_flow: Approval flow for user interaction
            auto_approve_safe: Auto-approve SAFE/LOW risk operations
        """
        self.security_controller = security_controller
        self.approval_flow = approval_flow or ApprovalFlow()
        self.auto_approve_safe = auto_approve_safe

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute the approval node.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        pending_calls = state.get("pending_tool_calls", [])
        if not pending_calls:
            return {}

        logger.info(
            "Approval node checking",
            tool_count=len(pending_calls),
        )

        approved_calls: list[ToolCall] = []
        blocked_calls: list[tuple[ToolCall, str]] = []

        for tool_call in pending_calls:
            # Check if this tool call needs approval
            needs_approval, reason = self._check_needs_approval(tool_call, state)

            if not needs_approval:
                approved_calls.append(tool_call)
                continue

            # Request approval
            approved, message = await self._request_approval(tool_call, reason, state)

            if approved:
                approved_calls.append(tool_call)
            else:
                blocked_calls.append((tool_call, message))

        # If any calls were blocked, add messages about them
        messages = state.get("messages", []).copy()
        for tool_call, reason in blocked_calls:
            messages.append(
                Message.tool_result(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=f"Blocked: {reason}",
                )
            )

        return {
            "messages": messages,
            "pending_tool_calls": approved_calls,
            "approvals_pending": [],
        }

    def _check_needs_approval(
        self,
        tool_call: ToolCall,
        state: AgentState,
    ) -> tuple[bool, str]:
        """Check if a tool call needs approval.

        Args:
            tool_call: Tool call to check
            state: Current state

        Returns:
            Tuple of (needs_approval, reason)
        """
        if not self.security_controller:
            return False, ""

        # For shell commands, check the command itself
        if tool_call.name in ("shell.run", "shell", "bash", "execute"):
            command = tool_call.arguments.get("command", "")
            if command:
                context = state.get("context", {})
                user = User(
                    id=context.get("user_id", "agent"),
                    name=context.get("user_id", "agent"),
                    role=Role.OPERATOR,
                )
                security_context = SecurityContext(
                    user=user,
                    cwd=context.get("cwd"),
                    interactive=True,
                )
                decision = self.security_controller.check(command, security_context)

                if decision.result == ValidationResult.BLOCKED:
                    return True, f"Command blocked: {decision.reason}"
                elif decision.result == ValidationResult.NEED_APPROVAL:
                    return True, decision.reason

        return False, ""

    async def _request_approval(
        self,
        tool_call: ToolCall,
        reason: str,
        state: AgentState,
    ) -> tuple[bool, str]:
        """Request user approval for a tool call.

        Args:
            tool_call: Tool call requiring approval
            reason: Reason approval is needed
            state: Current state

        Returns:
            Tuple of (approved, message)
        """
        # Build approval request
        command = tool_call.arguments.get("command", str(tool_call.arguments))
        context = state.get("context", {})

        from agentsh.security.approval import ApprovalRequest as ApprovalReq

        request = ApprovalReq(
            command=command,
            risk_level=RiskLevel.HIGH,
            reasons=[reason],
            context={
                "cwd": context.get("cwd", ""),
                "user_id": context.get("user_id", ""),
            },
        )

        response = self.approval_flow.request_approval(request)

        if response.result == ApprovalResult.APPROVED:
            return True, "Approved by user"
        elif response.result == ApprovalResult.EDITED:
            # User edited the command - update the tool call
            tool_call.arguments["command"] = response.edited_command
            return True, "Approved with edits"
        else:
            return False, f"Denied: {response.result.value}"


class MemoryNode:
    """Node that manages memory operations.

    This node:
    1. Retrieves relevant context from memory
    2. Stores completed turns in memory
    3. Updates context with relevant memories
    """

    def __init__(
        self,
        memory_manager: Optional[Any] = None,
        store_turns: bool = True,
        retrieve_context: bool = True,
        max_context_tokens: int = 2000,
    ) -> None:
        """Initialize memory node.

        Args:
            memory_manager: Memory manager instance (MemoryManager)
            store_turns: Whether to store conversation turns
            retrieve_context: Whether to retrieve relevant context
            max_context_tokens: Max tokens for retrieved context
        """
        self.memory_manager = memory_manager
        self.store_turns = store_turns
        self.retrieve_context = retrieve_context
        self.max_context_tokens = max_context_tokens

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute the memory node.

        Args:
            state: Current workflow state

        Returns:
            State updates with context enrichment
        """
        if not self.memory_manager:
            return {}

        logger.debug(
            "Memory node executing",
            step=state.get("step_count", 0),
        )

        updates: dict[str, Any] = {}

        # Store the current turn if we have messages
        if self.store_turns and state.get("messages"):
            await self._store_turn(state)

        # Retrieve relevant context for the goal
        if self.retrieve_context and state.get("goal"):
            context_updates = await self._retrieve_context(state)
            if context_updates:
                updates["context"] = {
                    **state.get("context", {}),
                    **context_updates,
                }

        return updates

    async def _store_turn(self, state: AgentState) -> None:
        """Store the current conversation turn.

        Args:
            state: Current workflow state
        """
        messages = state.get("messages", [])
        if len(messages) < 2:
            return

        # Find the last user and assistant messages
        user_input = ""
        agent_response = ""

        for msg in reversed(messages):
            role_value = msg.role.value if hasattr(msg.role, 'value') else msg.role
            if role_value == "assistant" and not agent_response:
                agent_response = msg.content or ""
            elif role_value == "user" and not user_input:
                user_input = msg.content or ""
            if user_input and agent_response:
                break

        if not user_input or not agent_response:
            return

        # Get tools used
        tools_used = [
            record.name for record in state.get("tools_used", [])
        ]

        # Store the turn
        try:
            self.memory_manager.add_turn(
                user_input=user_input,
                agent_response=agent_response,
                tools_used=tools_used,
                success=not state.get("error"),
                metadata={
                    "step_count": state.get("step_count", 0),
                    "goal": state.get("goal", ""),
                },
            )
        except Exception as e:
            logger.warning("Failed to store turn in memory", error=str(e))

    async def _retrieve_context(self, state: AgentState) -> dict[str, Any]:
        """Retrieve relevant context from memory.

        Args:
            state: Current workflow state

        Returns:
            Context updates dict
        """
        goal = state.get("goal", "")
        if not goal:
            return {}

        try:
            # Get relevant memories
            results = self.memory_manager.recall(
                query=goal,
                limit=5,
            )

            if not results:
                return {}

            # Build context string
            relevant_memories = []
            for result in results:
                memory_info = {
                    "title": result.record.title,
                    "type": result.record.type.value,
                    "score": result.score,
                    "preview": result.record.content[:200],
                }
                relevant_memories.append(memory_info)

            return {
                "relevant_memories": relevant_memories,
                "memory_context": self.memory_manager.get_context(
                    query=goal,
                    include_session=True,
                    include_relevant=True,
                    max_tokens=self.max_context_tokens,
                ),
            }

        except Exception as e:
            logger.warning("Failed to retrieve memory context", error=str(e))
            return {}


class ErrorRecoveryNode:
    """Node that handles error recovery.

    This node:
    1. Analyzes the error
    2. Attempts recovery strategies
    3. Returns to agent node or terminates
    """

    def __init__(self, max_retries: int = 2) -> None:
        """Initialize error recovery node.

        Args:
            max_retries: Maximum retry attempts
        """
        self.max_retries = max_retries
        self.retry_counts: dict[str, int] = {}

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute the error recovery node.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        error = state.get("error")
        if not error:
            return {}

        logger.info("Error recovery node executing", error=error)

        # Simple retry logic
        error_key = str(error)[:50]
        self.retry_counts[error_key] = self.retry_counts.get(error_key, 0) + 1

        if self.retry_counts[error_key] > self.max_retries:
            # Max retries exceeded - terminate
            return {
                "is_terminal": True,
                "final_result": f"Failed after {self.max_retries} retries: {error}",
            }

        # Clear error and retry
        return {
            "error": None,
            "is_terminal": False,
        }
