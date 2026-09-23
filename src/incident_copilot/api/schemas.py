from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, StringConstraints

QueryText = Annotated[
    str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)
]

MAX_QUERY_LENGTH: Final = 2000


class AssistRequest(BaseModel):
    query: QueryText


class AssistResponse(BaseModel):
    run_id: UUID
    answer: str
