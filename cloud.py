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

Note: This entrypoint eagerly loads all sub-servers at module import time
so that FastMCP Cloud and inspection tools can discover all available tools.
"""

import asyncio
from app.server import mcp, _ensure_setup

# Eagerly load sub-servers so tools are available immediately
# This is required for FastMCP Cloud and `fastmcp inspect` to discover all tools
def _load_subservers():
    """Load sub-servers in a new event loop (works even if one is already running)."""
    import concurrent.futures

    def run_in_new_loop():
        # Create a fresh event loop in this thread
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(_ensure_setup())
        finally:
            new_loop.close()

    # Run in a thread pool to avoid event loop conflicts
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_new_loop)
        future.result(timeout=10)  # 10 second timeout

try:
    _load_subservers()
except Exception as e:
    # Fallback: if anything goes wrong, just continue
    # Sub-servers will be loaded when the server actually starts
    import sys
    print(f"Warning: Could not eagerly load sub-servers: {e}", file=sys.stderr)
    print("Sub-servers will load when the server starts", file=sys.stderr)

# FastMCP Cloud will automatically discover and use this mcp instance
# No __main__ block needed - FastMCP Cloud ignores them anyway
