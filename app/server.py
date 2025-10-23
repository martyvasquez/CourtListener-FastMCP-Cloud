#!/usr/bin/env python3
"""CourtListener MCP Server - FastMCP Implementation."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import sys
import tomllib
from typing import Any

from fastmcp import FastMCP
from loguru import logger
import psutil

from app.config import config
from app.tools import citation_server, get_server, search_server

# Configure logging
# Note: File logging disabled for cloud deployment (read-only filesystem)
# FastMCP Cloud captures stdout/stderr automatically
# For local development, you can uncomment the file logging below:
# log_path = Path(__file__).parent / "logs" / "server.log"
# log_path.parent.mkdir(exist_ok=True)
# logger.add(log_path, rotation="1 MB", retention="1 week")


def get_version() -> str:
    """Get the version from pyproject.toml.

    Returns:
        The version string from pyproject.toml or 'unknown' if not found.

    """
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


def is_docker() -> bool:
    """Check if running inside a Docker container.

    Returns:
        True if running inside Docker, False otherwise.

    """
    return Path("/.dockerenv").exists() or (
        Path("/proc/1/cgroup").exists()
        and any(
            "docker" in line for line in Path("/proc/1/cgroup").open(encoding="utf-8")
        )
    )


# Create main server instance
mcp: FastMCP[Any] = FastMCP(
    name="CourtListener MCP Server",
    instructions="Model Context Protocol server providing LLMs with access to the CourtListener legal database. "
    "This server enables searching for legal opinions, cases, audio recordings, dockets, and people in the legal system. "
    "It also provides citation lookup, parsing, and validation tools using both the CourtListener API and citeurl library. "
    "Available tools include: search operations for opinions/cases/audio/dockets/people, get operations for specific records by ID, "
    "and comprehensive citation tools for parsing, validating, and looking up legal citations.",
)


@mcp.tool()
def status() -> dict[str, Any]:
    """Check the status of the CourtListener MCP server.

    Returns:
        A dictionary containing server status, system metrics, and service information.

    """
    logger.info("Status check requested")

    # Get system info using psutil
    process = psutil.Process()
    process_start = datetime.fromtimestamp(process.create_time(), tz=UTC)
    uptime_seconds = (datetime.now(UTC) - process_start).total_seconds()

    # Format uptime as human readable
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Docker and environment info
    docker_info = is_docker()
    environment = "docker" if docker_info else "native"

    return {
        "status": "healthy",
        "service": "CourtListener MCP Server",
        "version": get_version(),
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": {
            "runtime": environment,
            "docker": docker_info,
            "python_version": sys.version.split()[0],
        },
        "system": {
            "process_uptime": uptime,
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": round(process.cpu_percent(interval=0.1), 1),
        },
        "server": {
            "tools_available": ["search", "get", "citation"],
            "transport": "streamable-http",
            "api_base": "https://www.courtlistener.com/api/rest/v4/",
            "host": config.host,
            "port": config.mcp_port,
        },
    }


# Server composition setup
_initialized = False


async def _ensure_setup() -> None:
    """Ensure server setup runs exactly once.

    This function lazily loads sub-servers, which happens when:
    - main() is called for local development
    - FastMCP Cloud starts the server
    """
    global _initialized
    if not _initialized:
        logger.info("Setting up CourtListener MCP server sub-servers")
        # FastMCP 2.0+ syntax: import_server(server, prefix=None)
        # Using prefix for clarity: search_opinions, get_opinion, etc.
        await mcp.import_server(search_server, prefix="search")
        logger.info("Imported search server tools")
        await mcp.import_server(get_server, prefix="get")
        logger.info("Imported get server tools")
        # Citation tools have no prefix for cleaner names
        await mcp.import_server(citation_server)
        logger.info("Imported citation server tools")
        _initialized = True
        logger.info("Server setup complete - all sub-servers loaded")


async def main() -> None:
    """Run the CourtListener MCP server with streamable-http transport."""
    # Ensure sub-servers are loaded before starting
    await _ensure_setup()

    logger.info("Starting CourtListener MCP server with streamable-http transport")
    logger.info(
        f"Server configuration: host={config.host}, port={config.mcp_port}, log_level={config.courtlistener_log_level}"
    )

    try:
        await mcp.run_async(
            transport="streamable-http",
            host=config.host,
            port=config.mcp_port,
            path="/mcp/",
            log_level=config.courtlistener_log_level.lower(),
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise e


if __name__ == "__main__":
    logger.info("Starting CourtListener MCP server")
    asyncio.run(main())
