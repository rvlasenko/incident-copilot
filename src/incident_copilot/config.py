"""Runtime configuration read from environment variables and an optional .env file."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: SecretStr
    openai_model: str = "gpt-5-nano"
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    # Retries of transient errors (timeouts, 429, 5xx) are done by the OpenAI client itself.
    llm_max_retries: int = Field(default=2, ge=0)


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Upper bound on the active time of one run.
    run_timeout_seconds: float = Field(default=60.0, gt=0)
