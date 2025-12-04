"""Model Context Protocol (MCP) server for AgentSH.

Provides an MCP-compatible server that exposes AgentSH tools
for use by other AI systems and orchestration tools.
"""

import asyncio
import json
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from agentsh.telemetry.health import check_health
from agentsh.telemetry.logger import get_logger
from agentsh.tools.registry import ToolRegistry, get_tool_registry

logger = get_logger(__name__)


class MCPMessageType(str, Enum):
    """MCP message types."""

    # Requests
    INITIALIZE = "initialize"
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"
    LIST_RESOURCES = "resources/list"
    READ_RESOURCE = "resources/read"
    PING = "ping"

    # Responses
    RESULT = "result"
    ERROR = "error"


@dataclass
class MCPRequest:
    """MCP request message.

    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        id: Request ID
        method: Method name
        params: Method parameters
    """

    jsonrpc: str
    id: Any
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPRequest":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data["method"],
            params=data.get("params", {}),
        )


@dataclass
class MCPResponse:
    """MCP response message.

    Attributes:
        jsonrpc: JSON-RPC version
        id: Request ID
        result: Result data (for success)
        error: Error data (for failure)
    """

    jsonrpc: str
    id: Any
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        response = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response


@dataclass
class MCPToolInfo:
    """MCP tool information.

    Attributes:
        name: Tool name
        description: Tool description
        inputSchema: JSON schema for parameters
    """

    name: str
    description: str
    inputSchema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


@dataclass
class MCPServerConfig:
    """MCP server configuration.

    Attributes:
        name: Server name
        version: Server version
        allowed_tools: List of tool name patterns to expose (None = all)
        require_auth: Whether to require authentication
        auth_token: Authentication token (if required)
    """

    name: str = "agentsh"
    version: str = "1.0.0"
    allowed_tools: Optional[list[str]] = None
    require_auth: bool = False
    auth_token: Optional[str] = None


class MCPServer:
    """MCP server implementation.

    Exposes AgentSH tools via the Model Context Protocol for
    use by AI systems and orchestration tools.

    Example:
        server = MCPServer()
        await server.run_stdio()  # Run as stdio server
    """

    def __init__(
        self,
        config: Optional[MCPServerConfig] = None,
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        """Initialize MCP server.

        Args:
            config: Server configuration
            registry: Tool registry (uses global if not provided)
        """
        self.config = config or MCPServerConfig()
        self._registry = registry
        self._running = False
        self._initialized = False

        logger.debug(
            "MCPServer initialized",
            name=self.config.name,
            version=self.config.version,
        )

    @property
    def registry(self) -> ToolRegistry:
        """Get tool registry."""
        return self._registry or get_tool_registry()

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed to be exposed.

        Args:
            tool_name: Tool name

        Returns:
            True if tool is allowed
        """
        if self.config.allowed_tools is None:
            return True

        for pattern in self.config.allowed_tools:
            if pattern == tool_name:
                return True
            if pattern.endswith("*") and tool_name.startswith(pattern[:-1]):
                return True

        return False

    def get_tools(self) -> list[MCPToolInfo]:
        """Get list of exposed tools.

        Returns:
            List of tool information
        """
        tools = []
        for tool in self.registry.list_tools():
            if not self._is_tool_allowed(tool.name):
                continue

            tools.append(
                MCPToolInfo(
                    name=tool.name,
                    description=tool.description or f"Tool: {tool.name}",
                    inputSchema=tool.parameters or {"type": "object", "properties": {}},
                )
            )

        return tools

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an MCP request.

        Args:
            request: MCP request

        Returns:
            MCP response
        """
        try:
            if request.method == MCPMessageType.INITIALIZE.value:
                return await self._handle_initialize(request)
            elif request.method == MCPMessageType.LIST_TOOLS.value:
                return await self._handle_list_tools(request)
            elif request.method == MCPMessageType.CALL_TOOL.value:
                return await self._handle_call_tool(request)
            elif request.method == MCPMessageType.PING.value:
                return await self._handle_ping(request)
            elif request.method == MCPMessageType.LIST_RESOURCES.value:
                return await self._handle_list_resources(request)
            elif request.method == MCPMessageType.READ_RESOURCE.value:
                return await self._handle_read_resource(request)
            else:
                return MCPResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {request.method}",
                    },
                )
        except Exception as e:
            logger.error("MCP request failed", method=request.method, error=str(e))
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {e}",
                },
            )

    async def _handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """Handle initialize request."""
        self._initialized = True
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": self.config.name,
                    "version": self.config.version,
                },
            },
        )

    async def _handle_list_tools(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request."""
        tools = self.get_tools()
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "tools": [t.to_dict() for t in tools],
            },
        )

    async def _handle_call_tool(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request."""
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if not tool_name:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -32602,
                    "message": "Missing tool name",
                },
            )

        if not self._is_tool_allowed(tool_name):
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"Tool not allowed: {tool_name}",
                },
            )

        tool = self.registry.get_tool(tool_name)
        if not tool:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"Tool not found: {tool_name}",
                },
            )

        try:
            # Execute tool
            result = tool.handler(**arguments)

            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": result.output if hasattr(result, "output") else str(result),
                        }
                    ],
                    "isError": not (result.success if hasattr(result, "success") else True),
                },
            )
        except Exception as e:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error executing tool: {e}",
                        }
                    ],
                    "isError": True,
                },
            )

    async def _handle_ping(self, request: MCPRequest) -> MCPResponse:
        """Handle ping request."""
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={},
        )

    async def _handle_list_resources(self, request: MCPRequest) -> MCPResponse:
        """Handle resources/list request."""
        # Expose health status as a resource
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "resources": [
                    {
                        "uri": "agentsh://health",
                        "name": "Health Status",
                        "description": "Current health status of AgentSH",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": "agentsh://tools",
                        "name": "Available Tools",
                        "description": "List of available tools",
                        "mimeType": "application/json",
                    },
                ],
            },
        )

    async def _handle_read_resource(self, request: MCPRequest) -> MCPResponse:
        """Handle resources/read request."""
        uri = request.params.get("uri")

        if uri == "agentsh://health":
            health = check_health()
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(health.to_dict(), indent=2),
                        }
                    ],
                },
            )
        elif uri == "agentsh://tools":
            tools = self.get_tools()
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps([t.to_dict() for t in tools], indent=2),
                        }
                    ],
                },
            )
        else:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"Resource not found: {uri}",
                },
            )

    async def run_stdio(self) -> None:
        """Run MCP server using stdio transport.

        Reads JSON-RPC messages from stdin, processes them,
        and writes responses to stdout.
        """
        self._running = True
        logger.info("MCP server starting (stdio mode)")

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.stop)

        try:
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)

            writer_transport, writer_protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            writer = asyncio.StreamWriter(
                writer_transport, writer_protocol, reader, loop
            )

            while self._running:
                # Read content-length header
                header_line = await reader.readline()
                if not header_line:
                    break

                header = header_line.decode("utf-8").strip()
                if not header.startswith("Content-Length:"):
                    continue

                content_length = int(header.split(":")[1].strip())

                # Skip empty line
                await reader.readline()

                # Read content
                content = await reader.read(content_length)
                if not content:
                    break

                # Parse and handle request
                try:
                    data = json.loads(content.decode("utf-8"))
                    request = MCPRequest.from_dict(data)
                    response = await self.handle_request(request)
                    response_json = json.dumps(response.to_dict())

                    # Write response
                    response_bytes = response_json.encode("utf-8")
                    header = f"Content-Length: {len(response_bytes)}\r\n\r\n"
                    writer.write(header.encode("utf-8"))
                    writer.write(response_bytes)
                    await writer.drain()

                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON received", error=str(e))
                except Exception as e:
                    logger.error("Error processing request", error=str(e))

        except Exception as e:
            logger.error("MCP server error", error=str(e))
        finally:
            self._running = False
            logger.info("MCP server stopped")

    def stop(self) -> None:
        """Stop the MCP server."""
        self._running = False


async def run_mcp_server(
    config: Optional[MCPServerConfig] = None,
) -> None:
    """Run MCP server as main entry point.

    Args:
        config: Server configuration
    """
    server = MCPServer(config)
    await server.run_stdio()


def main() -> None:
    """Main entry point for MCP server."""
    # Load configuration from environment
    config = MCPServerConfig(
        name=os.environ.get("AGENTSH_MCP_NAME", "agentsh"),
        version=os.environ.get("AGENTSH_MCP_VERSION", "1.0.0"),
        require_auth=os.environ.get("AGENTSH_MCP_AUTH", "").lower() == "true",
        auth_token=os.environ.get("AGENTSH_MCP_TOKEN"),
    )

    # Parse allowed tools from environment
    allowed_tools_env = os.environ.get("AGENTSH_MCP_TOOLS")
    if allowed_tools_env:
        config.allowed_tools = [t.strip() for t in allowed_tools_env.split(",")]

    asyncio.run(run_mcp_server(config))


if __name__ == "__main__":
    main()
