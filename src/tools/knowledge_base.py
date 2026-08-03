"""Knowledge-base search tool, backed by nexus-rag's retrieval endpoint.

Returns raw chunks with their source names so the agent can reason over them
and attribute what it uses.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.config import get_settings
from tools.base import Tool, ToolError


def _run(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ToolError("missing 'query'")

    settings = get_settings()
    payload: dict[str, Any] = {"question": query}
    if args.get("top_k"):
        payload["top_k"] = int(args["top_k"])

    try:
        resp = httpx.post(
            f"{settings.rag_url}/search",
            json=payload,
            timeout=settings.tool_timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise ToolError(f"knowledge base unreachable: {e}") from e

    results = resp.json().get("results", [])
    if not results:
        return "No matching documents found."
    return "\n".join(f"[{r['source']}] {r['content']}" for r in results)


knowledge_base = Tool(
    name="search_knowledge_base",
    description=(
        "Search the user's own ingested documents and return the most relevant "
        "passages. Use this for any question about the user's notes, projects, or "
        "private data - information you would not otherwise know."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for, in natural language.",
            },
            "top_k": {
                "type": "integer",
                "description": "Optional number of passages to return.",
            },
        },
        "required": ["query"],
    },
    run=_run,
)