"""The tools available to the agent, and how they're described to the model."""

from __future__ import annotations

import json

from tools.base import Tool
from tools.calculator import calculator

TOOLS: dict[str, Tool] = {t.name: t for t in (calculator,)}


def get_tool(name: str) -> Tool | None:
    return TOOLS.get(name)


def tool_names() -> list[str]:
    return list(TOOLS)


def render_tools() -> str:
    """Format the catalogue for the prompt: what exists and how to call it."""
    return "\n".join(
        f"- {t.name}: {t.description}\n  arguments schema: {json.dumps(t.parameters)}"
        for t in TOOLS.values()
    )