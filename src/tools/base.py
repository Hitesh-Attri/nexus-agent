"""What a tool is: a name the model can select, a description and argument
schema it reads to decide how to use it, and a callable that does the work.

The description and parameters are the model's ONLY information about a tool,
so they are part of the prompt surface, not documentation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ToolError(RuntimeError):
    """A tool failed in a way the agent should observe and reason about."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]          # JSON Schema for the args object
    run: Callable[[dict[str, Any]], str]  # returns the observation text