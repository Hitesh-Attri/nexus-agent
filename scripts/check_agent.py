import json
import sys

sys.path.insert(0, "src")

from core.agent import run_agent

for task in [
    "What is 1234 * 17 divided by 3? Then subtract 100 from that result.",
    "Say hello in one short sentence.",
]:
    print("\n" + "=" * 60)
    print("TASK:", task)
    result = run_agent(task)
    print("ANSWER:", result["answer"])
    print("stopped:", result["stopped"], "| iterations:", result["iterations"])
    print("TRACE:", json.dumps(result["steps"], indent=2))