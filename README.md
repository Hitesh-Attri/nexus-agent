# nexus-agent

A from-scratch tool-using agent. Given a task in plain English, it decides which
tool to call, runs it, reads the result, and repeats until it can answer -
returning the answer together with the full trace of how it got there.

It owns no model and no data: reasoning goes to the resilient-llm-gateway and
retrieval goes to nexus-rag, both over HTTP.

## The idea in one line

Loop: ask the model for one decision ("call this tool with these arguments" or
"here is the final answer"), execute the tool, append the observation to the
transcript, ask again - bounded by a hard iteration cap.

## Layout

```
nexus-agent/
├── src/                        # import root (see "Imports" below)
│   ├── core/
│   │   ├── config.py           # typed settings from env / .env
│   │   ├── decision.py         # the decision schema + Decision parsing
│   │   ├── gateway.py          # httpx client for the gateway's /v1/chat
│   │   └── agent.py            # the reason -> act -> observe loop
│   ├── tools/
│   │   ├── base.py             # Tool dataclass + ToolError
│   │   ├── calculator.py       # arithmetic via an AST allowlist
│   │   ├── knowledge_base.py   # search nexus-rag's POST /search
│   │   └── registry.py         # the tool catalogue + how it's described
│   ├── api/
│   │   ├── health.py           # GET /health
│   │   └── agent.py            # POST /agent
│   └── main.py                 # FastAPI app
├── scripts/                    # manual checks, run directly
│   ├── check_tools.py          # tools only - no LLM
│   ├── check_decide.py         # one decision call - needs the gateway
│   └── check_agent.py          # full loop - needs the gateway
├── .env.example
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## How it works

One turn of the loop:

1. `_build_system()` renders the tool catalogue into the system prompt. The
   descriptions and parameters are the model's only knowledge of what exists.
2. `_build_user()` renders the task plus every previous step and its observation.
   The model is stateless, so this transcript *is* the agent's working memory.
3. `gateway.decide()` asks for one decision, constrained by `DECISION_SCHEMA`
   via the gateway's `response_schema`, and returns validated JSON.
4. `parse_decision()` turns it into a `Decision`, or raises `DecisionError`.
5. If the action is `tool`, the tool runs and its output becomes the next
   observation. If it is `final`, the loop returns the answer.

Every tool call costs one model call plus one more to read the result, so a task
needing *n* tool calls costs *n+1* calls to the gateway.

### Failures are observations, not crashes

- A tool raising `ToolError` becomes `error: ...` in the transcript, so the model
  can fix its arguments or route around the tool next turn.
- A malformed decision is recorded as a step with `error` set, so the model sees
  its own mistake.
- Only `GatewayError` propagates: if the gateway is unreachable, no amount of
  model reasoning helps, and the API returns 503.

### Why tool arguments are a JSON string

`args_json` carries the tool's arguments as a JSON-encoded **string** rather than
a nested object. Each tool has a different argument shape, so no single fixed
schema can describe them all, and provider structured-output layers reject
free-form objects with undeclared properties. A string keeps one decision schema
valid across every provider, at the cost of one `json.loads` we control.

## Tools

| Tool | What it does |
|---|---|
| `calculator` | Evaluates an arithmetic expression. The expression comes from the model, so it is parsed to an AST and evaluated against an allowlist - never with `eval()`. Exponents are capped. |
| `search_knowledge_base` | Calls nexus-rag's `POST /search` and returns the matching passages with their source names. Retrieval only: nexus-rag's `/query` would spend a second, redundant LLM call. |

Adding a tool: create a `Tool` in `src/tools/`, then add it to `TOOLS` in
`registry.py`. Nothing else changes - the prompt, the schema, and the loop are
all driven off the registry.

## Imports

Absolute, rooted at `src/`: `from core.agent import run_agent`,
`from tools.registry import get_tool`.

- **Run:** `uvicorn main:app --app-dir src` (the flag puts `src/` on the path).
- **Tests:** `pythonpath = ["src"]` in `pyproject.toml`.
- **Scripts:** each does `sys.path.insert(0, "src")` up top.

## Dependencies

`fastapi` + `uvicorn[standard]` (the service), `pydantic-settings` (config), and
`httpx` (calls to the gateway and to nexus-rag). No model SDK, no database
driver - the agent holds no state of its own.

## Prerequisites

- **resilient-llm-gateway** on `:8080` - every decision is a call to it.
- **nexus-rag** on `:8081` - only needed by `search_knowledge_base`; the
  calculator works without it.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate                    # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt

cp .env.example .env
uvicorn main:app --app-dir src --reload --port 8082
```

Ports across the stack: **8080** gateway, **8081** rag, **8082** agent.

Docker:

```bash
docker build -t nexus-agent .
docker run --rm -p 8082:8082 --env-file .env nexus-agent
```

Inside a container, `localhost` is the container itself - point `GATEWAY_URL` and
`RAG_URL` at reachable hosts (`host.docker.internal` locally, service names under
compose, Service Connect names on ECS).

## The endpoint

### `POST /agent`

```bash
curl.exe -sS -X POST http://localhost:8082/agent -H "Content-Type: application/json" -d "{\"task\":\"What is 1234 * 17 divided by 3? Then subtract 100.\"}"
```

```json
{
  "task": "What is 1234 * 17 divided by 3? Then subtract 100.",
  "answer": "6892.67",
  "iterations": 2,
  "stopped": "final",
  "steps": [
    {
      "n": 1,
      "thought": "I need to calculate (1234 * 17) / 3 - 100 using the calculator tool.",
      "action": "tool",
      "tool": "calculator",
      "args": { "expression": "(1234 * 17) / 3 - 100" },
      "observation": "6892.666666666667",
      "answer": null,
      "error": null
    },
    {
      "n": 2,
      "thought": "The calculation is done; I can answer now.",
      "action": "final",
      "tool": null,
      "args": {},
      "observation": null,
      "answer": "6892.67",
      "error": null
    }
  ]
}
```

Two turns for one tool call is expected: turn 1 chooses the call (the result does
not exist yet), turn 2 reads the observation and answers.

`stopped` is `final` when the model answered, or `max_iterations` when the cap was
reached. `max_iterations` may be set per request (1-20) to override the default.

The **trace is part of the response**, not just the logs. An agent that returns
only an answer is unauditable - you cannot tell whether it used a tool,
hallucinated, or got lucky.

### `GET /health`

```bash
curl.exe -sS http://localhost:8082/health          # {"status":"ok"}
```

## Configuration

| Var | Default | Meaning |
|---|---|---|
| `GATEWAY_URL` | `http://localhost:8080` | where the gateway is reachable |
| `RAG_URL` | `http://localhost:8081` | backs `search_knowledge_base` |
| `MAX_ITERATIONS` | `6` | hard cap on loop cycles per request |
| `GATEWAY_TIMEOUT` | `60` | seconds, per decision call |
| `TOOL_TIMEOUT` | `20` | seconds, per tool HTTP call |

## Design decisions worth knowing

- **Structured output, not text parsing.** The decision comes back as JSON
  validated against `DECISION_SCHEMA`, so there is no regex over "Action: ..."
  prose. The gateway validates it and fails over to another provider if a model
  violates the contract.
- **The loop always terminates.** It either returns `final` or falls out of the
  bounded `for` with `stopped: "max_iterations"`. There is no unbounded path.
- **The iteration cap is a cost rail too.** Each cycle is a paid model call, so a
  confused run is capped in spend, not just in time.
- **Tool descriptions are prompt surface.** They are the entire basis on which the
  model chooses; vague wording produces wrong tool selection.
- **No `eval()` on model output.** The calculator walks an AST allowlist, because
  an expression chosen by an LLM is untrusted input.
- **Stateless service.** No warm-up, no pool, no lifespan - it can scale to zero
  and back with no cold-start cost of its own.

## Known limits

- **Single-shot.** Each `POST /agent` is an independent task; there is no
  conversation memory between requests.
- **No repeat detection.** A model that calls the same tool with the same
  arguments repeatedly will grind to the iteration cap.
- **Structured output is required.** The decision call always sends
  `response_schema`, so a provider rung that cannot honour `json_schema` fails
  over instead of serving the request.
- **No tests yet.** The loop is best covered by faking `decide()` with canned
  decisions, which exercises every branch without spending model calls.

## Not built yet (next slices, in order)

1. Repeat detection - stop early when the model loops on an identical call.
2. Loop tests with a faked `decide()` - full coverage, zero model calls.
3. Conversation memory so tasks can build on previous turns.
4. Streaming the trace (SSE) - runs take tens of seconds with nothing to watch.
5. More tools: HTTP fetch, current date/time, document ingestion.
6. Request-id logging, matching the gateway's.
7. Deployment - ECR + an `ecs-service` deployment alongside the other services.
