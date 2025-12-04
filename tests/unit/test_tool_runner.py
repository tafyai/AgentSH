"""Tests for tool runner."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from agentsh.tools.base import RiskLevel, ToolResult
from agentsh.tools.registry import ToolRegistry
from agentsh.tools.runner import ExecutionContext, ToolRunner


class TestToolRunner:
    """Test tool runner execution."""

    @pytest.fixture
    def runner(self, tool_registry: ToolRegistry) -> ToolRunner:
        """Create a tool runner with test registry."""
        return ToolRunner(tool_registry)

    def test_execute_unknown_tool(self, runner: ToolRunner) -> None:
        """Should return error for unknown tool."""
        result = asyncio.run(runner.execute("unknown.tool", {}))

        assert not result.success
        assert "Unknown tool" in result.error

    def test_execute_sync_tool(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should execute synchronous tool."""
        def add_numbers(a: int, b: int) -> ToolResult:
            return ToolResult(success=True, output=str(a + b))

        tool_registry.register_tool(
            name="math.add",
            handler=add_numbers,
            description="Add two numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        )

        result = asyncio.run(runner.execute("math.add", {"a": 2, "b": 3}))

        assert result.success
        assert result.output == "5"

    def test_execute_async_tool(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should execute asynchronous tool."""
        async def async_greet(name: str) -> ToolResult:
            await asyncio.sleep(0.01)
            return ToolResult(success=True, output=f"Hello, {name}!")

        tool_registry.register_tool(
            name="greet",
            handler=async_greet,
            description="Greet someone",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )

        result = asyncio.run(runner.execute("greet", {"name": "World"}))

        assert result.success
        assert result.output == "Hello, World!"

    def test_missing_required_param(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate required parameters."""
        tool_registry.register_tool(
            name="test.required",
            handler=lambda x: x,
            description="Test",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )

        result = asyncio.run(runner.execute("test.required", {}))

        assert not result.success
        assert "Missing required parameter" in result.error

    def test_wrong_param_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate parameter types."""
        tool_registry.register_tool(
            name="test.type",
            handler=lambda x: x,
            description="Test",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        )

        result = asyncio.run(runner.execute("test.type", {"x": "not an int"}))

        assert not result.success
        assert "Invalid type" in result.error

    def test_tool_timeout(
        self, tool_registry: ToolRegistry
    ) -> None:
        """Should handle tool timeout."""
        async def slow_tool() -> ToolResult:
            await asyncio.sleep(10)
            return ToolResult(success=True, output="done")

        tool_registry.register_tool(
            name="slow",
            handler=slow_tool,
            description="Slow tool",
            parameters={"type": "object", "properties": {}},
            timeout_seconds=0.1,
        )

        runner = ToolRunner(tool_registry, default_timeout=0.1)
        result = asyncio.run(runner.execute("slow", {}))

        assert not result.success
        assert "timed out" in result.error.lower()

    def test_tool_string_return(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should handle string return from tool."""
        tool_registry.register_tool(
            name="simple",
            handler=lambda: "simple output",
            description="Simple",
            parameters={"type": "object", "properties": {}},
        )

        result = asyncio.run(runner.execute("simple", {}))

        assert result.success
        assert result.output == "simple output"

    def test_tool_dict_return(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should handle dict return from tool."""
        tool_registry.register_tool(
            name="dict_tool",
            handler=lambda: {"key": "value"},
            description="Dict return",
            parameters={"type": "object", "properties": {}},
        )

        result = asyncio.run(runner.execute("dict_tool", {}))

        assert result.success
        assert "key" in result.output
        assert "value" in result.output

    def test_tool_none_return(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should handle None return from tool."""
        tool_registry.register_tool(
            name="none_tool",
            handler=lambda: None,
            description="None return",
            parameters={"type": "object", "properties": {}},
        )

        result = asyncio.run(runner.execute("none_tool", {}))

        assert result.success
        assert result.output == ""

    def test_execute_batch_sequential(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should execute batch sequentially."""
        tool_registry.register_tool(
            name="echo",
            handler=lambda msg: ToolResult(success=True, output=msg),
            description="Echo",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
        )

        calls = [
            ("echo", {"msg": "first"}),
            ("echo", {"msg": "second"}),
        ]

        results = asyncio.run(runner.execute_batch(calls, parallel=False))

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].output == "first"
        assert results[1].output == "second"

    def test_execute_batch_parallel(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should execute batch in parallel."""
        tool_registry.register_tool(
            name="echo",
            handler=lambda msg: ToolResult(success=True, output=msg),
            description="Echo",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
        )

        calls = [
            ("echo", {"msg": "a"}),
            ("echo", {"msg": "b"}),
            ("echo", {"msg": "c"}),
        ]

        results = asyncio.run(runner.execute_batch(calls, parallel=True))

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_execution_context(self) -> None:
        """Should create execution context with defaults."""
        ctx = ExecutionContext()

        assert ctx.user_id == ""
        assert ctx.cwd == ""
        assert ctx.env is None
        assert ctx.device_id is None
        assert ctx.interactive is True

    def test_result_includes_duration(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should include execution duration in result."""
        tool_registry.register_tool(
            name="quick",
            handler=lambda: ToolResult(success=True, output="done"),
            description="Quick",
            parameters={"type": "object", "properties": {}},
        )

        result = asyncio.run(runner.execute("quick", {}))

        assert result.duration_ms is not None
        assert result.duration_ms >= 0
