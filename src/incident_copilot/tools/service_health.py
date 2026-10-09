"""get_service_health: the latest known value of each metric of one service."""

from typing import Final

from pydantic import AwareDatetime

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import MetricName, NonEmptyStr
from incident_copilot.tools.checks import require_known_service
from incident_copilot.tools.contracts import ToolError, ToolModel, ToolName, ToolSpec

TIMEOUT_SECONDS: Final = 5.0

DESCRIPTION: Final = (
    "Returns the latest error rate and p99 latency of a service at a given moment. "
    "Each value carries the time it was measured at, which can be much earlier than "
    "the requested moment."
)


class ServiceHealthInput(ToolModel):
    service: NonEmptyStr
    # Fixtures are a frozen day with no "now", so the moment is always explicit.
    at: AwareDatetime


class MetricReading(ToolModel):
    value: float
    measured_at: AwareDatetime


class ServiceHealth(ToolModel):
    service: NonEmptyStr
    # None means the service does not report this metric, not that the value is zero.
    error_rate: MetricReading | None
    latency_p99_ms: MetricReading | None


class ServiceHealthTool:
    def __init__(self, dataset: FixtureDataset) -> None:
        self._dataset = dataset

    def spec(self) -> ToolSpec[ServiceHealthInput, ServiceHealth]:
        return ToolSpec(
            name=ToolName.GET_SERVICE_HEALTH,
            description=DESCRIPTION,
            input_model=ServiceHealthInput,
            output_model=ServiceHealth,
            timeout_seconds=TIMEOUT_SECONDS,
            handler=self.run,
        )

    async def run(self, args: ServiceHealthInput) -> ServiceHealth:
        require_known_service(self._dataset, args.service)

        health = ServiceHealth(
            service=args.service,
            error_rate=self._latest_reading(args, MetricName.ERROR_RATE),
            latency_p99_ms=self._latest_reading(args, MetricName.LATENCY_P99_MS),
        )
        if health.error_rate is None and health.latency_p99_ms is None:
            # An empty answer would read as "healthy"; no data is a different fact.
            raise ToolError(
                f"No metrics for service '{args.service}' at or before {args.at.isoformat()}"
            )
        return health

    def _latest_reading(
        self, args: ServiceHealthInput, metric: MetricName
    ) -> MetricReading | None:
        points = [
            point
            for point in self._dataset.metrics
            if point.service == args.service
            and point.metric is metric
            and point.timestamp <= args.at
        ]
        if not points:
            return None
        latest = max(points, key=lambda point: point.timestamp)
        return MetricReading(value=latest.value, measured_at=latest.timestamp)
