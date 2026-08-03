"""The one decision the model makes each turn: call a tool, or answer.

The schema is deliberately flat and fixed. Tool arguments are carried as a JSON
*string* (args_json) rather than a nested object: each tool has a different
argument shape, so no single fixed schema can describe them, and provider
structured-output layers reject free-form objects with undeclared properties.
Encoding them as a string keeps one schema valid across every provider.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Brief reasoning about what to do next.",
        },
        "action": {
            "type": "string",
            "enum": ["tool", "final"],
            "description": "'tool' to call a tool, 'final' when you can answer.",
        },
        "tool": {
            "type": "string",
            "description": "Tool name. Required when action is 'tool'.",
        },
        "args_json": {
            "type": "string",
            "description": "JSON object of arguments for the tool, as a string.",
        },
        "answer": {
            "type": "string",
            "description": "The final answer. Required when action is 'final'.",
        },
    },
    "required": ["thought", "action"],
    "additionalProperties": False,
}


class DecisionError(ValueError):
    """The model returned a structurally valid but unusable decision."""


@dataclass(frozen=True)
class Decision:
    thought: str
    action: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    answer: str | None = None


def parse_decision(raw: dict[str, Any]) -> Decision:
    """Turn the model's validated JSON into a Decision, or raise DecisionError."""
    action = raw.get("action")
    thought = str(raw.get("thought", ""))

    if action == "final":
        answer = raw.get("answer")
        if not answer:
            raise DecisionError("action was 'final' but no answer was given")
        return Decision(thought=thought, action="final", answer=str(answer))

    if action == "tool":
        tool = raw.get("tool")
        if not tool:
            raise DecisionError("action was 'tool' but no tool name was given")
        args_json = raw.get("args_json") or "{}"
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as e:
            raise DecisionError(f"args_json was not valid JSON: {e}") from e
        if not isinstance(args, dict):
            raise DecisionError("args_json must decode to a JSON object")
        return Decision(thought=thought, action="tool", tool=str(tool), args=args)

    raise DecisionError(f"unknown action: {action!r}")