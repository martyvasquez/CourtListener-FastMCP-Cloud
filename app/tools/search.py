"""Search tools for CourtListener MCP server."""

import os
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
import httpx
from loguru import logger
from pydantic import Field

# Load environment variables
load_dotenv()

# Get API key from environment
API_KEY = os.getenv("COURT_LISTENER_API_KEY")

# Create the search server
search_server: FastMCP[Any] = FastMCP(
    name="CourtListener Search Server",
    instructions="Search server for CourtListener legal database providing comprehensive search capabilities. "
    "This server enables searching across different types of legal content including: "
    "court opinions and cases, oral argument audio recordings, federal dockets from PACER, "
    "RECAP filing documents, and judges/legal professionals. "
    "Search parameters include date ranges, court filters, case names, judge names, and full-text queries. "
    "Results are returned with detailed metadata and can be sorted by relevance or date.",
)


@search_server.tool()
async def opinions(
    q: Annotated[str, Field(description="Search query for full text of opinions using KEYWORD/BM25 search. Best for specific case names, citations, legal terms, or Boolean queries.")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    filed_after: Annotated[
        str, Field(description="Only show opinions filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Only show opinions filed before this date (YYYY-MM-DD)")
    ] = "",
    cited_gt: Annotated[
        int, Field(description="Minimum number of times opinion has been cited", ge=0)
    ] = 0,
    cited_lt: Annotated[
        int, Field(description="Maximum number of times opinion has been cited", ge=0)
    ] = 0,
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search case law opinion clusters with nested Opinion documents in CourtListener using KEYWORD search (BM25).

    This tool uses traditional keyword/BM25 search which is best for:
    - Specific case names or citations (e.g., "Brown v. Board of Education")
    - Exact legal terms or phrases (e.g., "qualified immunity")
    - Boolean queries with AND/OR/NOT operators
    - Field-specific searches (e.g., caseName:"Smith")

    For natural language or conceptual queries, use the semantic_search() tool instead.

    Returns:
        A dictionary containing search results with opinion clusters and nested opinions.
        Results include highlighted snippets with <mark> tags showing matched terms.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching opinions with keyword query: {q}")
    else:
        logger.info(f"Searching opinions with keyword query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": q,
        "order_by": order_by,
        "type": "o",  # Opinion type for V4 API
        "highlight": "on",  # Enable highlighting with <mark> tags
    }

    # Add optional filters
    if court:
        params["court"] = court
    if case_name:
        params["case_name"] = case_name
    if judge:
        params["judge"] = judge
    if filed_after:
        params["filed_after"] = filed_after
    if filed_before:
        params["filed_before"] = filed_before
    if cited_gt:
        params["cited_gt"] = cited_gt
    if cited_lt:
        params["cited_lt"] = cited_lt
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} opinions")
            else:
                logger.info(f"Found {data.get('count', 0)} opinions")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@search_server.tool()
async def semantic_search(
    natural_query: Annotated[str, Field(description="Natural language query describing the legal concept, topic, or question you're researching (e.g., 'cases about police use of force' or 'judicial opinions on privacy rights')")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    filed_after: Annotated[
        str, Field(description="Only show opinions filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Only show opinions filed before this date (YYYY-MM-DD)")
    ] = "",
    cited_gt: Annotated[
        int, Field(description="Minimum number of times opinion has been cited", ge=0)
    ] = 0,
    cited_lt: Annotated[
        int, Field(description="Maximum number of times opinion has been cited", ge=0)
    ] = 0,
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search case law using SEMANTIC/NATURAL LANGUAGE search powered by Citegeist Relevancy Engine.

    This tool uses semantic search which is best for:
    - Natural language questions (e.g., "What are the legal standards for search warrants?")
    - Conceptual or topical research (e.g., "cases about environmental protection")
    - Finding similar cases by meaning rather than exact keywords
    - Exploratory research where you don't know exact terminology

    For specific case names, citations, or Boolean queries, use the opinions() tool instead.

    The semantic search uses the Citegeist Relevancy Engine to understand the meaning and context
    of your query, finding relevant cases even when they use different terminology.

    Returns:
        A dictionary containing search results with opinion clusters and nested opinions.
        Results include highlighted snippets with <mark> tags showing relevant passages.
        Results are ranked by semantic similarity to your natural language query.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching opinions with semantic query: {natural_query}")
    else:
        logger.info(f"Searching opinions with semantic query: {natural_query}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": natural_query,
        "order_by": order_by,
        "type": "o",  # Opinion type for V4 API
        "semantic": "true",  # Enable semantic search
        "highlight": "on",  # Enable highlighting with <mark> tags
    }

    # Add optional filters
    if court:
        params["court"] = court
    if filed_after:
        params["filed_after"] = filed_after
    if filed_before:
        params["filed_before"] = filed_before
    if cited_gt:
        params["cited_gt"] = cited_gt
    if cited_lt:
        params["cited_lt"] = cited_lt
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} semantically relevant opinions")
            else:
                logger.info(f"Found {data.get('count', 0)} semantically relevant opinions")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@search_server.tool()
async def dockets(
    q: Annotated[str, Field(description="Search query for docket text")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    date_filed_after: Annotated[
        str, Field(description="Filter dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    date_filed_before: Annotated[
        str, Field(description="Filter dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search federal cases (dockets) from PACER in CourtListener.

    Returns:
        A dictionary containing search results with dockets.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching dockets with query: {q}")
    else:
        logger.info(f"Searching dockets with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": q,
        "order_by": order_by,
        "type": "d",  # Docket type for V4 API
    }

    # Add optional filters
    if court:
        params["court"] = court
    if case_name:
        params["case_name"] = case_name
    if docket_number:
        params["docket_number"] = docket_number
    if date_filed_after:
        params["date_filed_after"] = date_filed_after
    if date_filed_before:
        params["date_filed_before"] = date_filed_before
    if party_name:
        params["party_name"] = party_name
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} dockets")
            else:
                logger.info(f"Found {data.get('count', 0)} dockets")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@search_server.tool()
async def dockets_with_documents(
    q: Annotated[str, Field(description="Search query for federal cases")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    date_filed_after: Annotated[
        str, Field(description="Filter dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    date_filed_before: Annotated[
        str, Field(description="Filter dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search federal cases (dockets) with up to three nested documents. If there are more than three matching documents, the more_docs field will be true.

    Returns:
        A dictionary containing search results with dockets and their nested documents.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching dockets with documents using query: {q}")
    else:
        logger.info(f"Searching dockets with documents using query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": q,
        "order_by": order_by,
        "type": "r",  # Dockets with nested documents type for V4 API
    }

    # Add optional filters
    if court:
        params["court"] = court
    if case_name:
        params["case_name"] = case_name
    if docket_number:
        params["docket_number"] = docket_number
    if date_filed_after:
        params["date_filed_after"] = date_filed_after
    if date_filed_before:
        params["date_filed_before"] = date_filed_before
    if party_name:
        params["party_name"] = party_name
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} dockets with documents")
            else:
                logger.info(f"Found {data.get('count', 0)} dockets with documents")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@search_server.tool()
async def recap_documents(
    q: Annotated[str, Field(description="Search query for RECAP filing documents")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    document_number: Annotated[
        str, Field(description="Specific document number to search for")
    ] = "",
    attachment_number: Annotated[
        str, Field(description="Specific attachment number to search for")
    ] = "",
    filed_after: Annotated[
        str, Field(description="Filter documents filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Filter documents filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search federal filing documents from PACER in the RECAP archive.

    Returns:
        A dictionary containing search results with RECAP documents.

    """
    if ctx:
        await ctx.info(f"Searching RECAP documents with query: {q}")
    else:
        logger.info(f"Searching RECAP documents with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        return {"error": error_msg}

    params = {
        "q": q,
        "order_by": order_by,
        "type": "rd",  # RECAP document type for V4 API
    }

    # Add optional filters
    if court:
        params["court"] = court
    if case_name:
        params["case_name"] = case_name
    if docket_number:
        params["docket_number"] = docket_number
    if document_number:
        params["document_number"] = document_number
    if attachment_number:
        params["attachment_number"] = attachment_number
    if filed_after:
        params["filed_after"] = filed_after
    if filed_before:
        params["filed_before"] = filed_before
    if party_name:
        params["party_name"] = party_name
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} RECAP documents")
            else:
                logger.info(f"Found {data.get('count', 0)} RECAP documents")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        return {"error": str(e)}


@search_server.tool()
async def audio(
    q: Annotated[str, Field(description="Search query for oral argument audio")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    argued_after: Annotated[
        str, Field(description="Filter arguments after this date (YYYY-MM-DD)")
    ] = "",
    argued_before: Annotated[
        str, Field(description="Filter arguments before this date (YYYY-MM-DD)")
    ] = "",
    order_by: Annotated[
        str,
        Field(
            description="Sort by 'score desc', 'dateArgued desc', or 'dateArgued asc'"
        ),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search oral argument audio recordings in CourtListener.

    Returns:
        A dictionary containing search results with audio recordings.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching audio with query: {q}")
    else:
        logger.info(f"Searching audio with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": q,
        "order_by": order_by,
        "type": "oa",  # Oral argument type for V4 API
    }

    # Add optional filters
    if court:
        params["court"] = court
    if case_name:
        params["case_name"] = case_name
    if judge:
        params["judge"] = judge
    if argued_after:
        params["dateArgued_after"] = argued_after
    if argued_before:
        params["dateArgued_before"] = argued_before
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} audio recordings")
            else:
                logger.info(f"Found {data.get('count', 0)} audio recordings")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@search_server.tool()
async def people(
    q: Annotated[
        str, Field(description="Search query for judges and legal professionals")
    ],
    name: Annotated[str, Field(description="Filter by person's name")] = "",
    position_type: Annotated[
        str, Field(description="Filter by position type (e.g., 'jud' for judge)")
    ] = "",
    political_affiliation: Annotated[
        str, Field(description="Filter by political affiliation")
    ] = "",
    school: Annotated[str, Field(description="Filter by school attended")] = "",
    appointed_by: Annotated[
        str, Field(description="Filter by appointing authority")
    ] = "",
    selection_method: Annotated[
        str, Field(description="Filter by selection method")
    ] = "",
    order_by: Annotated[
        str, Field(description="Sort by 'score desc' or 'name asc'")
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search judges and legal professionals in the CourtListener database.

    Returns:
        A dictionary containing search results with people information.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Searching people with query: {q}")
    else:
        logger.info(f"Searching people with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    params = {
        "q": q,
        "order_by": order_by,
        "type": "p",  # People type for V4 API
    }

    # Add optional filters
    if name:
        params["name"] = name
    if position_type:
        params["position_type"] = position_type
    if political_affiliation:
        params["political_affiliation"] = political_affiliation
    if school:
        params["school"] = school
    if appointed_by:
        params["appointed_by"] = appointed_by
    if selection_method:
        params["selection_method"] = selection_method
    if limit:
        params["hit"] = limit  # V4 uses 'hit' instead of 'limit'

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if ctx:
                await ctx.info(f"Found {data.get('count', 0)} people")
            else:
                logger.info(f"Found {data.get('count', 0)} people")

            return data

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Search error: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
