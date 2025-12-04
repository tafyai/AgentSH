"""Agent module - LLM integration and agent loop."""

from agentsh.agent.agent_loop import (
    AgentConfig,
    AgentContext,
    AgentLoop,
    AgentResult,
    StreamingAgentLoop,
)
from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    MessageRole,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agentsh.agent.prompts import build_system_prompt

__all__ = [
    # Agent Loop
    "AgentConfig",
    "AgentContext",
    "AgentLoop",
    "AgentResult",
    "StreamingAgentLoop",
    # LLM Client
    "LLMClient",
    "LLMResponse",
    "Message",
    "MessageRole",
    "StopReason",
    "ToolCall",
    "ToolDefinition",
    # Prompts
    "build_system_prompt",
]
