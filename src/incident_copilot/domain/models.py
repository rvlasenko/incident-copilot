from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

# тип для Python и метаданные для библиотеки.
NonEmptyStr = Annotated[str, Field(min_length=1)]


# DomainModel — общий базовый класс. Настройки задаются один раз, и все модели домена их наследуют.
# frozen=True запрещает менять поля после создания объекта, extra="forbid" превращает лишнее поле в данных в ошибку.
class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# StrEnum — enum, значения которого одновременно являются строками.
# Pydantic сам превратит "degraded" из JSON в DependencyStatus.DEGRADED, а "broken" отклонит.
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
    value: float = Field(ge=0, allow_inf_nan=False)
    # Любая метрика не может быть отрицательной
    # Для mypy int и так подходит туда, где ожидается float: это отдельное правило системы типов Python.
    # Pydantic с float превратит 320 в 320.0. С float | int он оставит int как есть, и дальше в коде будут значения двух разных типов, например в JSON и при сравнениях.

    # error_rate — это доля, значит, она ещё и не больше 1
    # Но это правило зависит от другого поля (metric), а Field видит только своё поле.
    # Для таких проверок есть model_validator: он запускается после того, как все поля провалидированы, и видит объект целиком.

    # mode="after" означает, что валидатор запускается после проверки полей, поэтому self.metric уже enum, а self.value уже float.
    @model_validator(mode="after")
    def check_rate_bounds(self) -> Self:
        if self.metric is MetricName.ERROR_RATE and self.value > 1:
            # ValueError внутри валидатора Pydantic сам превращает в ValidationError с понятным описанием. Своё исключение здесь не нужно.
            raise ValueError(f"error_rate must be within [0, 1], got {self.value}")
        return self


class Service(DomainModel):
    name: NonEmptyStr
    owner_team: NonEmptyStr
    description: NonEmptyStr
    # Pydantic сам превратит JSON-массив в кортеж. ... здесь означает «кортеж любой длины».
    depends_on: tuple[NonEmptyStr, ...]


class LogLevel(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    CRITICAL = "CRITICAL"


class LogEntry(DomainModel):
    timestamp: AwareDatetime
    service: NonEmptyStr
    level: LogLevel
    message: NonEmptyStr
    version: NonEmptyStr
    trace_id: NonEmptyStr
