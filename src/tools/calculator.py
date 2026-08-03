"""Arithmetic tool.

The expression comes from the model, so it is parsed into an AST and evaluated
node by node against an allowlist - never with eval(), which would execute
arbitrary Python chosen by an LLM.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from tools.base import Tool, ToolError

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

MAX_EXPONENT = 100  # 9**9**9 would hang the process; cap it


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ToolError("only numeric literals are allowed")
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ToolError(f"exponent too large (max {MAX_EXPONENT})")
        return _BINARY[type(node.op)](left, right)
    raise ToolError(f"unsupported expression element: {type(node).__name__}")


def _run(args: dict[str, Any]) -> str:
    expression = str(args.get("expression", "")).strip()
    if not expression:
        raise ToolError("missing 'expression'")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ToolError(f"could not parse expression: {e}") from e
    try:
        result = _eval(tree)
    except ZeroDivisionError as e:
        raise ToolError("division by zero") from e
    return str(result)


calculator = Tool(
    name="calculator",
    description=(
        "Evaluate an arithmetic expression and return the numeric result. "
        "Use this for any calculation instead of doing mental math. "
        "Supports + - * / // % ** and parentheses."
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The arithmetic expression, e.g. '(1234 * 17) / 3'",
            }
        },
        "required": ["expression"],
    },
    run=_run,
)