#!/usr/bin/env python3
"""FastMCP Cloud entrypoint for CourtListener MCP Server.

This file serves as the deployment entrypoint for FastMCP Cloud.
FastMCP Cloud will automatically discover and host the 'mcp' instance.

Usage in FastMCP Cloud:
    - Entrypoint: cloud.py:mcp
    - The server will be available at: https://your-project-name.fastmcp.app/mcp

For local development and testing:
    - fastmcp dev cloud.py:mcp
    - fastmcp inspect cloud.py:mcp
    - Or run: python -m app.server

Note: This entrypoint imports the fully configured server from app.server.
FastMCP Cloud will handle the async initialization of sub-servers automatically.
"""

from app.server import mcp

# FastMCP Cloud will automatically discover and use this mcp instance
# The server is fully configured in app/server.py with all sub-servers
# FastMCP Cloud handles the async initialization context automatically

# No __main__ block needed - FastMCP Cloud ignores them anyway
