from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.domain.loaders import FixtureDataset, load_dataset
from incident_copilot.domain.models import MetricName, MetricPoint, Service
from incident_copilot.tools.contracts import ToolError, ToolName
from incident_copilot.tools.service_health import (
    MetricReading,
    ServiceHealth,
    ServiceHealthInput,
    ServiceHealthTool,
)

pytestmark = pytest.mark.anyio

REPO_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 22, hour, minute, tzinfo=UTC)


def _service(name: str) -> Service:
    return Service(name=name, owner_team="team", description=name, depends_on=())


def _point(
    service: str, metric: MetricName, hour: int, minute: int, value: float
) -> MetricPoint:
    return MetricPoint(
        service=service, metric=metric, timestamp=_at(hour, minute), value=value
    )


# Points are deliberately out of time order: the tool must not rely on file order.
DATASET = FixtureDataset(
    services=(_service("checkout"), _service("auth"), _service("silent")),
    dependencies=(),
    deploys=(),
    metrics=(
        _point("checkout", MetricName.ERROR_RATE, 14, 5, 0.08),
        _point("checkout", MetricName.ERROR_RATE, 13, 55, 0.005),
        _point("checkout", MetricName.ERROR_RATE, 14, 0, 0.06),
        _point("checkout", MetricName.LATENCY_P99_MS, 14, 0, 2150),
        _point("checkout", MetricName.LATENCY_P99_MS, 13, 50, 330),
        _point("auth", MetricName.ERROR_RATE, 12, 20, 0.001),
    ),
    logs=(),
)


async def _health(service: str, at: datetime) -> ServiceHealth:
    tool = ServiceHealthTool(DATASET)
    return await tool.run(ServiceHealthInput(service=service, at=at))


async def test_each_metric_returns_its_own_latest_reading() -> None:
    health = await _health("checkout", _at(14, 7))

    assert health.error_rate == MetricReading(value=0.08, measured_at=_at(14, 5))
    assert health.latency_p99_ms == MetricReading(value=2150, measured_at=_at(14, 0))


async def test_point_exactly_at_requested_moment_is_included() -> None:
    health = await _health("checkout", _at(14, 0))

    assert health.error_rate == MetricReading(value=0.06, measured_at=_at(14, 0))


async def test_points_after_requested_moment_are_ignored() -> None:
    health = await _health("checkout", _at(13, 59))

    assert health.error_rate == MetricReading(value=0.005, measured_at=_at(13, 55))
    assert health.latency_p99_ms == MetricReading(value=330, measured_at=_at(13, 50))


async def test_metric_the_service_does_not_report_is_none() -> None:
    health = await _health("auth", _at(14, 0))

    assert health.error_rate is not None
    assert health.latency_p99_ms is None


async def test_stale_reading_is_returned_with_its_measurement_time() -> None:
    health = await _health("auth", _at(23, 0))

    assert health.error_rate == MetricReading(value=0.001, measured_at=_at(12, 20))


async def test_unknown_service_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown service 'chekout'"):
        await _health("chekout", _at(14, 0))


async def test_no_points_before_requested_moment_is_an_error() -> None:
    with pytest.raises(ToolError, match="No metrics for service 'checkout'"):
        await _health("checkout", _at(9, 0))


async def test_known_service_without_any_metrics_is_an_error() -> None:
    with pytest.raises(ToolError, match="No metrics for service 'silent'"):
        await _health("silent", _at(14, 0))


def test_moment_without_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ServiceHealthInput(service="checkout", at=datetime(2026, 9, 22, 14, 0))


def test_spec_describes_the_tool() -> None:
    spec = ServiceHealthTool(DATASET).spec()

    assert spec.name is ToolName.GET_SERVICE_HEALTH
    assert spec.input_model is ServiceHealthInput
    assert spec.output_model is ServiceHealth
    assert spec.timeout_seconds > 0


async def test_spec_handler_runs_the_tool_on_repository_fixtures() -> None:
    # Called through the card, the way the executor will call it.
    spec = ServiceHealthTool(load_dataset(REPO_FIXTURES_DIR)).spec()

    before = await spec.handler(ServiceHealthInput(service="checkout", at=_at(13, 57)))
    during = await spec.handler(ServiceHealthInput(service="checkout", at=_at(14, 5)))

    assert before.error_rate == MetricReading(value=0.005, measured_at=_at(13, 55))
    assert during.error_rate == MetricReading(value=0.081, measured_at=_at(14, 5))
    assert during.latency_p99_ms == MetricReading(value=2150, measured_at=_at(14, 0))
