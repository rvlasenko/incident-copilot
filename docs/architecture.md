# Architecture

An assistant for on-call engineers. It takes a question about an incident,
decides how to handle it, gathers evidence from runbooks and operational data,
and answers with one of a fixed set of outcomes.

This page describes the system as it is in the code. Reasons behind the shape
are in [`decisions.md`](decisions.md); progress and next steps are in
`PLAN.md` only.

## Components

| Package | Role | Depends on |
|---|---|---|
| `api/` | HTTP boundary: request validation, one run per request | `agent` |
| `agent/` | the graph: state, planner, nodes, routers, run time limit | `llm` |
| `llm/` | provider-neutral structured LLM calls (`LLMProvider`) | vendor SDK |
| `tools/` | typed read-only adapters over operational data | `domain` |
| `domain/` | domain models and fixture loading | nothing internal |
| `config.py` | settings from environment and `.env` | — |

Dependencies point one way: `api → agent → tools → domain`. `tools` never
imports from `agent`, so agent state can hold tool results without an import
cycle.

`api/main.py` is the only place that reads settings and builds real
dependencies such as the OpenAI provider. Everything else receives its
dependencies as arguments, which is how tests replace the LLM and the data.

Retrieval, executor and verifier nodes are stubs, and the tools are not called
from the graph.

## Request flow

```
POST /assist {query}
  │  AssistRequest: strip, 1..2000 chars, else 422
  ▼
run_graph(state, timeout_seconds)          asyncio.timeout around the whole run
  │
  ▼
planner ── LLMError ─────────────────────────────► END  HANDED_OFF
  │ Plan(route, rationale)
  ├─ clarification ─► clarify ────────────────────► END  CLARIFICATION_NEEDED
  ├─ handoff ───────► handoff ────────────────────► END  HANDED_OFF
  ├─ retrieval_only ► retrieval ─► answer ────────► END  COMPLETED
  └─ investigation ─► retrieval ─► executor ─► verifier ─► answer ─► END  COMPLETED
  │
  ▼
FinishedRun(run_id, outcome, answer)  →  AssistResponse, HTTP 200
time limit expired anywhere           →  BUDGET_EXHAUSTED, HTTP 200
```

Every finished run returns HTTP 200 with exactly one `RunOutcome`. Non-200
responses mean the request itself was invalid (422) or the code broke an
invariant (500).

## State and invariants

`AgentState` is a frozen Pydantic model; nodes return partial updates and
LangGraph merges them.

- `outcome` and `answer` are set together or not at all. A finished run always
  tells the engineer something.
- Nodes after the planner call `require_plan()`; a missing plan there raises
  `GraphInvariantError` instead of failing later with an unclear error.
- `run_graph` validates the final state explicitly (D5).

## Tools

| Tool | Input | Output |
|---|---|---|
| `get_service_health` | service, moment | latest error rate and p99 latency, each with `measured_at` |
| `get_recent_deploys` | service, window | deploys in the window, oldest first, without author |
| `search_logs` | service, window, minimum level | log records, oldest first |
| `get_dependency_status` | service | internal services by name; external dependencies with status |

Contracts live in `tools/contracts.py`: `ToolCall` (a request with raw
arguments), `ToolResult` (status `ok`, `error` or `timeout`, with either data
or an error message), `ToolSpec` (the card a caller uses to validate
arguments, run the tool and check its output), and `ToolError`.

Every tool follows the same rules:

1. Receives its data source in the constructor; never loads it itself.
2. `run` is `async`, even over in-memory data, so a timeout can cancel it.
3. Reads only; never changes state anywhere (D16).
4. Returns a typed output model with the minimum fields needed (D14).
5. Raises `ToolError` with a message safe to show; never returns an empty
   answer that could be mistaken for "healthy" (D13).

## Concurrency and time limits

- The API endpoint, `run_graph`, the planner node and the LLM provider are
  `async`. One run is one task on the event loop.
- The run-level `asyncio.timeout` cancels the task. Cancellation reaches only
  code that is awaiting; blocking synchronous work inside a node is not
  interrupted. Nodes that wait on I/O must therefore be `async`.
- `FixtureDataset` is immutable and can be shared by requests and tools
  without locks.
- Tests share one event loop for the whole session (`tests/conftest.py`)
  because the OpenAI client pools connections process-wide; a connection
  opened on a closed loop fails the next test.

## Failure handling

| Failure | Where it is handled | Result |
|---|---|---|
| Invalid request body | FastAPI validation | 422 |
| LLM error after client retries | planner node | `HANDED_OFF`, warning log |
| Run exceeds time limit | `run_graph` | `BUDGET_EXHAUSTED`, warning log |
| Broken graph invariant | raised | 500 |
| Tool cannot answer | the tool | `ToolError` |
| Broken fixture file | `load_dataset` | `FixtureError` naming the file and line or item |

## Configuration

Read by `pydantic-settings` from the environment, then from `.env` in the
working directory. `.env` holds the API key and must stay out of git.

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | required | key for the planner LLM |
| `OPENAI_MODEL` | `gpt-5-nano` | planner model |
| `LLM_TIMEOUT_SECONDS` | `30` | timeout of one LLM request |
| `LLM_MAX_RETRIES` | `2` | client-side retries of transient LLM errors |
| `RUN_TIMEOUT_SECONDS` | `60` | upper bound on one run; must be positive |

Tests never need the key: the LLM is replaced by fakes. Tests marked `live`
call the real API and are skipped without a key.

## Setup and running

```bash
make install               # uv sync: dependencies into .venv
make fmt                   # format and auto-fix lint findings
make check                 # lint, types, tests; run before every commit
make test-live             # real OpenAI calls; needs OPENAI_API_KEY
make run                   # dev server with reload (fastapi dev)
```

Scripts in `scripts/` call single tools on the repository fixtures, for
example `uv run python scripts/try_recent_deploys.py`.

The service runs locally only; there is no deployment.

## Testing approach

- Graph tests inject fake planners to force each route and assert visited
  nodes and outcomes.
- Tool tests build small explicit datasets with `tests/factories.py` to hit
  edge cases (window bounds, ordering, missing metrics), plus one or two tests
  per tool on the repository fixtures through `repo_dataset` to prove the
  incident scenario.
- External systems are replaced, business logic is not: the OpenAI API is
  replaced by a local HTTP stub or a fake provider; tool logic always runs for
  real.