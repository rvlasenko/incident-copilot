"""Load synthetic fixtures that stand in for live operational systems.

Threat model: a typo made while editing fixtures by hand. Checks exist only
where such a typo would otherwise break the agent silently.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError

from incident_copilot.domain.models import (
    Dependency,
    Deploy,
    LogEntry,
    MetricPoint,
    Service,
)

SERVICES_FILE: Final = "services.json"
DEPENDENCIES_FILE: Final = "dependencies.json"
DEPLOYS_FILE: Final = "deploys.json"
METRICS_FILE: Final = "metrics.json"
LOGS_FILE: Final = "logs.jsonl"


class FixtureError(Exception):
    """Base class for all fixture problems, so callers can catch one type."""


class FixtureLoadError(FixtureError):
    """A single fixture file cannot be read, parsed or validated."""

    def __init__(self, path: Path, reason: str, line: int | None = None) -> None:
        location = f"{path}:{line}" if line is not None else str(path)
        super().__init__(f"Failed to load fixture {location}: {reason}")
        self.path = path
        self.line = line


class DatasetIntegrityError(FixtureError):
    """Files are valid on their own but reference names that do not exist."""

    def __init__(self, problems: list[str]) -> None:
        details = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(
            f"Fixture dataset has {len(problems)} integrity problem(s):\n{details}"
        )
        self.problems = tuple(problems)


@dataclass(frozen=True, slots=True)
class FixtureDataset:
    services: tuple[Service, ...]
    dependencies: tuple[Dependency, ...]
    deploys: tuple[Deploy, ...]
    metrics: tuple[MetricPoint, ...]
    logs: tuple[LogEntry, ...]


def load_json_list[ModelT: BaseModel](
    path: Path, model: type[ModelT]
) -> tuple[ModelT, ...]:
    """Load a JSON file containing an array of objects of one model type."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FixtureLoadError(path, f"cannot read file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(
            path, f"invalid JSON: {exc.msg}", line=exc.lineno
        ) from exc

    items: list[ModelT] = []
    for index, item in enumerate(raw):
        try:
            items.append(model.model_validate(item))
        except ValidationError as exc:
            raise FixtureLoadError(path, f"item {index} is invalid: {exc}") from exc
    return tuple(items)


def load_jsonl[ModelT: BaseModel](
    path: Path, model: type[ModelT]
) -> tuple[ModelT, ...]:
    """Load a JSON Lines file with one object per line; blank lines are skipped."""
    items: list[ModelT] = []
    try:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    items.append(model.model_validate_json(line))
                except ValidationError as exc:
                    raise FixtureLoadError(
                        path, f"invalid record: {exc}", line=line_number
                    ) from exc
    except OSError as exc:
        raise FixtureLoadError(path, f"cannot read file: {exc}") from exc
    return tuple(items)


def load_dataset(fixtures_dir: Path) -> FixtureDataset:
    """Load all fixture files from a directory and verify that references resolve."""
    dataset = FixtureDataset(
        services=load_json_list(fixtures_dir / SERVICES_FILE, Service),
        dependencies=load_json_list(fixtures_dir / DEPENDENCIES_FILE, Dependency),
        deploys=load_json_list(fixtures_dir / DEPLOYS_FILE, Deploy),
        metrics=load_json_list(fixtures_dir / METRICS_FILE, MetricPoint),
        logs=load_jsonl(fixtures_dir / LOGS_FILE, LogEntry),
    )
    problems = find_unknown_references(dataset)
    if problems:
        raise DatasetIntegrityError(problems)
    return dataset


def find_unknown_references(dataset: FixtureDataset) -> list[str]:
    """Return references to services or dependencies that are not defined."""
    services = {service.name for service in dataset.services}
    # A service may depend on another service or on an external dependency.
    dependency_targets = services | {
        dependency.name for dependency in dataset.dependencies
    }

    problems = [
        f"{SERVICES_FILE}: '{service.name}' depends on unknown '{target}'"
        for service in dataset.services
        for target in service.depends_on
        if target not in dependency_targets
    ]

    referenced: list[tuple[str, str]] = []
    referenced.extend((DEPLOYS_FILE, deploy.service) for deploy in dataset.deploys)
    referenced.extend((METRICS_FILE, point.service) for point in dataset.metrics)
    referenced.extend((LOGS_FILE, entry.service) for entry in dataset.logs)

    # set() reports each unknown name once per file; sorted() keeps output stable.
    problems += [
        f"{file_name}: reference to unknown service '{name}'"
        for file_name, name in sorted(set(referenced))
        if name not in services
    ]
    return problems
