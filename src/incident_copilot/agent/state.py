from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from incident_copilot.domain.models import NonEmptyStr


class AgentModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Route(StrEnum):
    RETRIEVAL_ONLY = "retrieval_only"
    INVESTIGATION = "investigation"
    CLARIFICATION = "clarification"
    HANDOFF = "handoff"


class RunOutcome(StrEnum):
    COMPLETED = "completed"
    RETRIEVAL_ONLY = "retrieval_only"
    CLARIFICATION_NEEDED = "clarification_needed"
    REFUSED = "refused"
    HANDED_OFF = "handed_off"
    BUDGET_EXHAUSTED = "budget_exhausted"


class Plan(AgentModel):
    route: Route
    rationale: NonEmptyStr


class AgentState(AgentModel):
    run_id: UUID
    query: NonEmptyStr
    plan: Plan | None = None
    outcome: RunOutcome | None = None
    answer: NonEmptyStr | None = None

    @model_validator(mode="after")
    def check_finished_run_is_complete(self) -> Self:
        # A finished run must always tell the user something, even on handoff.
        if (self.outcome is None) != (self.answer is None):
            raise ValueError("outcome and answer must be set together")
        return self

    @property
    def is_finished(self) -> bool:
        return self.outcome is not None


class FinishedRun(AgentModel):
    """What a run returns to callers: outcome and answer are guaranteed by type."""

    run_id: UUID
    outcome: RunOutcome
    answer: NonEmptyStr
