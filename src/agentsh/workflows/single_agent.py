"""Single-agent ReAct workflow using LangGraph."""

from typing import Any, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from agentsh.agent.llm_client import LLMClient
from agentsh.security.controller import SecurityController
from agentsh.telemetry.logger import get_logger
from agentsh.tools.registry import ToolRegistry
from agentsh.workflows.edges import (
    after_approval,
    after_recovery,
    after_tools,
    should_continue,
)
from agentsh.workflows.nodes import (
    AgentNode,
    ApprovalNode,
    ErrorRecoveryNode,
    MemoryNode,
    ToolNode,
)
from agentsh.workflows.states import AgentState

logger = get_logger(__name__)


def create_react_graph(
    llm_client: LLMClient,
    tool_registry: ToolRegistry,
    security_controller: Optional[SecurityController] = None,
    memory_manager: Optional[Any] = None,
    enable_checkpointing: bool = True,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_timeout: float = 30.0,
) -> StateGraph:
    """Create a ReAct (Reasoning + Acting) workflow graph.

    The graph structure is:
    ```
    START -> agent -> [approval|tools|recovery|END]
    approval -> [tools|agent|END]
    tools -> agent
    recovery -> [agent|END]
    ```

    Args:
        llm_client: LLM client for inference
        tool_registry: Registry of available tools
        security_controller: Optional security controller
        memory_manager: Optional memory manager
        enable_checkpointing: Enable state checkpointing
        temperature: LLM sampling temperature
        max_tokens: Maximum tokens per LLM response
        tool_timeout: Timeout per tool execution

    Returns:
        Compiled StateGraph
    """
    logger.info(
        "Creating ReAct graph",
        tools=len(tool_registry.list_tools()),
        security_enabled=security_controller is not None,
        checkpointing=enable_checkpointing,
    )

    # Create nodes
    agent_node = AgentNode(
        llm_client=llm_client,
        tool_registry=tool_registry,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    tool_node = ToolNode(
        tool_registry=tool_registry,
        timeout=tool_timeout,
    )

    approval_node = ApprovalNode(
        security_controller=security_controller,
        auto_approve_safe=True,
    )

    recovery_node = ErrorRecoveryNode(max_retries=2)

    memory_node = MemoryNode(memory_manager=memory_manager)

    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("approval", approval_node)
    graph.add_node("recovery", recovery_node)
    graph.add_node("memory", memory_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Add conditional edges from agent
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "approval": "approval",
            "recovery": "recovery",
            "end": END,
        },
    )

    # Add edges from tools
    graph.add_conditional_edges(
        "tools",
        after_tools,
        {
            "agent": "agent",
            "end": END,
            "recovery": "recovery",
        },
    )

    # Add edges from approval
    graph.add_conditional_edges(
        "approval",
        after_approval,
        {
            "tools": "tools",
            "agent": "agent",
            "end": END,
        },
    )

    # Add edges from recovery
    graph.add_conditional_edges(
        "recovery",
        after_recovery,
        {
            "agent": "agent",
            "end": END,
        },
    )

    # Memory node doesn't route - it's optional
    graph.add_edge("memory", "agent")

    # Compile with checkpointing if enabled
    if enable_checkpointing:
        checkpointer = MemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        compiled = graph.compile()

    logger.info("ReAct graph compiled successfully")

    return compiled


def create_simple_react_graph(
    llm_client: LLMClient,
    tool_registry: ToolRegistry,
) -> StateGraph:
    """Create a simple ReAct graph without security or memory.

    A minimal version for basic use cases:
    ```
    START -> agent -> [tools|END]
    tools -> agent
    ```

    Args:
        llm_client: LLM client for inference
        tool_registry: Registry of available tools

    Returns:
        Compiled StateGraph
    """
    agent_node = AgentNode(
        llm_client=llm_client,
        tool_registry=tool_registry,
    )

    tool_node = ToolNode(
        tool_registry=tool_registry,
    )

    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")

    # Simple routing: tools or end
    def simple_route(state: AgentState) -> str:
        if state.get("is_terminal", False):
            return "end"
        if state.get("pending_tool_calls", []):
            return "tools"
        return "end"

    graph.add_conditional_edges(
        "agent",
        simple_route,
        {
            "tools": "tools",
            "end": END,
        },
    )

    # Tools always go back to agent
    graph.add_edge("tools", "agent")

    return graph.compile()
