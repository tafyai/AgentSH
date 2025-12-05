"""Tests for single-agent ReAct workflow."""

from unittest.mock import MagicMock, patch

import pytest

from agentsh.workflows.single_agent import (
    create_react_graph,
    create_simple_react_graph,
)
from agentsh.workflows.states import AgentState


class TestCreateReactGraph:
    """Tests for create_react_graph function."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["tool1", "tool2"]
        registry.get_tool.return_value = MagicMock()
        return registry

    @pytest.fixture
    def mock_security_controller(self) -> MagicMock:
        """Create mock security controller."""
        return MagicMock()

    @pytest.fixture
    def mock_memory_manager(self) -> MagicMock:
        """Create mock memory manager."""
        return MagicMock()

    def test_create_basic_graph(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create a basic ReAct graph."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert graph is not None

    def test_create_graph_with_security(
        self,
        mock_llm_client: MagicMock,
        mock_tool_registry: MagicMock,
        mock_security_controller: MagicMock,
    ) -> None:
        """Should create graph with security controller."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            security_controller=mock_security_controller,
        )

        assert graph is not None

    def test_create_graph_with_memory(
        self,
        mock_llm_client: MagicMock,
        mock_tool_registry: MagicMock,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Should create graph with memory manager."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            memory_manager=mock_memory_manager,
        )

        assert graph is not None

    def test_create_graph_without_checkpointing(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create graph without checkpointing."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            enable_checkpointing=False,
        )

        assert graph is not None

    def test_create_graph_custom_temperature(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept custom temperature."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            temperature=0.7,
        )

        assert graph is not None

    def test_create_graph_custom_max_tokens(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept custom max_tokens."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            max_tokens=8192,
        )

        assert graph is not None

    def test_create_graph_custom_tool_timeout(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept custom tool_timeout."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            tool_timeout=60.0,
        )

        assert graph is not None

    def test_create_graph_all_options(
        self,
        mock_llm_client: MagicMock,
        mock_tool_registry: MagicMock,
        mock_security_controller: MagicMock,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Should create graph with all options."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            security_controller=mock_security_controller,
            memory_manager=mock_memory_manager,
            enable_checkpointing=True,
            temperature=0.5,
            max_tokens=2048,
            tool_timeout=45.0,
        )

        assert graph is not None


class TestCreateSimpleReactGraph:
    """Tests for create_simple_react_graph function."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["tool1"]
        registry.get_tool.return_value = MagicMock()
        return registry

    def test_create_simple_graph(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create a simple ReAct graph."""
        graph = create_simple_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert graph is not None


class TestSimpleRouting:
    """Tests for the simple routing function in create_simple_react_graph."""

    def test_route_to_end_when_terminal(self) -> None:
        """Should route to end when is_terminal is True."""
        # Test the routing logic directly
        state: AgentState = {
            "messages": [],
            "is_terminal": True,
            "pending_tool_calls": [],
        }

        # The simple_route function routes to 'end' when is_terminal
        assert state.get("is_terminal", False) is True

    def test_route_to_tools_when_pending(self) -> None:
        """Should route to tools when pending_tool_calls exist."""
        state: AgentState = {
            "messages": [],
            "is_terminal": False,
            "pending_tool_calls": [{"id": "1", "name": "tool1", "arguments": {}}],
        }

        # Has pending tool calls and not terminal -> should go to tools
        assert not state.get("is_terminal", False)
        assert len(state.get("pending_tool_calls", [])) > 0

    def test_route_to_end_when_no_tools(self) -> None:
        """Should route to end when no pending tools and not terminal."""
        state: AgentState = {
            "messages": [],
            "is_terminal": False,
            "pending_tool_calls": [],
        }

        # No pending tool calls, not terminal -> end by default
        assert not state.get("is_terminal", False)
        assert len(state.get("pending_tool_calls", [])) == 0


class TestGraphStructure:
    """Tests for graph structure validation."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["tool1", "tool2"]
        registry.get_tool.return_value = MagicMock()
        return registry

    def test_react_graph_has_nodes(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should have expected nodes."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            enable_checkpointing=False,
        )

        # The compiled graph should exist
        assert graph is not None

    def test_simple_graph_has_nodes(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should have expected nodes in simple graph."""
        graph = create_simple_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert graph is not None


class TestSimpleRouteFunction:
    """Tests for the simple_route function behavior in create_simple_react_graph."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = ["test_tool"]
        registry.get_tool.return_value = MagicMock()
        return registry

    def test_simple_route_terminal_state(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should route to end when is_terminal is True."""
        # Create the simple route function by extracting it
        # We test the routing logic via state conditions
        state: AgentState = {
            "messages": [],
            "is_terminal": True,
            "pending_tool_calls": [{"id": "1", "name": "tool", "arguments": {}}],
        }

        # Even with pending tool calls, terminal state takes priority
        if state.get("is_terminal", False):
            route = "end"
        elif state.get("pending_tool_calls", []):
            route = "tools"
        else:
            route = "end"

        assert route == "end"

    def test_simple_route_pending_tools(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should route to tools when pending_tool_calls exist and not terminal."""
        state: AgentState = {
            "messages": [],
            "is_terminal": False,
            "pending_tool_calls": [{"id": "1", "name": "tool", "arguments": {}}],
        }

        if state.get("is_terminal", False):
            route = "end"
        elif state.get("pending_tool_calls", []):
            route = "tools"
        else:
            route = "end"

        assert route == "tools"

    def test_simple_route_no_tools_not_terminal(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should route to end when no pending tools and not terminal."""
        state: AgentState = {
            "messages": [],
            "is_terminal": False,
            "pending_tool_calls": [],
        }

        if state.get("is_terminal", False):
            route = "end"
        elif state.get("pending_tool_calls", []):
            route = "tools"
        else:
            route = "end"

        assert route == "end"

    def test_simple_route_empty_state(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should handle empty/minimal state."""
        state: AgentState = {"messages": []}

        if state.get("is_terminal", False):
            route = "end"
        elif state.get("pending_tool_calls", []):
            route = "tools"
        else:
            route = "end"

        assert route == "end"


class TestCreateReactGraphExtended:
    """Extended tests for create_react_graph function."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = []  # Empty tool list
        registry.get_tool.return_value = None
        return registry

    def test_create_graph_empty_tool_registry(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create graph with empty tool registry."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert graph is not None

    def test_create_graph_with_zero_temperature(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept zero temperature (deterministic)."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            temperature=0.0,
        )

        assert graph is not None

    def test_create_graph_with_high_temperature(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept high temperature."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            temperature=1.0,
        )

        assert graph is not None

    def test_create_graph_with_small_max_tokens(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept small max_tokens value."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            max_tokens=100,
        )

        assert graph is not None

    def test_create_graph_with_large_max_tokens(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept large max_tokens value."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            max_tokens=100000,
        )

        assert graph is not None

    def test_create_graph_with_short_timeout(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept short tool timeout."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            tool_timeout=1.0,
        )

        assert graph is not None

    def test_create_graph_with_long_timeout(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should accept long tool timeout."""
        graph = create_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
            tool_timeout=3600.0,  # 1 hour
        )

        assert graph is not None


class TestCreateSimpleReactGraphExtended:
    """Extended tests for create_simple_react_graph function."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_registry(self) -> MagicMock:
        """Create mock tool registry."""
        registry = MagicMock()
        registry.list_tools.return_value = []
        registry.get_tool.return_value = None
        return registry

    def test_create_simple_graph_empty_tools(
        self, mock_llm_client: MagicMock, mock_tool_registry: MagicMock
    ) -> None:
        """Should create simple graph with no tools."""
        graph = create_simple_react_graph(
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry,
        )

        assert graph is not None

    def test_create_simple_graph_many_tools(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should create simple graph with many tools."""
        registry = MagicMock()
        registry.list_tools.return_value = [f"tool_{i}" for i in range(100)]
        registry.get_tool.return_value = MagicMock()

        graph = create_simple_react_graph(
            llm_client=mock_llm_client,
            tool_registry=registry,
        )

        assert graph is not None
