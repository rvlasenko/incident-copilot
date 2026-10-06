from uuid import uuid4

import pytest

from incident_copilot.agent.planner import PLANNER_SYSTEM_PROMPT, LLMPlanner
from incident_copilot.agent.state import AgentState, Plan, Route
from incident_copilot.llm.base import LLMError
from tests.fakes import FakeProvider

pytestmark = pytest.mark.anyio

QUERY = "why did checkout error rate spike after 14:00?"


def _state() -> AgentState:
    return AgentState(run_id=uuid4(), query=QUERY)


async def test_planner_returns_provider_plan() -> None:
    plan = Plan(route=Route.INVESTIGATION, rationale="needs live metrics")
    planner = LLMPlanner(FakeProvider(result=plan))

    assert await planner(_state()) == plan


async def test_planner_sends_query_system_prompt_and_plan_schema() -> None:
    provider = FakeProvider(result=Plan(route=Route.INVESTIGATION, rationale="r"))
    planner = LLMPlanner(provider)

    await planner(_state())

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.system == PLANNER_SYSTEM_PROMPT
    assert QUERY in call.user
    assert call.schema is Plan


async def test_planner_propagates_provider_error() -> None:
    planner = LLMPlanner(FakeProvider(result=LLMError("OutputParserException")))

    with pytest.raises(LLMError):
        await planner(_state())
