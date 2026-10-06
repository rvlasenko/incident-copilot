import asyncio
import logging
import time
from uuid import uuid4

import pytest

from incident_copilot.agent.graph import (
    BUDGET_EXHAUSTED_ANSWER,
    AgentGraph,
    build_graph,
    run_graph,
)
from incident_copilot.agent.nodes import PLANNER_UNAVAILABLE_ANSWER, Node
from incident_copilot.agent.state import AgentState, Plan, Route, RunOutcome
from tests.fakes import failing_planner, fixed_route_graph, hanging_planner

pytestmark = pytest.mark.anyio

# Generous limit for tests that are not about the time budget.
TIMEOUT = 5.0


def _new_state() -> AgentState:
    return AgentState(run_id=uuid4(), query="why is checkout failing?")


async def _visited_nodes(graph: AgentGraph) -> list[str]:
    updates = graph.astream(_new_state(), stream_mode="updates")
    return [node async for update in updates for node in update]


@pytest.mark.parametrize(
    ("route", "expected_outcome"),
    [
        (Route.RETRIEVAL_ONLY, RunOutcome.COMPLETED),
        (Route.INVESTIGATION, RunOutcome.COMPLETED),
        (Route.CLARIFICATION, RunOutcome.CLARIFICATION_NEEDED),
        (Route.HANDOFF, RunOutcome.HANDED_OFF),
    ],
)
async def test_every_route_finishes_with_expected_outcome(
    route: Route, expected_outcome: RunOutcome
) -> None:
    initial = _new_state()

    final = await run_graph(fixed_route_graph(route), initial, timeout_seconds=TIMEOUT)

    assert final.outcome is expected_outcome
    assert final.answer
    assert final.run_id == initial.run_id


@pytest.mark.parametrize(
    ("route", "expected_path"),
    [
        (Route.RETRIEVAL_ONLY, [Node.PLANNER, Node.RETRIEVAL, Node.ANSWER]),
        (
            Route.INVESTIGATION,
            [Node.PLANNER, Node.RETRIEVAL, Node.EXECUTOR, Node.VERIFIER, Node.ANSWER],
        ),
        (Route.CLARIFICATION, [Node.PLANNER, Node.CLARIFY]),
        (Route.HANDOFF, [Node.PLANNER, Node.HANDOFF]),
    ],
)
async def test_route_determines_visited_nodes(
    route: Route, expected_path: list[Node]
) -> None:
    assert await _visited_nodes(fixed_route_graph(route)) == expected_path


async def test_planner_failure_hands_off_without_running_other_nodes() -> None:
    graph = build_graph(planner=failing_planner)

    visited = await _visited_nodes(graph)
    run = await run_graph(graph, _new_state(), timeout_seconds=TIMEOUT)

    assert visited == [Node.PLANNER]
    assert run.outcome is RunOutcome.HANDED_OFF
    assert run.answer == PLANNER_UNAVAILABLE_ANSWER


async def test_planner_failure_is_logged_with_error_type_and_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = _new_state()

    with caplog.at_level(logging.WARNING):
        await run_graph(
            build_graph(planner=failing_planner), state, timeout_seconds=TIMEOUT
        )

    [record] = caplog.records
    message = record.getMessage()
    assert str(state.run_id) in message
    assert "error_type=SimulatedOutage" in message
    assert "status_code=503" in message


async def test_hanging_planner_ends_run_at_the_time_limit() -> None:
    state = _new_state()
    started = time.monotonic()

    run = await run_graph(
        build_graph(planner=hanging_planner), state, timeout_seconds=0.05
    )

    assert run.outcome is RunOutcome.BUDGET_EXHAUSTED
    assert run.answer == BUDGET_EXHAUSTED_ANSWER
    assert run.run_id == state.run_id
    assert time.monotonic() - started < 1


async def test_time_limit_cancels_the_planner_instead_of_abandoning_it() -> None:
    cancelled = False

    async def planner(state: AgentState) -> Plan:
        nonlocal cancelled
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled = True
            raise
        raise AssertionError("unreachable")

    await run_graph(build_graph(planner=planner), _new_state(), timeout_seconds=0.05)

    assert cancelled


async def test_time_limit_is_logged_with_run_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = _new_state()

    with caplog.at_level(logging.WARNING):
        await run_graph(
            build_graph(planner=hanging_planner), state, timeout_seconds=0.05
        )

    [record] = caplog.records
    assert str(state.run_id) in record.getMessage()


async def test_timeout_error_raised_by_a_node_is_not_reported_as_time_limit() -> None:
    async def planner(state: AgentState) -> Plan:
        raise TimeoutError("raised by the node itself")

    with pytest.raises(TimeoutError, match="raised by the node itself"):
        await run_graph(
            build_graph(planner=planner), _new_state(), timeout_seconds=TIMEOUT
        )
