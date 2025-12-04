"""Workflow executor for running LangGraph workflows."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Optional

from agentsh.agent.llm_client import LLMClient
from agentsh.security.controller import SecurityController
from agentsh.telemetry.logger import get_logger, LoggerMixin
from agentsh.tools.registry import ToolRegistry
from agentsh.workflows.single_agent import create_react_graph, create_simple_react_graph
from agentsh.workflows.states import (
    AgentState,
    ToolCallRecord,
    WorkflowStatus,
    create_initial_state,
)

logger = get_logger(__name__)


@dataclass
class WorkflowResult:
    """Result of a workflow execution.

    Attributes:
        response: Final response to user
        success: Whether workflow completed successfully
        status: Workflow status
        tool_calls: List of tool calls made
        total_steps: Number of steps executed
        duration_ms: Total execution time in milliseconds
        error: Error message if failed
        final_state: Final workflow state
    """

    response: str
    success: bool = True
    status: WorkflowStatus = WorkflowStatus.COMPLETED
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    total_steps: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    final_state: Optional[AgentState] = None


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution.

    Attributes:
        event_type: Type of event
        node: Node that emitted the event
        data: Event data
        timestamp: When the event occurred
    """

    event_type: str
    node: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class WorkflowExecutor(LoggerMixin):
    """Executes LangGraph workflows with streaming support.

    The executor:
    1. Creates and compiles workflow graphs
    2. Runs workflows with state management
    3. Streams events during execution
    4. Handles errors and recovery

    Example:
        executor = WorkflowExecutor(llm_client, tool_registry)
        result = await executor.execute("List all Python files")
        print(result.response)

    With streaming:
        async for event in executor.stream("List files"):
            print(event.event_type, event.data)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        security_controller: Optional[SecurityController] = None,
        memory_manager: Optional[Any] = None,
        max_steps: int = 10,
        tool_timeout: float = 30.0,
    ) -> None:
        """Initialize the workflow executor.

        Args:
            llm_client: LLM client for inference
            tool_registry: Registry of available tools
            security_controller: Optional security controller
            memory_manager: Optional memory manager
            max_steps: Maximum steps per workflow
            tool_timeout: Timeout per tool execution
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.security_controller = security_controller
        self.memory_manager = memory_manager
        self.max_steps = max_steps
        self.tool_timeout = tool_timeout

        # Create the workflow graph
        self._graph = create_react_graph(
            llm_client=llm_client,
            tool_registry=tool_registry,
            security_controller=security_controller,
            memory_manager=memory_manager,
            tool_timeout=tool_timeout,
        )

        self.logger.info(
            "WorkflowExecutor initialized",
            tools=len(tool_registry.list_tools()),
            max_steps=max_steps,
            security_enabled=security_controller is not None,
        )

    async def execute(
        self,
        goal: str,
        context: Optional[dict[str, Any]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute a workflow for a given goal.

        Args:
            goal: User's request/goal
            context: Execution context (cwd, env, etc.)
            config: Optional LangGraph config

        Returns:
            WorkflowResult with response and metadata
        """
        start_time = datetime.now()

        self.logger.info("Executing workflow", goal=goal[:100])

        # Create initial state
        initial_state = create_initial_state(
            goal=goal,
            max_steps=self.max_steps,
            context=context or {},
        )

        try:
            # Run the graph
            config = config or {}
            final_state = await self._graph.ainvoke(initial_state, config)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Extract results
            response = final_state.get("final_result", "")
            if not response:
                # Try to get from last message
                messages = final_state.get("messages", [])
                if messages:
                    response = messages[-1].content

            success = not final_state.get("error")
            status = (
                WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
            )

            return WorkflowResult(
                response=response,
                success=success,
                status=status,
                tool_calls=final_state.get("tools_used", []),
                total_steps=final_state.get("step_count", 0),
                duration_ms=duration_ms,
                error=final_state.get("error"),
                final_state=final_state,
            )

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("Workflow execution failed", error=str(e))

            return WorkflowResult(
                response=f"Workflow failed: {str(e)}",
                success=False,
                status=WorkflowStatus.FAILED,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def stream(
        self,
        goal: str,
        context: Optional[dict[str, Any]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[WorkflowEvent]:
        """Stream workflow execution events.

        Args:
            goal: User's request/goal
            context: Execution context
            config: Optional LangGraph config

        Yields:
            WorkflowEvent for each step
        """
        self.logger.info("Streaming workflow", goal=goal[:100])

        initial_state = create_initial_state(
            goal=goal,
            max_steps=self.max_steps,
            context=context or {},
        )

        config = config or {}

        yield WorkflowEvent(
            event_type="workflow_start",
            node="executor",
            data={"goal": goal},
        )

        try:
            async for event in self._graph.astream(initial_state, config):
                # event is a dict with node name as key
                for node_name, node_output in event.items():
                    yield WorkflowEvent(
                        event_type="node_complete",
                        node=node_name,
                        data=node_output,
                    )

                    # Emit tool call events
                    if node_name == "tools":
                        for tool_record in node_output.get("tools_used", []):
                            yield WorkflowEvent(
                                event_type="tool_executed",
                                node="tools",
                                data={
                                    "name": tool_record.name,
                                    "success": tool_record.success,
                                    "duration_ms": tool_record.duration_ms,
                                },
                            )

            yield WorkflowEvent(
                event_type="workflow_complete",
                node="executor",
                data={"success": True},
            )

        except Exception as e:
            yield WorkflowEvent(
                event_type="workflow_error",
                node="executor",
                data={"error": str(e)},
            )

    async def execute_with_callbacks(
        self,
        goal: str,
        context: Optional[dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, str, bool], None]] = None,
    ) -> WorkflowResult:
        """Execute workflow with callbacks for real-time updates.

        Args:
            goal: User's request/goal
            context: Execution context
            on_token: Callback for each token (if streaming LLM)
            on_tool_call: Callback when tool is called (name, args)
            on_tool_result: Callback when tool completes (name, result, success)

        Returns:
            WorkflowResult
        """
        result = None

        async for event in self.stream(goal, context):
            if event.event_type == "tool_executed" and on_tool_result:
                on_tool_result(
                    event.data.get("name", ""),
                    event.data.get("result", ""),
                    event.data.get("success", False),
                )
            elif event.event_type == "workflow_complete":
                # Build result from final state
                pass

        # Fallback to non-streaming execution
        if result is None:
            result = await self.execute(goal, context)

        return result


class SimpleWorkflowExecutor:
    """Simplified workflow executor without security or memory.

    For basic use cases that don't need full security/memory features.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        max_steps: int = 10,
    ) -> None:
        """Initialize simple executor.

        Args:
            llm_client: LLM client
            tool_registry: Tool registry
            max_steps: Maximum steps
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_steps = max_steps

        self._graph = create_simple_react_graph(llm_client, tool_registry)

    async def execute(
        self,
        goal: str,
        context: Optional[dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute a simple workflow.

        Args:
            goal: User's request
            context: Optional context

        Returns:
            WorkflowResult
        """
        initial_state = create_initial_state(
            goal=goal,
            max_steps=self.max_steps,
            context=context or {},
        )

        try:
            final_state = await self._graph.ainvoke(initial_state)

            response = final_state.get("final_result", "")
            if not response:
                messages = final_state.get("messages", [])
                if messages:
                    response = messages[-1].content

            return WorkflowResult(
                response=response,
                success=not final_state.get("error"),
                tool_calls=final_state.get("tools_used", []),
                total_steps=final_state.get("step_count", 0),
            )

        except Exception as e:
            return WorkflowResult(
                response=f"Error: {str(e)}",
                success=False,
                error=str(e),
            )
