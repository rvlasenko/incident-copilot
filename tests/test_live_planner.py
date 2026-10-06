"""Smoke test against the real OpenAI API. Run manually with `make test-live`.

LLM output is not deterministic, so a failure here is a signal to look at the
prompt or the model, not proof of a code bug.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from incident_copilot.agent.planner import LLMPlanner
from incident_copilot.agent.state import AgentState, Plan, Route
from incident_copilot.config import LLMSettings
from incident_copilot.llm.openai_provider import OpenAIProvider

pytestmark = [pytest.mark.live, pytest.mark.anyio]


@pytest.fixture(scope="module")
def planner() -> LLMPlanner:
    try:
        settings = LLMSettings()
    except ValidationError:
        pytest.skip("OPENAI_API_KEY is not configured")
    return LLMPlanner(OpenAIProvider(settings))


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        (
            "What does the runbook say about handling payment provider timeouts?",
            Route.RETRIEVAL_ONLY,
        ),
        (
            "Why did the checkout error rate spike after 14:00 UTC today?",
            Route.INVESTIGATION,
        ),
        (
            "Roll back the latest inventory deploy right now.",
            Route.HANDOFF,
        ),
    ],
)
async def test_real_planner_returns_valid_plan(
    planner: LLMPlanner, query: str, expected_route: Route
) -> None:
    plan = await planner(AgentState(run_id=uuid4(), query=query))

    assert isinstance(plan, Plan)
    assert plan.route is expected_route, plan.rationale
