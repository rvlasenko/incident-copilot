"""Builders for small, explicit test datasets.

Tests describe only the records that matter to them; everything else is empty.
Real fixtures are reached through the `repo_dataset` pytest fixture instead.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import (
    Dependency,
    DependencyStatus,
    Deploy,
    DeployStatus,
    LogEntry,
    LogLevel,
    MetricName,
    MetricPoint,
    Service,
)

REPO_FIXTURES_DIR: Final = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def at(hour: int, minute: int) -> datetime:
    """A moment on the day all fixtures describe."""
    return datetime(2026, 9, 22, hour, minute, tzinfo=UTC)


def service(name: str, depends_on: Iterable[str] = ()) -> Service:
    return Service(
        name=name, owner_team="team", description=name, depends_on=tuple(depends_on)
    )


def dependency(name: str, status: DependencyStatus, since: datetime) -> Dependency:
    return Dependency(name=name, status=status, since=since, description=name)


def deploy(
    deploy_id: str,
    service_name: str,
    deployed_at: datetime,
    status: DeployStatus = DeployStatus.SUCCEEDED,
) -> Deploy:
    return Deploy(
        id=deploy_id,
        service=service_name,
        version="1.0.0",
        deployed_at=deployed_at,
        author="alice",
        status=status,
        change_summary=f"change {deploy_id}",
    )


def metric(
    service_name: str, name: MetricName, timestamp: datetime, value: float
) -> MetricPoint:
    return MetricPoint(
        service=service_name, metric=name, timestamp=timestamp, value=value
    )


def log(
    service_name: str,
    timestamp: datetime,
    level: LogLevel,
    message: str = "something happened",
    trace_id: str = "t-1",
) -> LogEntry:
    return LogEntry(
        timestamp=timestamp,
        service=service_name,
        level=level,
        message=message,
        version="1.0.0",
        trace_id=trace_id,
    )


def dataset(
    *,
    services: Iterable[str | Service] = (),
    dependencies: Iterable[Dependency] = (),
    deploys: Iterable[Deploy] = (),
    metrics: Iterable[MetricPoint] = (),
    logs: Iterable[LogEntry] = (),
) -> FixtureDataset:
    return FixtureDataset(
        services=tuple(
            service(item) if isinstance(item, str) else item for item in services
        ),
        dependencies=tuple(dependencies),
        deploys=tuple(deploys),
        metrics=tuple(metrics),
        logs=tuple(logs),
    )
