"""
scripts/start_mcp_server.py
=============================
Start the MCP server for ARIS tools.

Usage: python scripts/start_mcp_server.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server import MCPServer


def main():
    print("\n🚀 Starting ARIS MCP Server...\n")

    server = MCPServer()
    caps = server.get_capabilities()
    print(f"  Server: {caps['name']} v{caps['version']}")
    print(f"  Tools:  {caps['capabilities']['tool_count']} available")
    print(f"  Categories: {', '.join(caps['capabilities']['categories'])}")
    print(f"\n  MCP Server ready. Tools exposed for external agents.\n")

    # List available tools
    tools = server.list_tools()
    print("  Available tools:")
    for t in tools:
        print(f"    • {t['name']}: {t['description'][:60]}...")

    print(f"\n✅ MCP Server initialised.\n")


if __name__ == "__main__":
    main()
