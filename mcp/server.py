"""
mcp/server.py
==============
Model Context Protocol (MCP) server for the ARIS agent.
Exposes agent tools and capabilities via a standardised protocol.
"""

import json
import logging
from typing import Any

from tools.tool_registry import TOOL_REGISTRY, execute_tool
from tools.tool_search import ALL_TOOL_SCHEMAS

logger = logging.getLogger("MCPServer")


class MCPServer:
    """
    MCP Server that exposes ARIS tools through a standardised interface.
    Handles tool listing, execution, and result formatting.
    """

    def __init__(self):
        self.tools = TOOL_REGISTRY
        self.schemas = ALL_TOOL_SCHEMAS
        logger.info("MCP Server initialised with %d tools", len(self.tools))

    def list_tools(self) -> list[dict]:
        """Return all available tool schemas."""
        return list(self.schemas)

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Execute a tool by name with the given arguments.
        Returns the tool result or an error dict.
        """
        logger.info("MCP call_tool: %s args=%s", tool_name, arguments)
        result = execute_tool(tool_name, **arguments)
        return result

    def get_capabilities(self) -> dict:
        """Return server capabilities."""
        return {
            "name": "aris-mcp-server",
            "version": "1.0.0",
            "capabilities": {
                "tools": True,
                "tool_count": len(self.tools),
                "categories": ["sales", "inventory", "supplier"],
            },
        }

    def handle_request(self, request: dict) -> dict:
        """
        Handle an incoming MCP request.
        Supports: list_tools, call_tool, get_capabilities.
        """
        method = request.get("method", "")

        if method == "list_tools":
            return {"result": self.list_tools()}

        elif method == "call_tool":
            tool_name = request.get("params", {}).get("name", "")
            arguments = request.get("params", {}).get("arguments", {})
            result = self.call_tool(tool_name, arguments)
            return {"result": result}

        elif method == "get_capabilities":
            return {"result": self.get_capabilities()}

        else:
            return {"error": f"Unknown method: {method}"}
