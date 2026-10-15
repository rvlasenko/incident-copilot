# incident-copilot

A controlled agentic workflow for on-call engineers. It takes a question about
an incident, gathers evidence from runbooks and read-only operational tools,
and ends every run in exactly one explicit outcome. Risky actions are only
proposed; a human approves them.

## Status

Early stage. Working today:

- `POST /assist` validates the request, runs the agent graph under a time
  limit and returns one outcome with HTTP 200.
- An LLM planner sorts the request into a route: investigation,
  runbook question, clarification or handoff.
- Four read-only tools over synthetic fixtures, tested on their own.

Not built yet: retrieval, the executor that calls the tools, the verifier and
the real answer. Nothing in the graph calls the tools, so a request that
reaches the answer step gets a placeholder answer.

## Why

An LLM agent in on-call can fail in two dangerous ways: it presents an
unconfirmed guess as fact, or it touches production without asking. This
project keeps the LLM inside deterministic control:

- answers must be backed by evidence, or the run asks for clarification or hands off;
- routing, time limits and final states are enforced in code, not in the prompt;
- tools are read-only and typed;
- behavior is meant to be measured offline, not eyeballed.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). Local development
only; there is no deployment.

```bash
make install                 # uv sync
cp .env.example .env         # set OPENAI_API_KEY
make run                     # dev server with reload at http://127.0.0.1:8000
```

```bash
curl -X POST http://127.0.0.1:8000/assist \
  -H 'Content-Type: application/json' \
  -d '{"query": "checkout is returning 5xx after a deploy, what is going on?"}'
```

Development commands:

```bash
make fmt                     # format and auto-fix lint findings
make check                   # lint, types, tests; run before every commit
make test-live               # real OpenAI calls; needs OPENAI_API_KEY
```

Tests do not need an API key.

## Documentation

- [docs/architecture.md](docs/architecture.md): how the system works today,
  covering components, request flow, invariants, failure handling,
  configuration and known gaps.
- [docs/decisions.md](docs/decisions.md): why it is built this way, with the
  alternatives that were rejected.

## Stack

Python 3.13, uv, FastAPI, Pydantic v2, LangGraph, OpenAI (via `langchain-openai`),
pytest, ruff, mypy (strict).
