"""Provider-neutral interface for structured LLM calls.

Callers depend on LLMProvider and handle a single LLMError; which vendor sits
behind it is an infrastructure detail.
"""

from typing import Protocol

from pydantic import BaseModel


class LLMError(Exception):
    """The provider did not return a valid structured result after its own retries.

    Carries only the error class and HTTP status. The provider's raw message is
    never copied here because it can echo request details such as part of the
    API key; it stays on the chained exception (__cause__) for local debugging.
    """

    def __init__(self, error_type: str, status_code: int | None = None) -> None:
        detail = (
            error_type if status_code is None else f"{error_type} (HTTP {status_code})"
        )
        super().__init__(detail)
        self.error_type = error_type
        self.status_code = status_code


class LLMProvider(Protocol):
    def generate[ModelT: BaseModel](
        self, *, system: str, user: str, schema: type[ModelT]
    ) -> ModelT: ...
