from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]


class DomainModel(BaseModel):
    # extra="forbid" turns a typo or a forgotten field in fixtures into a validation error.
    model_config = ConfigDict(frozen=True, extra="forbid")


class DependencyStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"


class DeployStatus(StrEnum):
    SUCCEEDED = "succeeded"
    ROLLED_BACK = "rolled_back"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class Dependency(DomainModel):
    name: NonEmptyStr
    status: DependencyStatus
    since: AwareDatetime
    description: NonEmptyStr


class Deploy(DomainModel):
    id: NonEmptyStr
    service: NonEmptyStr
    version: NonEmptyStr
    deployed_at: AwareDatetime
    author: NonEmptyStr
    status: DeployStatus
    change_summary: NonEmptyStr


class MetricName(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY_P99_MS = "latency_p99_ms"


class MetricPoint(DomainModel):
    service: NonEmptyStr
    metric: MetricName
    timestamp: AwareDatetime
    # Plain float: ints are coerced, so downstream code sees a single numeric type.
    value: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_rate_bounds(self) -> Self:
        # The upper bound depends on the metric kind, so it cannot live in Field().
        if self.metric is MetricName.ERROR_RATE and self.value > 1:
            raise ValueError(f"error_rate must be within [0, 1], got {self.value}")
        return self


class Service(DomainModel):
    name: NonEmptyStr
    owner_team: NonEmptyStr
    description: NonEmptyStr
    # Tuple, not list: frozen=True does not stop a list from being mutated in place.
    depends_on: tuple[NonEmptyStr, ...]


class LogLevel(StrEnum):
    # StrEnum compares alphabetically; never order levels with < or >.
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(DomainModel):
    timestamp: AwareDatetime
    service: NonEmptyStr
    level: LogLevel
    message: NonEmptyStr
    version: NonEmptyStr
    trace_id: NonEmptyStr
