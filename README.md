# incident-copilot

A controlled agentic workflow for on-call engineers. It takes a question about
an incident, gathers evidence from runbooks and read-only operational tools,
and ends every run in one explicit outcome. Risky actions are only proposed;
a human approves them.

> **Status:** early stage. The graph and planner are real; retrieval, executor,
> verifier and answer are stubs. See [docs/architecture.md](docs/architecture.md)
> for what is built today.

## Why

An LLM agent in on-call can fail in two dangerous ways: it presents an
unconfirmed guess as fact, or it touches production without asking. This
project keeps the LLM inside deterministic control:

- answers must be backed by evidence, or the run asks for clarification or hands off;
- routing, time limits and final states are enforced in code, not in the prompt;
- tools are read-only and typed;
- behavior is meant to be measured offline, not eyeballed.

The reasoning behind each choice is in [docs/decisions.md](docs/decisions.md).

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
make install                 # uv sync
cp .env.example .env         # set OPENAI_API_KEY
make run                     # dev server at http://127.0.0.1:8000
```

```bash
curl -X POST http://127.0.0.1:8000/assist \
  -H 'Content-Type: application/json' \
  -d '{"query": "checkout is returning 5xx after a deploy, what is going on?"}'
```

Run `make check` (lint, types, tests) before every commit. Tests do not need an
API key; `make test-live` calls the real OpenAI API.

## Architecture

Dependencies point one way: `api → agent → tools → domain`.

| Package | Role |
|---|---|
| `api/` | HTTP boundary, request validation |
| `agent/` | LangGraph graph: state, planner, nodes, routing |
| `llm/` | provider-neutral structured LLM calls |
| `tools/` | typed read-only adapters over operational data |
| `domain/` | domain models and fixture loading |

Details: [docs/architecture.md](docs/architecture.md).

## Flow

```
POST /assist
  ▼
planner ─┬─ clarification ─► clarify ─────────────────────────► CLARIFICATION_NEEDED
         ├─ handoff ───────► handoff ─────────────────────────► HANDED_OFF
         ├─ retrieval_only ► retrieval ─► answer ─────────────► COMPLETED
         └─ investigation ─► retrieval ─► executor ─► verifier ─► answer ─► COMPLETED

time limit exceeded anywhere ─► BUDGET_EXHAUSTED
```

Every finished run returns HTTP 200 with exactly one outcome.

## Layout

```
src/incident_copilot/   application code (packages above, config.py)
data/fixtures/          synthetic service state read by tools
docs/                   architecture and design decisions
tests/                  unit, graph and tool tests
scripts/                manual playground scripts
```

## Stack

Python 3.13, uv, FastAPI, Pydantic v2, LangGraph, OpenAI (via `langchain-openai`),
pytest, ruff, mypy (strict).
