"""The reason -> act -> observe loop.

The model is stateless, so each turn re-sends the task plus every previous
step and its observation. That transcript is the agent's working memory: it is
how the model knows what it already tried and what came back.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from core.config import get_settings
from core.decision import DecisionError, parse_decision
from core.gateway import decide
from tools.base import ToolError
from tools.registry import get_tool, render_tools, tool_names

# Observations are re-sent every turn, so an unbounded one would grow the prompt
# without limit. Truncation keeps the transcript affordable.
MAX_OBSERVATION_CHARS = 2000

SYSTEM_TEMPLATE = """You are an agent that solves a task by calling tools.

Tools available:
{tools}

How to respond:
- Reply with exactly one decision per turn.
- To use a tool: action "tool", set "tool" to its name and "args_json" to a JSON
  object string matching that tool's argument schema.
- When the observations are enough to answer: action "final" with "answer".
- Never invent an observation; only use what the tools returned.
- Prefer a tool over your own reasoning when a tool covers the task.
- If a tool returns an error, read it and either fix the arguments or answer
  without that tool.
- Give the final answer directly and concisely; do not restate the calculation.
- Respond with a single JSON object matching the required response schema, and
  nothing else. Do not emit a native function call or tool-call message: the
  tools above are executed by the caller from your JSON decision, not by the API.
"""


@dataclass
class Step:
    n: int
    thought: str
    action: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    observation: str | None = None
    answer: str | None = None
    error: str | None = None


def _build_system() -> str:
    return SYSTEM_TEMPLATE.format(tools=render_tools())


def _build_user(task: str, steps: list[Step]) -> str:
    if not steps:
        return f"Task: {task}"
    lines = [f"Task: {task}", "", "Steps so far:"]
    for s in steps:
        if s.error:
            lines.append(f"{s.n}. invalid decision -> {s.error}")
        else:
            lines.append(f"{s.n}. {s.tool}({json.dumps(s.args)}) -> {s.observation}")
    lines.append("")
    lines.append("Continue. Call another tool or give the final answer.")
    return "\n".join(lines)


def _run_tool(name: str, args: dict[str, Any]) -> str:
    tool = get_tool(name)
    if tool is None:
        return f"error: no such tool '{name}'. Available tools: {', '.join(tool_names())}"
    try:
        observation = tool.run(args)
    except ToolError as e:
        # Tool failures are fed back as observations, not raised: the model can
        # correct its arguments or route around the tool on the next turn.
        return f"error: {e}"
    return observation[:MAX_OBSERVATION_CHARS]


def run_agent(task: str, max_iterations: int | None = None) -> dict[str, Any]:
    """Run the loop until the model answers or the iteration cap is reached."""
    limit = max_iterations or get_settings().max_iterations
    system = _build_system()
    steps: list[Step] = []

    for n in range(1, limit + 1):
        raw = decide(system, _build_user(task, steps))

        try:
            decision = parse_decision(raw)
        except DecisionError as e:
            # Malformed decision: record it and let the model see its own mistake.
            steps.append(Step(n=n, thought=str(raw.get("thought", "")),
                              action="invalid", error=str(e)))
            continue

        if decision.action == "final":
            steps.append(Step(n=n, thought=decision.thought, action="final", answer=decision.answer))
            return {"answer": decision.answer, "iterations": n,
                    "steps": [asdict(s) for s in steps], "stopped": "final"}

        observation = _run_tool(decision.tool or "", decision.args)
        steps.append(Step(n=n, thought=decision.thought, action="tool",
                          tool=decision.tool, args=decision.args,
                          observation=observation))

    return {
        "answer": "I could not complete the task within the allowed number of steps.",
        "iterations": limit,
        "steps": [asdict(s) for s in steps],
        "stopped": "max_iterations",
    }