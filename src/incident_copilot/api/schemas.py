from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from incident_copilot.agent.state import RunOutcome

MAX_QUERY_LENGTH: Final = 2000

QueryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_LENGTH),
]


class AssistRequest(BaseModel):
    query: QueryText


class AssistResponse(BaseModel):
    run_id: UUID
    outcome: RunOutcome
    answer: str
