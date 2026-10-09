# Design decisions

Why the code is shaped the way it is. Each entry records the decision, the
alternatives that were rejected, and the price paid. Code explains *what*;
this file explains *why*, so a change here should come with a new or updated
entry.

Status values: **Accepted** (in the code), **Planned** (agreed, lands in the
named step), **Superseded** (kept for history, points to the replacement).

---

## Orchestration (week 1)

### D1. The LLM proposes, code decides

**Status:** Accepted

The planner LLM returns a `Plan` (route + rationale). Which node runs next is
decided by plain functions in `agent/routing.py` that read the plan.

- **Why:** routing is the part that must be testable and predictable. A fake
  planner can force any route in tests without an LLM.
- **Rejected:** letting the LLM call nodes or tools directly (ReAct-style
  loop). More flexible, but the execution path becomes non-deterministic and
  hard to test or audit.
- **Price:** adding a route means changing code, not just the prompt.

### D2. Planner failure is a handoff, not a server error

**Status:** Accepted

Any `LLMError` from the planner ends the run as `HANDED_OFF` with HTTP 200 and
a fixed answer telling the engineer to investigate manually.

- **Why:** the API reports what the *agent* concluded. "I could not analyse
  this" is a valid conclusion; a 500 would hide it behind a generic error.
- **Logging:** only `error_type` and `status_code` are logged. The provider's
  raw message is never copied because it can echo request details such as part
  of the API key (covered by `test_openai_provider.py`).

### D3. One external time limit around the whole run

**Status:** Accepted (step 1.5, 2026-10-06)

`run_graph` wraps `graph.ainvoke` in `asyncio.timeout(RUN_TIMEOUT_SECONDS)`.
On expiry the run ends as `BUDGET_EXHAUSTED` with HTTP 200.

- **Rejected: deadline checks between nodes.** They cannot stop a node that is
  already hanging inside an LLM call.
- **Rejected: relying on the per-request LLM timeout.** The OpenAI client
  retries transient errors, so `timeout * (retries + 1)` can exceed any budget.
- **Consequence:** the whole call chain is `async`, because only an awaiting
  call can be cancelled (see `architecture.md`, Concurrency).
- **Invariant:** a `TimeoutError` raised by a node itself is re-raised, not
  reported as a spent budget; only an expired run-level limit becomes
  `BUDGET_EXHAUSTED`.
- **Not covered yet:** step limit against loops (3.5), token or money budget
  (not planned), persisting the outcome of a timed-out run (4.3).

### D4. Contracts appear in the step that uses them

**Status:** Accepted

`AgentState` grows only when a node needs a new field. Tool contracts were
added in week 2, evidence contracts come in week 3.

- **Why:** fields without a consumer get their meaning guessed later and
  usually guessed wrong.

### D5. The final state is validated explicitly

**Status:** Accepted

`graph.ainvoke` returns a plain dict, and the last node's update is never
validated on the way into another node. `run_graph` validates it into
`AgentState` and requires `outcome` and `answer` before building
`FinishedRun`; a violation raises `GraphInvariantError`.

### D6. Fixture validation follows a narrow threat model

**Status:** Accepted

Fixtures are edited by hand, so the realistic failure is a typo. The loaders
check schemas (`extra="forbid"`) and cross-file references, and nothing else.
Cycle and duplicate checks are listed in `PLAN.md` as deferred until a tool
depends on them.

### D18. `RunOutcome` says how a run ended, not which path it took

**Status:** Accepted (2026-10-09)

A successful run ends as `COMPLETED` on both the `retrieval_only` and the
`investigation` route. The former `RETRIEVAL_ONLY` outcome was removed: no
node ever set it.

- **Why:** the path is already recorded in `Plan.route`. Repeating it in the
  outcome creates two fields that can contradict each other, for example an
  `investigation` route with a `RETRIEVAL_ONLY` outcome.
- **If the engineer needs to see the path:** expose the route in the API
  response instead of adding outcome values.
- **Documents found by retrieval** are part of the answer (citations, 4.1),
  not of the outcome.

---

## Tool layer (week 2)

### D7. No access control by owner team

**Status:** Accepted (2026-10-07)

`services.json` keeps `owner_team` as reference data, but no tool checks who
is asking.

- **Why:** all tools are read-only over synthetic data and the system has a
  single user, so there is nobody to deny.
- **Price:** there is no `denied` tool status and no permission tests.
  Revisit if the API ever gets real users.

### D8. A failed tool call is a result, not an exception

**Status:** Accepted for contracts; executor boundary planned for 2.3

Inside a tool, an unanswerable request raises `ToolError`. The executor is the
boundary that turns it, a timeout or a validation failure into a `ToolResult`
with status `error` or `timeout`. Nothing raised by a tool leaves the executor.

- **Why:** one failed tool must not kill a run whose other tools succeeded.
  The verifier needs to see the failure to decide whether the evidence is
  still sufficient (mandatory vs optional tools).
- **Invariant:** `ok` carries `data` and no `error`; a failed status carries
  `error` and no `data` (enforced by `ToolResult`).
- **Invariant:** `ToolError` messages are written by us and safe to show to
  the engineer.

### D9. `ToolResult.data` is a plain dict

**Status:** Accepted

Each tool has a typed `output_model`, but the result stored in agent state is
a dict.

- **Why:** agent state will be checkpointed to PostgreSQL in week 4 and must
  stay JSON-serializable without a registry of result types.
- **Price:** readers of `data` lose static types. Mitigation: the executor
  validates the handler's output against `output_model` before converting it,
  so the dict shape is guaranteed at write time.

### D10. Tools share a form, not a parent class

**Status:** Accepted; `Tool` protocol planned for 2.3

Every tool is a class with `run(args)` and `spec() -> ToolSpec`. There is no
`BaseTool`. The executor only sees `ToolSpec` cards.

- **Why:** a base class tends to collect shared code until understanding one
  tool requires reading two classes. A `Protocol` documents the required shape
  and lets mypy check it without inheritance, the same way `LLMProvider` works.
- **Planned (2.3):** `Tool` protocol in `tools/contracts.py`, used by the
  registry builder, plus a short "how to add a tool" guide in that module.

### D11. Tools are infrastructure adapters

**Status:** Accepted

A tool class adapts one data source to a typed answer. Filtering by window or
picking the latest point is query logic that a real backend (Prometheus, SQL)
would do itself. Decisions about causes belong to the planner, routers and,
from week 3, the verifier.

- **Rejected for now:** a separate "data source" interface under each tool.
  When a real API replaces the fixtures, the adapter class is replaced as a
  whole; agent and executor code do not change.
- **Dependency injection:** each tool receives `FixtureDataset` in its
  constructor and never loads files itself, so tests pass small explicit
  datasets.

### D12. Time is always explicit

**Status:** Accepted

Fixtures describe one frozen day, so there is no meaningful "now". Every tool
takes the moment or window it is asked about.

- `get_recent_deploys` and the planned `search_logs` take `ServiceWindowInput`
  (both ends included; `start > end` is rejected because an LLM planner may
  swap them).
- `get_service_health` takes a single moment for now. The executor will pass
  the end of the window.

### D13. Empty answers versus errors

**Status:** Accepted

| Situation | Result |
|---|---|
| Unknown service | `ToolError` (every tool) |
| No deploys or logs in the window | `ok` with an empty list: "nothing happened" is evidence |
| No metric points at or before the moment | `ToolError`: an empty health answer would read as "healthy" |
| Metric the service never reports | that field is `None`, not zero |

### D14. Field minimization

**Status:** Accepted

Tool outputs drop fields that do not help find a cause. Example: deploy
`author` is not returned, so a person's name never reaches the LLM prompt.

### D15. Stale readings are returned with their timestamp

**Status:** Accepted

`get_service_health` returns the latest point at or before the moment, even
if it is hours old, together with `measured_at`. Judging freshness is the
verifier's job (week 3).

- **Why:** a service that crashes often stops reporting metrics, so the last
  point being "before the incident" is a real situation, not a fixture quirk.

### D16. Automatically retried tools must be read-only

**Status:** Planned (2.4)

The retry policy re-calls a tool after a transient failure. That is safe only
because every current tool reads data and changes nothing.

- **Invariant:** a tool with side effects (`propose_rollback`, week 4) is
  never retried automatically.
- **Planned:** a retry keeps the original `call_id`; the attempt number goes
  to the audit log, so one logical call stays one call in the trajectory.

### D17. Which tools run is decided by code

**Status:** Planned (2.3), proposed and not yet confirmed

For the `investigation` route, a small function builds the four `ToolCall`s
from the plan's target service and time window. The planner only extracts
those two values.

- **Why:** four cheap read-only tools, all needed for an investigation.
- **Price:** the week-5 "tool selection" metric becomes trivial.
- **Migration path:** with many tools, the planner would pick from the catalog
  (each `ToolSpec` already carries `description` and an input schema) and code
  would validate the choice and add mandatory tools. Only the call-building
  function changes; executor and tools stay as they are.

---

## Intentionally unsupported

| Not supported | Why | Revisit |
|---|---|---|
| Access control | single user, read-only data (D7) | real users |
| Row limit on log search | 9 log lines in fixtures | real log volume |
| Health trend or baseline | one value per metric is enough until the verifier compares against normal | 3.4 |
| Dependency status history | fixtures hold only the current status with `since` | real status API |
| Step limit, token budget | no loop in the graph yet | 3.5 |
| Persisting runs, resuming | no checkpointer yet | 4.3 |
| API authentication | local single-user tool | deployment |