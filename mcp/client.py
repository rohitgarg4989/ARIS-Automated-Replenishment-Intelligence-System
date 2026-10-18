"""
mcp/client.py
==============
Model Context Protocol (MCP) client for connecting to MCP servers.
"""

import json
import logging
from typing import Any

logger = logging.getLogger("MCPClient")


class MCPClient:
    """
    MCP Client that connects to an MCP server and invokes tools.
    """

    def __init__(self, server=None):
        self._server = server
        logger.info("MCP Client initialised")

    def connect(self, server):
        """Connect to an MCP server instance."""
        self._server = server
        logger.info("Connected to MCP server")

    def list_tools(self) -> list[dict]:
        """List all tools available on the connected server."""
        if not self._server:
            return []
        response = self._server.handle_request({"method": "list_tools"})
        return response.get("result", [])

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the connected server."""
        if not self._server:
            return {"status": "error", "message": "Not connected to any server."}
        response = self._server.handle_request({
            "method": "call_tool",
            "params": {"name": tool_name, "arguments": arguments},
        })
        return response.get("result", {})

    def get_capabilities(self) -> dict:
        """Get server capabilities."""
        if not self._server:
            return {}
        response = self._server.handle_request({"method": "get_capabilities"})
        return response.get("result", {})
