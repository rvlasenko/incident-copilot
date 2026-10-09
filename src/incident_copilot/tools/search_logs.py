"""search_logs: log records of one service within a time window."""

from typing import Final

from pydantic import AwareDatetime

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import LogLevel, NonEmptyStr
from incident_copilot.tools.checks import require_known_service
from incident_copilot.tools.contracts import (
    ServiceWindowInput,
    ToolModel,
    ToolName,
    ToolSpec,
)

TIMEOUT_SECONDS: Final = 5.0

DESCRIPTION: Final = (
    "Returns log records of a service between start and end at or above min_level "
    "(WARNING by default), oldest first. An empty list means no such records. "
    "Records from different services that share a trace_id belong to one request."
)


class SearchLogsInput(ServiceWindowInput):
    min_level: LogLevel = LogLevel.WARNING


class LogRecord(ToolModel):
    # No service field: every record belongs to the service in the envelope.
    timestamp: AwareDatetime
    level: LogLevel
    message: NonEmptyStr
    version: NonEmptyStr
    trace_id: NonEmptyStr


class LogSearchResult(ToolModel):
    service: NonEmptyStr
    records: tuple[LogRecord, ...]


class SearchLogsTool:
    def __init__(self, dataset: FixtureDataset) -> None:
        self._dataset = dataset

    def spec(self) -> ToolSpec[SearchLogsInput, LogSearchResult]:
        return ToolSpec(
            name=ToolName.SEARCH_LOGS,
            description=DESCRIPTION,
            input_model=SearchLogsInput,
            output_model=LogSearchResult,
            timeout_seconds=TIMEOUT_SECONDS,
            handler=self.run,
        )

    async def run(self, args: SearchLogsInput) -> LogSearchResult:
        require_known_service(self._dataset, args.service)

        matching = sorted(
            (
                entry
                for entry in self._dataset.logs
                if entry.service == args.service
                and args.start <= entry.timestamp <= args.end
                and entry.level.severity >= args.min_level.severity
            ),
            key=lambda entry: entry.timestamp,
        )
        return LogSearchResult(
            service=args.service,
            records=tuple(
                LogRecord(
                    timestamp=entry.timestamp,
                    level=entry.level,
                    message=entry.message,
                    version=entry.version,
                    trace_id=entry.trace_id,
                )
                for entry in matching
            ),
        )
