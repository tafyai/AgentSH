"""Agent module - LLM integration and agent loop."""

from agentsh.agent.agent_loop import (
    AgentConfig,
    AgentContext,
    AgentLoop,
    AgentResult,
    StreamingAgentLoop,
)
from agentsh.agent.cache import (
    CacheConfig,
    CacheEntry,
    CacheKeyBuilder,
    LLMCache,
    SQLiteLLMCache,
    get_llm_cache,
    set_llm_cache,
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
from agentsh.agent.http_client import (
    ClientStats,
    HTTPClientConfig,
    HTTPClientManager,
    cleanup_http_clients,
    get_anthropic_client,
    get_http_client_manager,
    get_openai_client,
)
from agentsh.agent.resilient import (
    CircuitBreakerConfig,
    CircuitState,
    ResilienceConfig,
    ResilientLLMClient,
    RetryConfig,
    create_resilient_client,
)

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
    # Cache
    "CacheConfig",
    "CacheEntry",
    "CacheKeyBuilder",
    "LLMCache",
    "SQLiteLLMCache",
    "get_llm_cache",
    "set_llm_cache",
    # Resilience
    "CircuitBreakerConfig",
    "CircuitState",
    "ResilienceConfig",
    "ResilientLLMClient",
    "RetryConfig",
    "create_resilient_client",
    # HTTP Client
    "ClientStats",
    "HTTPClientConfig",
    "HTTPClientManager",
    "cleanup_http_clients",
    "get_anthropic_client",
    "get_http_client_manager",
    "get_openai_client",
    # Prompts
    "build_system_prompt",
]
