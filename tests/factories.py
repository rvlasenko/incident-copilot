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
    Deploy,
    DeployStatus,
    MetricName,
    MetricPoint,
    Service,
)

REPO_FIXTURES_DIR: Final = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def at(hour: int, minute: int) -> datetime:
    """A moment on the day all fixtures describe."""
    return datetime(2026, 9, 22, hour, minute, tzinfo=UTC)


def service(name: str) -> Service:
    return Service(name=name, owner_team="team", description=name, depends_on=())


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


def dataset(
    *,
    services: Iterable[str] = (),
    deploys: Iterable[Deploy] = (),
    metrics: Iterable[MetricPoint] = (),
) -> FixtureDataset:
    return FixtureDataset(
        services=tuple(service(name) for name in services),
        dependencies=(),
        deploys=tuple(deploys),
        metrics=tuple(metrics),
        logs=(),
    )
