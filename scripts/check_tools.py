import sys

sys.path.insert(0, "src")

from tools.base import ToolError
from tools.registry import get_tool, render_tools

calc = get_tool("calculator")
print("result:", calc.run({"expression": "(1234 * 17) / 3"}))   # 6992.666...
print("result:", calc.run({"expression": "2 ** 10"}))           # 1024

for bad in ["__import__('os').system('echo hi')", "1/0", "2 ** 9999"]:
    try:
        calc.run({"expression": bad})
        print("NOT BLOCKED:", bad)
    except ToolError as e:
        print("blocked:", e)

print("\ncatalogue as the model sees it:\n" + render_tools())