"""Agent Factory - Creates and configures agent instances."""

import asyncio
from typing import Optional

from agentsh.agent.agent_loop import AgentConfig, AgentContext, AgentLoop
from agentsh.agent.llm_client import LLMClient
from agentsh.agent.providers.anthropic import AnthropicClient
from agentsh.agent.providers.openai import OpenAIClient
from agentsh.config.schemas import AgentSHConfig, LLMProvider
from agentsh.telemetry.logger import get_logger
from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


def create_llm_client(config: AgentSHConfig) -> LLMClient:
    """Create an LLM client based on configuration.

    Args:
        config: AgentSH configuration

    Returns:
        Configured LLM client

    Raises:
        ValueError: If provider is not supported
    """
    if config.llm.provider == LLMProvider.ANTHROPIC:
        return AnthropicClient(
            api_key=config.llm.api_key,
            model=config.llm.model,
            timeout=config.llm.timeout,
        )
    elif config.llm.provider == LLMProvider.OPENAI:
        return OpenAIClient(
            api_key=config.llm.api_key,
            model=config.llm.model,
            timeout=config.llm.timeout,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm.provider}")


def create_agent_loop(
    config: AgentSHConfig,
    tool_registry: Optional[ToolRegistry] = None,
) -> AgentLoop:
    """Create a fully configured agent loop.

    Args:
        config: AgentSH configuration
        tool_registry: Optional pre-configured tool registry

    Returns:
        Configured AgentLoop
    """
    llm_client = create_llm_client(config)

    if tool_registry is None:
        tool_registry = ToolRegistry()
        # Register default tools (Phase 4)
        # For now, create empty registry

    agent_config = AgentConfig(
        max_steps=10,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
        timeout=30.0,
    )

    return AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        config=agent_config,
    )


def create_ai_handler(config: AgentSHConfig) -> callable:
    """Create an AI handler function for the shell wrapper.

    This creates a synchronous handler that can be used with ShellWrapper.

    Args:
        config: AgentSH configuration

    Returns:
        Handler function that takes request string and returns response
    """
    agent = create_agent_loop(config)

    def handler(request: str) -> str:
        """Handle an AI request synchronously."""
        # Run the async agent in a new event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                context = AgentContext(
                    cwd=str(config.shell.cwd) if hasattr(config.shell, 'cwd') else "",
                )
                result = loop.run_until_complete(agent.invoke(request, context))

                if result.success:
                    return result.response
                else:
                    return f"Error: {result.error}\n\n{result.response}"
            finally:
                loop.close()
        except Exception as e:
            logger.error("AI handler error", error=str(e))
            return f"AI Error: {str(e)}"

    return handler


async def create_async_ai_handler(config: AgentSHConfig) -> callable:
    """Create an async AI handler function.

    Args:
        config: AgentSH configuration

    Returns:
        Async handler function
    """
    agent = create_agent_loop(config)

    async def handler(request: str) -> str:
        """Handle an AI request asynchronously."""
        context = AgentContext()
        result = await agent.invoke(request, context)

        if result.success:
            return result.response
        else:
            return f"Error: {result.error}\n\n{result.response}"

    return handler
