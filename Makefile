.PHONY: install fmt lint typecheck test test-live check run

install:
	uv sync

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src tests

test:
	uv run pytest

test-live:
	uv run pytest -m live

check: lint typecheck test

run:
	uv run fastapi dev src/incident_copilot/api/main.py