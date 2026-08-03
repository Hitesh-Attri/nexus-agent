import sys

sys.path.insert(0, "src")

from core.decision import parse_decision
from core.gateway import decide
from tools.registry import render_tools

system = (
    "You are an agent that solves tasks using tools.\n"
    "Tools available:\n" + render_tools() + "\n\n"
    "Reply with a decision: action 'tool' to call a tool (set tool and args_json), "
    "or action 'final' with an answer when you are done."
)

for task in ["What is 1234 * 17 divided by 3?", "Say hello."]:
    raw = decide(system, f"Task: {task}")
    print("\ntask:", task)
    print("raw :", raw)
    print("parsed:", parse_decision(raw))