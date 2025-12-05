"""Tests for agent factory module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsh.agent.factory import (
    create_agent_loop,
    create_ai_handler,
    create_async_ai_handler,
    create_async_workflow_handler,
    create_llm_client,
    create_memory_manager,
    create_workflow_executor,
    create_workflow_handler,
)
from agentsh.config.schemas import (
    AgentSHConfig,
    LLMConfig,
    LLMProvider,
    ShellConfig,
)


@pytest.fixture
def mock_llm_config() -> MagicMock:
    """Create mock LLM config with api_key attribute."""
    config = MagicMock()
    config.provider = LLMProvider.ANTHROPIC
    config.api_key = "test-key"
    config.model = "claude-3-sonnet"
    config.temperature = 0.7
    config.max_tokens = 4096
    config.timeout = 60
    return config


@pytest.fixture
def anthropic_config(mock_llm_config: MagicMock) -> MagicMock:
    """Create config with Anthropic provider."""
    config = MagicMock()
    config.llm = mock_llm_config
    config.shell = MagicMock()
    config.shell.cwd = "/home/user"
    return config


@pytest.fixture
def openai_config() -> MagicMock:
    """Create config with OpenAI provider."""
    config = MagicMock()
    config.llm = MagicMock()
    config.llm.provider = LLMProvider.OPENAI
    config.llm.api_key = "test-key"
    config.llm.model = "gpt-4"
    config.llm.temperature = 0.7
    config.llm.max_tokens = 4096
    config.llm.timeout = 60
    config.shell = MagicMock()
    return config


class TestCreateLLMClient:
    """Tests for create_llm_client function."""

    def test_create_anthropic_client(self, anthropic_config: AgentSHConfig) -> None:
        """Should create Anthropic client."""
        with patch("agentsh.agent.factory.AnthropicClient") as mock_client:
            mock_client.return_value = MagicMock()
            client = create_llm_client(anthropic_config)

            mock_client.assert_called_once_with(
                api_key="test-key",
                model="claude-3-sonnet",
                timeout=60,
            )

    def test_create_openai_client(self, openai_config: AgentSHConfig) -> None:
        """Should create OpenAI client."""
        with patch("agentsh.agent.factory.OpenAIClient") as mock_client:
            mock_client.return_value = MagicMock()
            client = create_llm_client(openai_config)

            mock_client.assert_called_once_with(
                api_key="test-key",
                model="gpt-4",
                timeout=60,
            )

    def test_unsupported_provider(self) -> None:
        """Should raise error for unsupported provider."""
        config = MagicMock()
        config.llm = MagicMock()
        config.llm.provider = "unsupported"

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(config)


class TestCreateAgentLoop:
    """Tests for create_agent_loop function."""

    def test_create_agent_loop_default_registry(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should create agent loop with default registry."""
        with patch("agentsh.agent.factory.AnthropicClient") as mock_client:
            mock_client.return_value = MagicMock()
            agent_loop = create_agent_loop(anthropic_config)

            assert agent_loop is not None
            assert agent_loop.tool_registry is not None

    def test_create_agent_loop_custom_registry(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should use provided tool registry."""
        from agentsh.tools.registry import ToolRegistry

        custom_registry = ToolRegistry()
        custom_registry.register_tool(
            name="test.tool",
            handler=lambda: "result",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
        )

        with patch("agentsh.agent.factory.AnthropicClient") as mock_client:
            mock_client.return_value = MagicMock()
            agent_loop = create_agent_loop(anthropic_config, tool_registry=custom_registry)

            assert agent_loop.tool_registry is custom_registry


class TestCreateAIHandler:
    """Tests for create_ai_handler function."""

    def test_create_handler(self, anthropic_config: AgentSHConfig) -> None:
        """Should create a callable handler."""
        with patch("agentsh.agent.factory.AnthropicClient") as mock_client:
            mock_client.return_value = MagicMock()
            handler = create_ai_handler(anthropic_config)

            assert callable(handler)

    def test_handler_returns_success_response(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should return success response."""
        with patch("agentsh.agent.factory.create_agent_loop") as mock_loop:
            mock_agent = MagicMock()
            mock_result = MagicMock(success=True, response="Hello!")
            mock_agent.invoke = AsyncMock(return_value=mock_result)
            mock_loop.return_value = mock_agent

            handler = create_ai_handler(anthropic_config)
            result = handler("Say hello")

            assert result == "Hello!"

    def test_handler_returns_error_response(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should return error response on failure."""
        with patch("agentsh.agent.factory.create_agent_loop") as mock_loop:
            mock_agent = MagicMock()
            mock_result = MagicMock(
                success=False, error="Something went wrong", response="Details"
            )
            mock_agent.invoke = AsyncMock(return_value=mock_result)
            mock_loop.return_value = mock_agent

            handler = create_ai_handler(anthropic_config)
            result = handler("Test")

            assert "Error:" in result
            assert "Something went wrong" in result

    def test_handler_catches_exceptions(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should catch and return exceptions."""
        with patch("agentsh.agent.factory.create_agent_loop") as mock_loop:
            mock_agent = MagicMock()
            mock_agent.invoke = AsyncMock(side_effect=Exception("Network error"))
            mock_loop.return_value = mock_agent

            handler = create_ai_handler(anthropic_config)
            result = handler("Test")

            assert "AI Error:" in result
            assert "Network error" in result


class TestCreateAsyncAIHandler:
    """Tests for create_async_ai_handler function."""

    @pytest.mark.asyncio
    async def test_create_async_handler(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should create async handler."""
        with patch("agentsh.agent.factory.create_agent_loop") as mock_loop:
            mock_agent = MagicMock()
            mock_result = MagicMock(success=True, response="Async response")
            mock_agent.invoke = AsyncMock(return_value=mock_result)
            mock_loop.return_value = mock_agent

            handler = await create_async_ai_handler(anthropic_config)
            result = await handler("Test")

            assert result == "Async response"

    @pytest.mark.asyncio
    async def test_async_handler_error_response(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should return error in async handler."""
        with patch("agentsh.agent.factory.create_agent_loop") as mock_loop:
            mock_agent = MagicMock()
            mock_result = MagicMock(success=False, error="Error", response="Info")
            mock_agent.invoke = AsyncMock(return_value=mock_result)
            mock_loop.return_value = mock_agent

            handler = await create_async_ai_handler(anthropic_config)
            result = await handler("Test")

            assert "Error:" in result


class TestCreateMemoryManager:
    """Tests for create_memory_manager function."""

    def test_create_memory_manager(self, anthropic_config: AgentSHConfig) -> None:
        """Should create memory manager."""
        with patch("agentsh.agent.factory.MemoryManager") as mock_manager:
            mock_manager.return_value = MagicMock()
            manager = create_memory_manager(anthropic_config)

            mock_manager.assert_called_once()

    def test_create_memory_manager_custom_path(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should use custom database path."""
        with patch("agentsh.agent.factory.MemoryManager") as mock_manager:
            mock_manager.return_value = MagicMock()
            manager = create_memory_manager(anthropic_config, db_path="/tmp/memory.db")

            mock_manager.assert_called_once_with(db_path="/tmp/memory.db")


class TestCreateWorkflowExecutor:
    """Tests for create_workflow_executor function."""

    def test_create_executor(self, anthropic_config: AgentSHConfig) -> None:
        """Should create workflow executor."""
        with patch("agentsh.agent.factory.create_llm_client") as mock_create:
            with patch("agentsh.agent.factory.WorkflowExecutor") as mock_executor:
                mock_create.return_value = MagicMock()
                mock_executor.return_value = MagicMock()

                executor = create_workflow_executor(anthropic_config)

                mock_executor.assert_called_once()

    def test_create_executor_with_all_options(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should create executor with all options."""
        from agentsh.tools.registry import ToolRegistry

        tool_registry = ToolRegistry()
        security_controller = MagicMock()
        memory_manager = MagicMock()

        with patch("agentsh.agent.factory.create_llm_client") as mock_create:
            with patch("agentsh.agent.factory.WorkflowExecutor") as mock_executor:
                mock_create.return_value = MagicMock()
                mock_executor.return_value = MagicMock()

                executor = create_workflow_executor(
                    anthropic_config,
                    tool_registry=tool_registry,
                    security_controller=security_controller,
                    memory_manager=memory_manager,
                )

                call_args = mock_executor.call_args
                assert call_args.kwargs["tool_registry"] is tool_registry
                assert call_args.kwargs["security_controller"] is security_controller
                assert call_args.kwargs["memory_manager"] is memory_manager


class TestCreateWorkflowHandler:
    """Tests for create_workflow_handler function."""

    def test_create_handler(self, anthropic_config: AgentSHConfig) -> None:
        """Should create workflow handler."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_executor:
            mock_executor.return_value = MagicMock()
            handler = create_workflow_handler(anthropic_config)

            assert callable(handler)

    def test_handler_success(self, anthropic_config: AgentSHConfig) -> None:
        """Should return success response."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_create:
            mock_executor = MagicMock()
            mock_result = MagicMock(success=True, response="Workflow done")
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_executor

            handler = create_workflow_handler(anthropic_config)
            result = handler("Run workflow")

            assert result == "Workflow done"

    def test_handler_error(self, anthropic_config: AgentSHConfig) -> None:
        """Should return error response."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_create:
            mock_executor = MagicMock()
            mock_result = MagicMock(success=False, error="Failed", response="Details")
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_executor

            handler = create_workflow_handler(anthropic_config)
            result = handler("Run workflow")

            assert "Error:" in result
            assert "Failed" in result

    def test_handler_exception(self, anthropic_config: AgentSHConfig) -> None:
        """Should catch exceptions."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_create:
            mock_executor = MagicMock()
            mock_executor.execute = AsyncMock(side_effect=Exception("Workflow error"))
            mock_create.return_value = mock_executor

            handler = create_workflow_handler(anthropic_config)
            result = handler("Run workflow")

            assert "Workflow Error:" in result


class TestCreateAsyncWorkflowHandler:
    """Tests for create_async_workflow_handler function."""

    @pytest.mark.asyncio
    async def test_create_async_handler(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should create async workflow handler."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_create:
            mock_executor = MagicMock()
            mock_result = MagicMock(success=True, response="Async workflow")
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_executor

            handler = await create_async_workflow_handler(anthropic_config)
            result = await handler("Test")

            assert result == "Async workflow"

    @pytest.mark.asyncio
    async def test_async_handler_error(
        self, anthropic_config: AgentSHConfig
    ) -> None:
        """Should return error in async handler."""
        with patch("agentsh.agent.factory.create_workflow_executor") as mock_create:
            mock_executor = MagicMock()
            mock_result = MagicMock(success=False, error="Error", response="Info")
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_create.return_value = mock_executor

            handler = await create_async_workflow_handler(anthropic_config)
            result = await handler("Test")

            assert "Error:" in result
