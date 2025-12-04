"""Tests for MCP server implementation."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from agentsh.orchestrator.mcp_server import (
    MCPMessageType,
    MCPRequest,
    MCPResponse,
    MCPServer,
    MCPServerConfig,
    MCPToolInfo,
)


class TestMCPMessageType:
    """Tests for MCPMessageType enum."""

    def test_request_types(self):
        """Should have expected request types."""
        assert MCPMessageType.INITIALIZE.value == "initialize"
        assert MCPMessageType.LIST_TOOLS.value == "tools/list"
        assert MCPMessageType.CALL_TOOL.value == "tools/call"
        assert MCPMessageType.LIST_RESOURCES.value == "resources/list"
        assert MCPMessageType.READ_RESOURCE.value == "resources/read"
        assert MCPMessageType.PING.value == "ping"

    def test_response_types(self):
        """Should have expected response types."""
        assert MCPMessageType.RESULT.value == "result"
        assert MCPMessageType.ERROR.value == "error"


class TestMCPRequest:
    """Tests for MCPRequest dataclass."""

    def test_create_request(self):
        """Should create request with fields."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params={},
        )
        assert request.jsonrpc == "2.0"
        assert request.id == 1
        assert request.method == "tools/list"

    def test_from_dict(self):
        """Should create request from dictionary."""
        data = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {"x": 1}},
        }
        request = MCPRequest.from_dict(data)
        assert request.id == 42
        assert request.method == "tools/call"
        assert request.params["name"] == "test_tool"

    def test_from_dict_defaults(self):
        """Should use defaults for missing fields."""
        data = {
            "method": "ping",
        }
        request = MCPRequest.from_dict(data)
        assert request.jsonrpc == "2.0"
        assert request.id is None
        assert request.params == {}


class TestMCPResponse:
    """Tests for MCPResponse dataclass."""

    def test_create_success_response(self):
        """Should create success response."""
        response = MCPResponse(
            jsonrpc="2.0",
            id=1,
            result={"tools": []},
        )
        assert response.result == {"tools": []}
        assert response.error is None

    def test_create_error_response(self):
        """Should create error response."""
        response = MCPResponse(
            jsonrpc="2.0",
            id=1,
            error={"code": -32601, "message": "Method not found"},
        )
        assert response.error["code"] == -32601
        assert response.result is None

    def test_to_dict_success(self):
        """Should convert success response to dict."""
        response = MCPResponse(
            jsonrpc="2.0",
            id=1,
            result={"data": "test"},
        )
        d = response.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["result"]["data"] == "test"
        assert "error" not in d

    def test_to_dict_error(self):
        """Should convert error response to dict."""
        response = MCPResponse(
            jsonrpc="2.0",
            id=1,
            error={"code": -32603, "message": "Internal error"},
        )
        d = response.to_dict()
        assert d["error"]["code"] == -32603
        assert "result" not in d


class TestMCPToolInfo:
    """Tests for MCPToolInfo dataclass."""

    def test_create_tool_info(self):
        """Should create tool info."""
        info = MCPToolInfo(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
            },
        )
        assert info.name == "test_tool"
        assert info.description == "A test tool"

    def test_to_dict(self):
        """Should convert to dictionary."""
        info = MCPToolInfo(
            name="my_tool",
            description="Does something",
            inputSchema={"type": "object", "properties": {}},
        )
        d = info.to_dict()
        assert d["name"] == "my_tool"
        assert d["description"] == "Does something"
        assert d["inputSchema"]["type"] == "object"


class TestMCPServerConfig:
    """Tests for MCPServerConfig dataclass."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = MCPServerConfig()
        assert config.name == "agentsh"
        assert config.version == "1.0.0"
        assert config.allowed_tools is None
        assert config.require_auth is False
        assert config.auth_token is None

    def test_custom_config(self):
        """Should accept custom values."""
        config = MCPServerConfig(
            name="my-server",
            version="2.0.0",
            allowed_tools=["tool1", "tool2"],
            require_auth=True,
            auth_token="secret",
        )
        assert config.name == "my-server"
        assert config.version == "2.0.0"
        assert config.allowed_tools == ["tool1", "tool2"]
        assert config.require_auth is True
        assert config.auth_token == "secret"


class TestMCPServer:
    """Tests for MCPServer."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()

        # Create mock tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "test_tool"
        mock_tool1.description = "A test tool"
        mock_tool1.parameters = {
            "type": "object",
            "properties": {"input": {"type": "string"}},
        }
        mock_tool1.handler = MagicMock(return_value="Tool executed")

        mock_tool2 = MagicMock()
        mock_tool2.name = "other_tool"
        mock_tool2.description = "Another tool"
        mock_tool2.parameters = {"type": "object", "properties": {}}
        mock_tool2.handler = MagicMock(return_value="Other result")

        registry.list_tools.return_value = [mock_tool1, mock_tool2]
        registry.get_tool.side_effect = lambda name: (
            mock_tool1 if name == "test_tool" else
            mock_tool2 if name == "other_tool" else
            None
        )

        return registry

    @pytest.fixture
    def server(self, mock_registry):
        """Create an MCP server."""
        return MCPServer(registry=mock_registry)

    @pytest.fixture
    def config_server(self, mock_registry):
        """Create an MCP server with config."""
        config = MCPServerConfig(
            name="test-server",
            version="1.0.0",
            allowed_tools=["test_*"],
        )
        return MCPServer(config=config, registry=mock_registry)

    def test_create_server(self, server):
        """Should create server instance."""
        assert server is not None
        assert server.config.name == "agentsh"

    def test_create_server_with_config(self, config_server):
        """Should create server with custom config."""
        assert config_server.config.name == "test-server"

    def test_is_tool_allowed_all(self, server):
        """Should allow all tools when no filter set."""
        assert server._is_tool_allowed("any_tool") is True

    def test_is_tool_allowed_exact_match(self, mock_registry):
        """Should match exact tool names."""
        config = MCPServerConfig(allowed_tools=["tool1", "tool2"])
        server = MCPServer(config=config, registry=mock_registry)

        assert server._is_tool_allowed("tool1") is True
        assert server._is_tool_allowed("tool2") is True
        assert server._is_tool_allowed("tool3") is False

    def test_is_tool_allowed_wildcard(self, mock_registry):
        """Should match wildcard patterns."""
        config = MCPServerConfig(allowed_tools=["test_*", "remote.*"])
        server = MCPServer(config=config, registry=mock_registry)

        assert server._is_tool_allowed("test_tool") is True
        assert server._is_tool_allowed("test_another") is True
        assert server._is_tool_allowed("remote.run") is True
        assert server._is_tool_allowed("other_tool") is False

    def test_get_tools(self, server):
        """Should get list of tools."""
        tools = server.get_tools()
        assert len(tools) == 2
        assert any(t.name == "test_tool" for t in tools)
        assert any(t.name == "other_tool" for t in tools)

    def test_get_tools_filtered(self, config_server):
        """Should filter tools based on allowed list."""
        tools = config_server.get_tools()
        # Only test_* should be allowed
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_handle_initialize(self, server):
        """Should handle initialize request."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is None
        assert response.result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response.result
        assert response.result["serverInfo"]["name"] == "agentsh"

    @pytest.mark.asyncio
    async def test_handle_list_tools(self, server):
        """Should handle tools/list request."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=2,
            method="tools/list",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is None
        assert "tools" in response.result
        assert len(response.result["tools"]) == 2

    @pytest.mark.asyncio
    async def test_handle_call_tool(self, server):
        """Should handle tools/call request."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "test_tool",
                "arguments": {"input": "hello"},
            },
        )
        response = await server.handle_request(request)

        assert response.error is None
        assert "content" in response.result
        assert response.result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_handle_call_tool_missing_name(self, server):
        """Should error when tool name missing."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=4,
            method="tools/call",
            params={"arguments": {}},
        )
        response = await server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32602
        assert "Missing tool name" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_call_tool_not_found(self, server):
        """Should error when tool not found."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=5,
            method="tools/call",
            params={"name": "nonexistent"},
        )
        response = await server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32602
        assert "not found" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_call_tool_not_allowed(self, config_server):
        """Should error when tool not allowed."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=6,
            method="tools/call",
            params={"name": "other_tool"},
        )
        response = await config_server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32602
        assert "not allowed" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_ping(self, server):
        """Should handle ping request."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=7,
            method="ping",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is None
        assert response.result == {}

    @pytest.mark.asyncio
    async def test_handle_list_resources(self, server):
        """Should handle resources/list request."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=8,
            method="resources/list",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is None
        assert "resources" in response.result
        resources = response.result["resources"]
        assert any(r["uri"] == "agentsh://health" for r in resources)
        assert any(r["uri"] == "agentsh://tools" for r in resources)

    @pytest.mark.asyncio
    async def test_handle_read_resource_health(self, server):
        """Should handle reading health resource."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=9,
            method="resources/read",
            params={"uri": "agentsh://health"},
        )

        with patch("agentsh.orchestrator.mcp_server.check_health") as mock_health:
            mock_health.return_value = MagicMock(
                to_dict=lambda: {"status": "healthy", "healthy": True}
            )
            response = await server.handle_request(request)

        assert response.error is None
        assert "contents" in response.result
        content = response.result["contents"][0]
        assert content["uri"] == "agentsh://health"
        assert content["mimeType"] == "application/json"

    @pytest.mark.asyncio
    async def test_handle_read_resource_tools(self, server):
        """Should handle reading tools resource."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=10,
            method="resources/read",
            params={"uri": "agentsh://tools"},
        )
        response = await server.handle_request(request)

        assert response.error is None
        content = response.result["contents"][0]
        assert content["uri"] == "agentsh://tools"
        # Should be JSON containing tool list
        tools_data = json.loads(content["text"])
        assert len(tools_data) == 2

    @pytest.mark.asyncio
    async def test_handle_read_resource_not_found(self, server):
        """Should error for unknown resource."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=11,
            method="resources/read",
            params={"uri": "agentsh://unknown"},
        )
        response = await server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32602
        assert "not found" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, server):
        """Should error for unknown method."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=12,
            method="unknown/method",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32601
        assert "Method not found" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_exception(self, server, mock_registry):
        """Should handle exceptions gracefully."""
        mock_registry.list_tools.side_effect = RuntimeError("Registry error")

        request = MCPRequest(
            jsonrpc="2.0",
            id=13,
            method="tools/list",
            params={},
        )
        response = await server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32603
        assert "Internal error" in response.error["message"]

    def test_stop(self, server):
        """Should stop the server."""
        server._running = True
        server.stop()
        assert server._running is False


class TestMCPProtocol:
    """Tests for MCP protocol compliance."""

    @pytest.fixture
    def server(self):
        """Create a basic server."""
        return MCPServer()

    @pytest.mark.asyncio
    async def test_jsonrpc_version(self, server):
        """Should always return JSON-RPC 2.0."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="ping",
            params={},
        )
        response = await server.handle_request(request)
        assert response.jsonrpc == "2.0"

    @pytest.mark.asyncio
    async def test_id_preserved(self, server):
        """Should preserve request ID in response."""
        request = MCPRequest(
            jsonrpc="2.0",
            id="unique-id-123",
            method="ping",
            params={},
        )
        response = await server.handle_request(request)
        assert response.id == "unique-id-123"

    @pytest.mark.asyncio
    async def test_capabilities_structure(self, server):
        """Should return proper capabilities structure."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={},
        )
        response = await server.handle_request(request)

        caps = response.result["capabilities"]
        assert "tools" in caps
        assert "resources" in caps
