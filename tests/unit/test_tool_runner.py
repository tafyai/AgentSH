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


class TestToolRunnerTypeValidation:
    """Test type validation in tool runner."""

    @pytest.fixture
    def runner(self, tool_registry: ToolRegistry) -> ToolRunner:
        """Create a tool runner with test registry."""
        return ToolRunner(tool_registry)

    def test_validate_string_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate string type."""
        tool_registry.register_tool(
            name="test.string",
            handler=lambda x: ToolResult(success=True, output=x),
            description="Test string",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )

        # Valid string
        result = asyncio.run(runner.execute("test.string", {"x": "hello"}))
        assert result.success

        # Invalid type
        result = asyncio.run(runner.execute("test.string", {"x": 123}))
        assert not result.success
        assert "Invalid type" in result.error

    def test_validate_number_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate number type (int or float)."""
        tool_registry.register_tool(
            name="test.number",
            handler=lambda x: ToolResult(success=True, output=str(x)),
            description="Test number",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
        )

        # Valid integer
        result = asyncio.run(runner.execute("test.number", {"x": 42}))
        assert result.success

        # Valid float
        result = asyncio.run(runner.execute("test.number", {"x": 3.14}))
        assert result.success

        # Invalid type
        result = asyncio.run(runner.execute("test.number", {"x": "not a number"}))
        assert not result.success

    def test_validate_boolean_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate boolean type."""
        tool_registry.register_tool(
            name="test.bool",
            handler=lambda x: ToolResult(success=True, output=str(x)),
            description="Test boolean",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "boolean"}},
                "required": ["x"],
            },
        )

        # Valid boolean
        result = asyncio.run(runner.execute("test.bool", {"x": True}))
        assert result.success

        result = asyncio.run(runner.execute("test.bool", {"x": False}))
        assert result.success

        # Invalid type
        result = asyncio.run(runner.execute("test.bool", {"x": "true"}))
        assert not result.success

    def test_validate_array_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate array type."""
        tool_registry.register_tool(
            name="test.array",
            handler=lambda x: ToolResult(success=True, output=str(len(x))),
            description="Test array",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "array"}},
                "required": ["x"],
            },
        )

        # Valid array
        result = asyncio.run(runner.execute("test.array", {"x": [1, 2, 3]}))
        assert result.success
        assert result.output == "3"

        # Invalid type
        result = asyncio.run(runner.execute("test.array", {"x": "not an array"}))
        assert not result.success

    def test_validate_object_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should validate object type."""
        tool_registry.register_tool(
            name="test.object",
            handler=lambda x: ToolResult(success=True, output=str(x)),
            description="Test object",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "object"}},
                "required": ["x"],
            },
        )

        # Valid object
        result = asyncio.run(runner.execute("test.object", {"x": {"key": "value"}}))
        assert result.success

        # Invalid type
        result = asyncio.run(runner.execute("test.object", {"x": [1, 2, 3]}))
        assert not result.success

    def test_unknown_type_accepts_any(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should accept any value for unknown type."""
        tool_registry.register_tool(
            name="test.unknown",
            handler=lambda x: ToolResult(success=True, output=str(x)),
            description="Test unknown type",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "custom_type"}},
                "required": ["x"],
            },
        )

        # Should accept any value
        result = asyncio.run(runner.execute("test.unknown", {"x": "anything"}))
        assert result.success

        result = asyncio.run(runner.execute("test.unknown", {"x": 123}))
        assert result.success


class TestToolRunnerSecurity:
    """Test security controller integration."""

    @pytest.fixture
    def mock_risk_assessment(self) -> MagicMock:
        """Create a mock risk assessment."""
        from agentsh.security.classifier import CommandRiskAssessment, RiskLevel
        return CommandRiskAssessment(
            command="ls -la",
            risk_level=RiskLevel.SAFE,
        )

    @pytest.fixture
    def mock_security_controller(self, mock_risk_assessment: MagicMock) -> MagicMock:
        """Create a mock security controller."""
        from agentsh.security.controller import SecurityDecision, ValidationResult

        controller = MagicMock()
        # Default to allowing commands
        controller.validate_and_approve.return_value = SecurityDecision(
            result=ValidationResult.ALLOW,
            command="ls -la",
            risk_assessment=mock_risk_assessment,
            reason="",
        )
        return controller

    def test_security_check_allowed(
        self,
        tool_registry: ToolRegistry,
        mock_security_controller: MagicMock,
        mock_risk_assessment: MagicMock,
    ) -> None:
        """Should allow commands that pass security check."""
        from agentsh.security.controller import SecurityDecision, ValidationResult

        mock_security_controller.validate_and_approve.return_value = SecurityDecision(
            result=ValidationResult.ALLOW,
            command="ls -la",
            risk_assessment=mock_risk_assessment,
            reason="",
        )

        runner = ToolRunner(tool_registry, security_controller=mock_security_controller)

        tool_registry.register_tool(
            name="shell.run",
            handler=lambda command: ToolResult(success=True, output="executed"),
            description="Run shell command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

        result = asyncio.run(runner.execute("shell.run", {"command": "ls -la"}))

        assert result.success
        mock_security_controller.validate_and_approve.assert_called_once()

    def test_security_check_blocked(
        self,
        tool_registry: ToolRegistry,
        mock_security_controller: MagicMock,
        mock_risk_assessment: MagicMock,
    ) -> None:
        """Should block commands that fail security check."""
        from agentsh.security.controller import SecurityDecision, ValidationResult

        mock_security_controller.validate_and_approve.return_value = SecurityDecision(
            result=ValidationResult.BLOCKED,
            command="rm -rf /",
            risk_assessment=mock_risk_assessment,
            reason="Command contains dangerous pattern",
        )

        runner = ToolRunner(tool_registry, security_controller=mock_security_controller)

        tool_registry.register_tool(
            name="shell.run",
            handler=lambda command: ToolResult(success=True, output="executed"),
            description="Run shell command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

        result = asyncio.run(runner.execute("shell.run", {"command": "rm -rf /"}))

        assert not result.success
        assert "Security" in result.error
        assert "dangerous pattern" in result.error

    def test_security_check_requires_approval(
        self,
        tool_registry: ToolRegistry,
        mock_security_controller: MagicMock,
        mock_risk_assessment: MagicMock,
    ) -> None:
        """Should require approval for certain commands."""
        from agentsh.security.controller import SecurityDecision, ValidationResult

        mock_security_controller.validate_and_approve.return_value = SecurityDecision(
            result=ValidationResult.NEED_APPROVAL,
            command="sudo apt update",
            risk_assessment=mock_risk_assessment,
            reason="Elevated privileges required",
        )

        runner = ToolRunner(tool_registry, security_controller=mock_security_controller)

        tool_registry.register_tool(
            name="shell.run",
            handler=lambda command: ToolResult(success=True, output="executed"),
            description="Run shell command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

        result = asyncio.run(runner.execute("shell.run", {"command": "sudo apt update"}))

        assert not result.success
        assert "Approval required" in result.error

    def test_security_not_checked_for_non_command_tools(
        self,
        tool_registry: ToolRegistry,
        mock_security_controller: MagicMock,
    ) -> None:
        """Should not check security for non-command tools."""
        runner = ToolRunner(tool_registry, security_controller=mock_security_controller)

        tool_registry.register_tool(
            name="math.add",
            handler=lambda a, b: ToolResult(success=True, output=str(a + b)),
            description="Add numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        )

        result = asyncio.run(runner.execute("math.add", {"a": 1, "b": 2}))

        assert result.success
        mock_security_controller.validate_and_approve.assert_not_called()

    def test_no_security_check_without_controller(
        self, tool_registry: ToolRegistry
    ) -> None:
        """Should skip security check when no controller is set."""
        runner = ToolRunner(tool_registry, security_controller=None)

        tool_registry.register_tool(
            name="shell.run",
            handler=lambda command: ToolResult(success=True, output="executed"),
            description="Run shell command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

        result = asyncio.run(runner.execute("shell.run", {"command": "ls -la"}))

        assert result.success


class TestToolRunnerRetries:
    """Test retry logic in tool runner."""

    @pytest.fixture
    def runner(self, tool_registry: ToolRegistry) -> ToolRunner:
        """Create a tool runner with test registry."""
        return ToolRunner(tool_registry)

    def test_retry_on_failure(self, tool_registry: ToolRegistry) -> None:
        """Should retry failed executions."""
        attempt_count = 0

        def flaky_tool() -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                return ToolResult(success=False, error="Temporary failure")
            return ToolResult(success=True, output="success")

        tool_registry.register_tool(
            name="flaky",
            handler=flaky_tool,
            description="Flaky tool",
            parameters={"type": "object", "properties": {}},
            max_retries=3,
        )

        runner = ToolRunner(tool_registry)
        result = asyncio.run(runner.execute("flaky", {}))

        assert result.success
        assert attempt_count == 3

    def test_no_retry_on_success(self, tool_registry: ToolRegistry) -> None:
        """Should not retry successful executions."""
        attempt_count = 0

        def reliable_tool() -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            return ToolResult(success=True, output="done")

        tool_registry.register_tool(
            name="reliable",
            handler=reliable_tool,
            description="Reliable tool",
            parameters={"type": "object", "properties": {}},
            max_retries=3,
        )

        runner = ToolRunner(tool_registry)
        result = asyncio.run(runner.execute("reliable", {}))

        assert result.success
        assert attempt_count == 1

    def test_max_retries_exhausted(self, tool_registry: ToolRegistry) -> None:
        """Should fail after max retries exhausted."""
        attempt_count = 0

        def always_fail() -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            return ToolResult(success=False, error="Always fails")

        tool_registry.register_tool(
            name="failing",
            handler=always_fail,
            description="Always failing tool",
            parameters={"type": "object", "properties": {}},
            max_retries=2,
        )

        runner = ToolRunner(tool_registry)
        result = asyncio.run(runner.execute("failing", {}))

        assert not result.success
        assert "Always fails" in result.error
        assert attempt_count == 3  # 1 initial + 2 retries

    def test_retry_on_exception(self, tool_registry: ToolRegistry) -> None:
        """Should retry on exception."""
        attempt_count = 0

        def exception_tool() -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise RuntimeError("Temporary error")
            return ToolResult(success=True, output="recovered")

        tool_registry.register_tool(
            name="exception_tool",
            handler=exception_tool,
            description="Exception tool",
            parameters={"type": "object", "properties": {}},
            max_retries=2,
        )

        runner = ToolRunner(tool_registry)
        result = asyncio.run(runner.execute("exception_tool", {}))

        assert result.success
        assert attempt_count == 2


class TestToolRunnerResultHandling:
    """Test result handling in tool runner."""

    @pytest.fixture
    def runner(self, tool_registry: ToolRegistry) -> ToolRunner:
        """Create a tool runner with test registry."""
        return ToolRunner(tool_registry)

    def test_dict_with_error_key(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should handle dict return with error key as failure.

        Note: The output from failed tool execution is not preserved after
        retries are exhausted - only the error message is kept.
        """
        tool_registry.register_tool(
            name="error_dict",
            handler=lambda: {"error": "Something went wrong", "output": "partial"},
            description="Returns error dict",
            parameters={"type": "object", "properties": {}},
            max_retries=0,  # Disable retries to test error dict handling directly
        )

        result = asyncio.run(runner.execute("error_dict", {}))

        assert not result.success
        assert result.error == "Something went wrong"
        # Note: output is not preserved after retry loop exhaustion
        assert result.output == ""

    def test_dict_without_output_key(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should handle dict return with error but no output key."""
        tool_registry.register_tool(
            name="error_only",
            handler=lambda: {"error": "Error only"},
            description="Returns error-only dict",
            parameters={"type": "object", "properties": {}},
            max_retries=0,
        )

        result = asyncio.run(runner.execute("error_only", {}))

        assert not result.success
        assert result.error == "Error only"
        assert result.output == ""

    def test_arbitrary_return_type(
        self, tool_registry: ToolRegistry, runner: ToolRunner
    ) -> None:
        """Should convert arbitrary return types to string."""
        tool_registry.register_tool(
            name="tuple_return",
            handler=lambda: (1, 2, 3),
            description="Returns tuple",
            parameters={"type": "object", "properties": {}},
        )

        result = asyncio.run(runner.execute("tuple_return", {}))

        assert result.success
        assert "(1, 2, 3)" in result.output


class TestToolRunnerContext:
    """Test execution context handling."""

    @pytest.fixture
    def runner(self, tool_registry: ToolRegistry) -> ToolRunner:
        """Create a tool runner with test registry."""
        return ToolRunner(tool_registry)

    def test_custom_execution_context(self) -> None:
        """Should create context with custom values."""
        ctx = ExecutionContext(
            user_id="test-user",
            cwd="/home/test",
            env={"PATH": "/usr/bin"},
            device_id="robot-1",
            interactive=False,
        )

        assert ctx.user_id == "test-user"
        assert ctx.cwd == "/home/test"
        assert ctx.env == {"PATH": "/usr/bin"}
        assert ctx.device_id == "robot-1"
        assert ctx.interactive is False

    def test_context_passed_to_security(
        self, tool_registry: ToolRegistry
    ) -> None:
        """Should pass context to security controller."""
        from agentsh.security.classifier import CommandRiskAssessment, RiskLevel
        from agentsh.security.controller import SecurityDecision, ValidationResult

        risk_assessment = CommandRiskAssessment(
            command="ls",
            risk_level=RiskLevel.SAFE,
        )
        mock_controller = MagicMock()
        mock_controller.validate_and_approve.return_value = SecurityDecision(
            result=ValidationResult.ALLOW,
            command="ls",
            risk_assessment=risk_assessment,
            reason="",
        )

        runner = ToolRunner(tool_registry, security_controller=mock_controller)

        tool_registry.register_tool(
            name="shell.run",
            handler=lambda command: ToolResult(success=True, output="ok"),
            description="Run command",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

        ctx = ExecutionContext(
            user_id="admin",
            cwd="/home/admin",
            device_id="server-1",
        )

        asyncio.run(runner.execute("shell.run", {"command": "ls"}, ctx))

        # Verify security context was built from execution context
        call_args = mock_controller.validate_and_approve.call_args
        security_context = call_args[0][1]  # Second positional arg

        assert security_context.user.id == "admin"
        assert security_context.device_id == "server-1"
        assert security_context.cwd == "/home/admin"


class TestIsCommandTool:
    """Test _is_command_tool method."""

    def test_known_command_tools(self, tool_registry: ToolRegistry) -> None:
        """Should recognize known command tools."""
        runner = ToolRunner(tool_registry)

        assert runner._is_command_tool("shell.run") is True
        assert runner._is_command_tool("shell.execute") is True
        assert runner._is_command_tool("bash") is True
        assert runner._is_command_tool("execute") is True
        assert runner._is_command_tool("run_command") is True

    def test_non_command_tools(self, tool_registry: ToolRegistry) -> None:
        """Should recognize non-command tools."""
        runner = ToolRunner(tool_registry)

        assert runner._is_command_tool("math.add") is False
        assert runner._is_command_tool("file.read") is False
        assert runner._is_command_tool("network.fetch") is False
