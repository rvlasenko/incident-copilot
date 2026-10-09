"""Contracts of the tool layer: a tool request, a tool answer and a tool's catalog card.

This module must not import from `agent`: the agent state will hold tool
results, so the dependency goes agent -> tools only.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from incident_copilot.domain.models import NonEmptyStr


class ToolError(Exception):
    """A tool got valid arguments but cannot answer, e.g. the service does not exist.

    Raised inside a tool only. The executor is the boundary that turns it into
    a ToolResult, so the message must be safe to show to the engineer.
    """


class ToolModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolName(StrEnum):
    # A tool is added here in the same step that implements it.
    GET_SERVICE_HEALTH = "get_service_health"
    GET_RECENT_DEPLOYS = "get_recent_deploys"
    SEARCH_LOGS = "search_logs"


class ToolStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class ServiceWindowInput(ToolModel):
    """Arguments of tools that look at one service over a time range; both ends included."""

    service: NonEmptyStr
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def check_window_order(self) -> Self:
        # The planner may swap the ends; an inverted window would silently match nothing.
        if self.start > self.end:
            raise ValueError("start must not be after end")
        return self


class ToolCall(ToolModel):
    """A request to run one tool. Arguments are not validated yet."""

    call_id: UUID
    tool: ToolName
    # Raw on purpose: they are checked against the tool's own input model before the call.
    arguments: dict[str, Any]


class ToolResult(ToolModel):
    """The answer to one ToolCall. A failed call is a result too, not an exception."""

    call_id: UUID
    tool: ToolName
    status: ToolStatus
    # A plain dict so the agent state stays JSON-serializable for checkpoints.
    data: dict[str, Any] | None = None
    error: NonEmptyStr | None = None

    @model_validator(mode="after")
    def check_payload_matches_status(self) -> Self:
        # Readers must be able to trust the status without inspecting both fields.
        if self.status is ToolStatus.OK:
            if self.data is None or self.error is not None:
                raise ValueError("an ok result must carry data and no error")
        elif self.data is not None or self.error is None:
            raise ValueError("a failed result must carry an error and no data")
        return self


@dataclass(frozen=True, slots=True)
class ToolSpec[InputT: BaseModel, OutputT: BaseModel]:
    """Everything the executor needs to run one tool without knowing which tool it is."""

    name: ToolName
    # Written for an LLM that will later pick tools from the catalog.
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]
    timeout_seconds: float
    # Async even over in-memory fixtures: a real tool waits on a network call,
    # and only an awaiting call can be cancelled by a timeout.
    handler: Callable[[InputT], Awaitable[OutputT]]
