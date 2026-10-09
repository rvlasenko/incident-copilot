# Architecture

An assistant for on-call engineers. It takes a question about an incident,
decides how to handle it, gathers evidence from runbooks and live operational
data, and answers with a fixed set of outcomes. The reasons behind the shape
below are in [`decisions.md`](decisions.md).

Current state: week 2 of `PLAN.md`. The graph and planner are real; retrieval,
executor, verifier and answer are stubs; two read-only tools exist but are not
wired into the graph yet.

## Components

| Package | Role | Depends on |
|---|---|---|
| `api/` | HTTP boundary: request validation, one run per request | `agent` |
| `agent/` | the graph: state, planner, nodes, routers, run time limit | `llm`, `tools` (from 2.3) |
| `llm/` | provider-neutral structured LLM calls (`LLMProvider`) | vendor SDK |
| `tools/` | typed read-only adapters over operational data | `domain` |
| `domain/` | domain models and fixture loading | nothing internal |
| `config.py` | settings from environment and `.env` | — |

Dependencies point one way: `api → agent → tools → domain`. `tools` must not
import from `agent`, because agent state will hold tool results.

`api/main.py` is the only place that reads settings and builds real
dependencies (OpenAI provider, later the fixture dataset and tool registry).
Everything else receives its dependencies as arguments, which is how tests
replace the LLM and the data.

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

## Tool layer

```
                build_tool_calls(plan)            (2.3)
                        │ list[ToolCall]          raw arguments
                        ▼
executor ── for each call ──────────────────────────────────────────┐
  │ registry[tool] → ToolSpec                                       │
  │ input_model.model_validate(arguments)    invalid → error        │
  │ handler(args) under timeout_seconds      ToolError → error      │
  │                                          timeout   → timeout    │
  │ output_model check, model_dump()         ok + data              │
  ▼                                                                 │
AgentState: ToolResult per call  ◄──────────────────────────────────┘
```

Built today: `ToolCall`, `ToolResult`, `ToolSpec`, `ServiceWindowInput`,
`ToolError` in `tools/contracts.py`; `ServiceHealthTool` and
`RecentDeploysTool`. Planned: `search_logs`, `get_dependency_status` (2.2),
registry, `Tool` protocol and executor (2.3), retry policy (2.4), audit log
(2.5).

Rules every tool follows:

1. Receives its data source in the constructor; never loads it itself.
2. `run` is `async`, even over in-memory data, so a timeout can cancel it.
3. Reads only; never changes state anywhere (required for retries, D16).
4. Returns a typed output model with the minimum fields needed (D14).
5. Raises `ToolError` with a message safe to show; never returns an empty
   answer that could be mistaken for "healthy" (D13).

## Concurrency and time limits

- The API endpoint, `run_graph`, the planner node and the LLM provider are
  `async`. One run is one task on the event loop.
- The run-level `asyncio.timeout` cancels the task. Cancellation reaches only
  code that is awaiting; blocking synchronous work inside a node is not
  interrupted. Nodes that wait on I/O must therefore be `async`.
- Per-tool timeouts (2.3) are nested inside the run limit. Whichever expires
  first wins: a tool timeout becomes a `ToolResult` and the run continues; the
  run limit ends the run.
- `FixtureDataset` is immutable and shared by all requests and tools without
  locks.
- Tests share one event loop for the whole session (`tests/conftest.py`)
  because the OpenAI client pools connections process-wide; a connection
  opened on a closed loop fails the next test.

## Failure handling

| Failure | Where it is handled | Result |
|---|---|---|
| Invalid request body | FastAPI validation | 422 |
| LLM error after client retries | planner node | `HANDED_OFF`, warning log |
| Run exceeds time limit | `run_graph` | `BUDGET_EXHAUSTED`, warning log |
| Tool error or tool timeout | executor (2.3) | `ToolResult` in state |
| Broken graph invariant | raised | 500 |
| Broken fixture file | `load_dataset` | `FixtureError`; from 2.3 the dataset loads at startup, so the process does not start |

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
uv sync                    # dependencies into .venv
make check                 # lint, types, tests; run before every commit
make test-live             # real OpenAI calls; needs OPENAI_API_KEY
uv run uvicorn incident_copilot.api.main:app --reload
```

Manual playground scripts in `scripts/` call single tools on the repository
fixtures, for example `uv run python scripts/try_recent_deploys.py`.

There is no deployment yet; the service runs locally only.

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