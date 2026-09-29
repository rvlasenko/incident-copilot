from uuid import uuid4

import pytest
from pydantic import SecretStr

from incident_copilot.agent.planner import PLANNER_SYSTEM_PROMPT, LLMPlanner
from incident_copilot.agent.state import AgentState, Plan, Route
from incident_copilot.config import LLMSettings
from incident_copilot.llm.base import LLMError
from incident_copilot.llm.openai_provider import OpenAIProvider
from tests.fakes import FakeProvider

QUERY = "why did checkout error rate spike after 14:00?"


def _state() -> AgentState:
    return AgentState(run_id=uuid4(), query=QUERY)


def test_planner_returns_provider_plan() -> None:
    plan = Plan(route=Route.INVESTIGATION, rationale="needs live metrics")
    planner = LLMPlanner(FakeProvider(result=plan))

    assert planner(_state()) == plan


def test_planner_sends_query_system_prompt_and_plan_schema() -> None:
    provider = FakeProvider(result=Plan(route=Route.INVESTIGATION, rationale="r"))
    planner = LLMPlanner(provider)

    planner(_state())

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.system == PLANNER_SYSTEM_PROMPT
    assert QUERY in call.user
    assert call.schema is Plan


def test_planner_propagates_provider_error() -> None:
    planner = LLMPlanner(FakeProvider(result=LLMError("schema mismatch")))

    with pytest.raises(LLMError):
        planner(_state())


def test_openai_provider_converts_connection_failure_to_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A closed local port fails instantly, so the real error path runs without network access.
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")
    settings = LLMSettings(
        openai_api_key=SecretStr("sk-test"), llm_max_retries=0, llm_timeout_seconds=2
    )

    with pytest.raises(LLMError, match="Connection"):
        OpenAIProvider(settings).generate(system="s", user="u", schema=Plan)
