import openai
from langchain_core.exceptions import ModelError, OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from incident_copilot.config import LLMSettings
from incident_copilot.llm.base import LLMError


class OpenAIProvider:
    def __init__(self, settings: LLMSettings) -> None:
        # No temperature: reasoning models of the GPT-5 family reject non-default values.
        self._chat = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def generate[ModelT: BaseModel](
        self, *, system: str, user: str, schema: type[ModelT]
    ) -> ModelT:
        structured = self._chat.with_structured_output(schema)
        try:
            result = structured.invoke([SystemMessage(system), HumanMessage(user)])
        except (
            ModelError,
            openai.OpenAIError,
            OutputParserException,
            ValidationError,
        ) as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        if not isinstance(result, schema):
            raise LLMError(f"Expected {schema.__name__}, got {type(result).__name__}")
        return result
