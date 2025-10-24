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
        # No prefixes - tools use their natural names for better UX
        # The only conflict (audio) has been renamed to audio_by_id in get server
        await mcp.import_server(search_server)
        logger.info("Imported search server tools")
        await mcp.import_server(get_server)
        logger.info("Imported get server tools")
        await mcp.import_server(citation_server)
        logger.info("Imported citation server tools")
        _initialized = True
        logger.info("Server setup complete - all sub-servers loaded")


# ============================================================================
# Resources and Prompts (registered at module level for fastmcp inspect)
# ============================================================================

# Import dependencies for resources/prompts at module level
import os as _os
import httpx as _httpx
from typing import Annotated as _Annotated
from pydantic import Field as _Field
from fastmcp import Context as _Context

_API_KEY = _os.getenv("COURT_LISTENER_API_KEY")


@mcp.resource(
    uri="courtlistener://opinions/{opinion_id}",
    name="Opinion by ID",
    description="Get a specific court opinion by ID",
    mime_type="application/json",
)
async def get_opinion_resource(
    opinion_id: _Annotated[str, _Field(description="The opinion ID")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get a court opinion by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")

    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/opinions/{opinion_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.resource(
    uri="courtlistener://dockets/{docket_id}",
    name="Docket by ID",
    description="Get a specific court docket by ID",
    mime_type="application/json",
)
async def get_docket_resource(
    docket_id: _Annotated[str, _Field(description="The docket ID")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get a court docket by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")
    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.resource(
    uri="courtlistener://courts/{court_id}",
    name="Court by ID",
    description="Get court information by ID",
    mime_type="application/json",
)
async def get_court_resource(
    court_id: _Annotated[str, _Field(description="Court ID (e.g., 'scotus', 'ca9')")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get court information by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")
    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/courts/{court_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.resource(
    uri="courtlistener://people/{person_id}",
    name="Person (Judge) by ID",
    description="Get judge or legal professional information by ID",
    mime_type="application/json",
)
async def get_person_resource(
    person_id: _Annotated[str, _Field(description="The person (judge) ID")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get judge information by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")
    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/people/{person_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.resource(
    uri="courtlistener://clusters/{cluster_id}",
    name="Opinion Cluster by ID",
    description="Get an opinion cluster by ID",
    mime_type="application/json",
)
async def get_cluster_resource(
    cluster_id: _Annotated[str, _Field(description="The opinion cluster ID")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get opinion cluster by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")
    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/clusters/{cluster_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.resource(
    uri="courtlistener://audio/{audio_id}",
    name="Audio by ID",
    description="Get oral argument audio information by ID",
    mime_type="application/json",
)
async def get_audio_resource(
    audio_id: _Annotated[str, _Field(description="The audio recording ID")],
    ctx: _Context | None = None,
) -> dict[str, Any]:
    """Get audio information by ID from CourtListener."""
    if not _API_KEY:
        raise ValueError("COURT_LISTENER_API_KEY not found")
    headers = {"Authorization": f"Token {_API_KEY}"}
    async with _httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/audio/{audio_id}/",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# Prompts
# ============================================================================


@mcp.prompt(
    name="verify-citation",
    description="Multi-step citation verification workflow",
)
async def verify_citation_prompt(
    citation: _Annotated[str, _Field(description="The citation to verify")],
) -> list[str]:
    """Generate a prompt for systematic citation verification."""
    return [
        f"I need to verify this legal citation: {citation}",
        "",
        "Please perform these verification steps systematically:",
        "",
        f"1. Use 'verify_citation_format' tool to check if '{citation}' is in valid format",
        "   - Report the recognized format type",
        "   - Note any formatting issues",
        "",
        f"2. Use 'parse_citation_with_citeurl' tool to parse '{citation}'",
        "   - Extract volume, reporter, page number",
        "   - Get normalized citation format",
        "",
        f"3. Use 'lookup_citation' tool to find the actual case for '{citation}'",
        "   - Confirm the case exists in CourtListener",
        "   - Retrieve case name and parties",
        "",
        "4. Cross-reference all three results and provide verification summary",
    ]


@mcp.prompt(
    name="analyze-case",
    description="Analyze a specific legal case with citation, holding, and reasoning",
)
async def analyze_case_prompt(
    case_name: _Annotated[str, _Field(description="The name of the case to analyze")],
    include_citations: _Annotated[
        bool, _Field(description="Whether to include cited cases")
    ] = True,
) -> list[str]:
    """Generate a prompt for comprehensive case analysis."""
    messages = [
        f"I need to perform a comprehensive legal analysis of the case: {case_name}",
        "",
        "Please follow these steps:",
        f"1. Search for the case using 'opinions' tool with query: '{case_name}'",
        "2. Identify the primary opinion and retrieve its full text",
        "3. Extract and summarize: case citation, court, dates, parties, facts, issues, holding, reasoning",
    ]
    if include_citations:
        messages.extend([
            "4. Use 'extract_citations_from_text' to identify all cited cases",
            "5. Look up the most important precedents and explain how they support the holding",
        ])
    return messages


@mcp.prompt(
    name="research-judge",
    description="Research a judge's opinions and judicial history",
)
async def research_judge_prompt(
    judge_name: _Annotated[str, _Field(description="The name of the judge to research")],
    court: _Annotated[str, _Field(description="Optional court filter")] = "",
) -> list[str]:
    """Generate a prompt for researching a judge's judicial history."""
    messages = [
        f"I need to research the judicial history of: {judge_name}",
        "",
        "Please follow this research workflow:",
        f"1. Use 'people' tool to search for judge: '{judge_name}'",
        "2. Get the full judge profile using 'person' tool with the judge's ID",
    ]
    if court:
        messages.append(f"3. Search for opinions by this judge in court '{court}' using 'opinions' tool")
    else:
        messages.append("3. Search for opinions authored by this judge using 'opinions' tool")
    messages.extend([
        "4. Analyze the judge's record: topics, notable decisions, judicial philosophy, dissents",
        "5. Provide comprehensive summary: biography, career, significant opinions, expertise",
    ])
    return messages


@mcp.prompt(
    name="compare-cases",
    description="Compare two legal cases for similarities and differences",
)
async def compare_cases_prompt(
    case_1: _Annotated[str, _Field(description="First case name or citation")],
    case_2: _Annotated[str, _Field(description="Second case name or citation")],
) -> list[str]:
    """Generate a prompt for comparing two legal cases."""
    return [
        f"I need to compare these two legal cases: {case_1} and {case_2}",
        "",
        "STEP 1: Retrieve both cases using appropriate tools",
        "STEP 2: Extract key information: citation, court, date, parties, facts, issues, holdings",
        "STEP 3: Compare similarities: legal issues, facts, area of law, precedents cited",
        "STEP 4: Compare differences: outcomes, jurisdictions, time periods, factual distinctions",
        "STEP 5: Analyze relationship: does one cite the other? Same line of precedent? Conflicts?",
        "STEP 6: Provide comprehensive comparison with side-by-side table and legal analysis",
    ]


@mcp.prompt(
    name="case-law-summary",
    description="Generate a comprehensive summary of a legal opinion",
)
async def case_law_summary_prompt(
    case_identifier: _Annotated[str, _Field(description="Case name, citation, or opinion ID")],
    include_procedural_history: _Annotated[
        bool, _Field(description="Include procedural history")
    ] = True,
) -> list[str]:
    """Generate a prompt for creating case law summary."""
    messages = [
        f"I need a comprehensive summary of this legal opinion: {case_identifier}",
        "",
        "Please create a structured case summary:",
        f"1. CASE IDENTIFICATION: Retrieve {case_identifier}, get full name, citation, court, date",
    ]
    if include_procedural_history:
        messages.append("2. PROCEDURAL HISTORY: Lower court proceedings, how case reached this court")
        step = 3
    else:
        step = 2
    messages.extend([
        f"{step}. FACTS: Key factual background, events, parties' positions",
        f"{step+1}. LEGAL ISSUES: Questions of law presented",
        f"{step+2}. HOLDING: Court's decision and disposition",
        f"{step+3}. REASONING: Analysis, precedents applied, statutory interpretation",
        f"{step+4}. RULE OF LAW: Legal principles established",
        f"{step+5}. ADDITIONAL OPINIONS: Concurrences, dissents if any",
        "Format professionally with clear headings and concise language",
    ])
    return messages


@mcp.prompt(
    name="find-precedents",
    description="Find and analyze relevant precedent cases for a legal issue",
)
async def find_precedents_prompt(
    legal_issue: _Annotated[str, _Field(description="Description of the legal issue")],
    jurisdiction: _Annotated[str, _Field(description="Preferred jurisdiction")] = "federal",
) -> list[str]:
    """Generate a prompt for finding relevant precedents."""
    return [
        f"I need to find relevant precedent cases for this legal issue: {legal_issue}",
        f"Preferred jurisdiction: {jurisdiction}",
        "",
        "PHASE 1: Initial Search",
        f"1. Search for opinions using key terms from '{legal_issue}'",
        f"   - Filter by jurisdiction: {jurisdiction}",
        "   - Sort by citation count (most influential)",
        "",
        "PHASE 2: Evaluate Relevance",
        "2. For each case: assess if it addresses the same issue, review holding, check citation count",
        "",
        "PHASE 3: Identify Key Precedents",
        "3. Select the 3-5 most relevant cases",
        "   - Prioritize: binding > persuasive, recent > old, higher courts > lower courts",
        "",
        "PHASE 4: Deep Analysis",
        "4. For each key precedent: retrieve full text, extract specific holding, note reasoning",
        "",
        "PHASE 5: Precedent Summary",
        "5. Provide structured summary: binding precedents, persuasive precedents, trends, conflicts, recommended citations",
    ]


@mcp.prompt(
    name="semantic-vs-keyword-search",
    description="Guide for choosing between semantic and keyword search",
)
async def semantic_vs_keyword_prompt() -> list[str]:
    """Generate a prompt explaining when to use semantic vs keyword search."""
    return [
        "CHOOSING BETWEEN SEMANTIC AND KEYWORD SEARCH",
        "",
        "CourtListener provides two powerful search methods. Choose based on your query type:",
        "",
        "USE SEMANTIC SEARCH (semantic_search tool) when:",
        "  - You have a natural language question (e.g., 'What are the legal standards for search warrants?')",
        "  - You're researching a concept or topic (e.g., 'cases about environmental protection')",
        "  - You want to find similar cases by meaning, not exact words",
        "  - You're doing exploratory research and don't know exact legal terms",
        "  - Your query is conversational (e.g., 'How do courts treat police use of force?')",
        "",
        "USE KEYWORD SEARCH (opinions tool) when:",
        "  - You know the specific case name or citation (e.g., 'Brown v. Board of Education')",
        "  - You're searching for exact legal terms or phrases (e.g., 'qualified immunity')",
        "  - You need Boolean queries with AND/OR/NOT operators",
        "  - You want field-specific searches (e.g., caseName:\"Smith\" judge:\"Roberts\")",
        "  - You're looking for specific statute numbers, code sections, or precise terminology",
        "",
        "SEARCH CAPABILITIES:",
        "  - Both methods support: court filters, date ranges, citation counts, result limits",
        "  - Both return: highlighted snippets with <mark> tags, full metadata, relevance scores",
        "  - Semantic search uses: Citegeist Relevancy Engine for contextual understanding",
        "  - Keyword search uses: BM25 algorithm for exact term matching",
        "",
        "BEST PRACTICES:",
        "  1. For known cases: always use keyword search (opinions tool)",
        "  2. For legal concepts: start with semantic search (semantic_search tool)",
        "  3. For comprehensive research: use both methods and compare results",
        "  4. Review highlighted snippets to verify relevance",
    ]


@mcp.prompt(
    name="natural-language-search",
    description="Example workflow for semantic/natural language legal research",
)
async def natural_language_search_prompt(
    research_question: _Annotated[str, _Field(description="The natural language research question")],
    court_filter: _Annotated[str, _Field(description="Optional court filter")] = "",
) -> list[str]:
    """Generate a prompt for semantic search workflow."""
    messages = [
        f"SEMANTIC SEARCH WORKFLOW: {research_question}",
        "",
        "STEP 1: Initial Semantic Search",
        f"  - Use 'semantic_search' tool with natural_query: '{research_question}'",
    ]
    if court_filter:
        messages.append(f"  - Filter by court: '{court_filter}'")
    messages.extend([
        "  - Set limit to 20 for good coverage",
        "  - Sort by 'score desc' to get most semantically relevant cases first",
        "",
        "STEP 2: Review Highlighted Snippets",
        "  - Examine the <mark> tags in returned snippets",
        "  - Identify which results are truly relevant to your question",
        "  - Note the semantic similarity scores",
        "",
        "STEP 3: Refine if Needed",
        "  - If results are too broad: add date filters or citation count filters",
        "  - If not enough results: try rephrasing your question in different words",
        "  - Consider related concepts the search may have missed",
        "",
        "STEP 4: Deep Dive on Top Results",
        "  - Use resource templates to get full opinion text for most relevant cases",
        "  - Extract key holdings, reasoning, and citations from top 3-5 results",
        "",
        "STEP 5: Synthesize Findings",
        "  - Summarize the legal standards across multiple relevant cases",
        "  - Note any trends, splits in authority, or evolving doctrines",
        "  - Provide citations to the most important cases found",
    ])
    return messages


@mcp.prompt(
    name="keyword-search-guide",
    description="Example workflow for keyword/Boolean legal research",
)
async def keyword_search_prompt(
    search_terms: _Annotated[str, _Field(description="The keywords or Boolean query")],
    court_filter: _Annotated[str, _Field(description="Optional court filter")] = "",
) -> list[str]:
    """Generate a prompt for keyword search workflow."""
    messages = [
        f"KEYWORD SEARCH WORKFLOW: {search_terms}",
        "",
        "STEP 1: Construct Precise Query",
        f"  - Base query: '{search_terms}'",
        "  - Consider Boolean operators: AND, OR, NOT",
        "  - Use quotes for exact phrases: \"qualified immunity\"",
        "  - Use field-specific searches: caseName:\"Smith\" judge:\"Roberts\"",
        "",
        "STEP 2: Execute Keyword Search",
        f"  - Use 'opinions' tool with q: '{search_terms}'",
    ]
    if court_filter:
        messages.append(f"  - Filter by court: '{court_filter}'")
    messages.extend([
        "  - Set appropriate filters (dates, judges, citation counts)",
        "  - Sort by 'score desc' for BM25 relevance or 'dateFiled desc' for recency",
        "",
        "STEP 3: Analyze Match Quality",
        "  - Examine <mark> tags to see which terms were matched",
        "  - Check if matches are in important sections (holdings vs. dicta)",
        "  - Review BM25 scores to gauge term frequency relevance",
        "",
        "STEP 4: Refine Query",
        "  - Too many results? Add more specific terms or field filters",
        "  - Too few results? Use broader terms or remove restrictive filters",
        "  - Wrong results? Check for ambiguous terms that need context",
        "",
        "STEP 5: Retrieve Full Cases",
        "  - Use resource templates for complete opinion text",
        "  - Verify the context around highlighted matches",
        "  - Extract precise holdings and citations for your research",
    ])
    return messages


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
