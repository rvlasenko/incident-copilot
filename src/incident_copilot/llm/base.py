"""Provider-neutral interface for structured LLM calls.

Callers depend on LLMProvider and handle a single LLMError; which vendor sits
behind it is an infrastructure detail.
"""

from typing import Protocol

from pydantic import BaseModel


class LLMError(Exception):
    """The provider did not return a valid structured result after its own retries."""


class LLMProvider(Protocol):
    def generate[ModelT: BaseModel](
        self, *, system: str, user: str, schema: type[ModelT]
    ) -> ModelT: ...
