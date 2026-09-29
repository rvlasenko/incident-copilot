from uuid import uuid4

import pytest

from incident_copilot.agent.graph import build_graph, run_graph
from incident_copilot.agent.nodes import PLANNER_UNAVAILABLE_ANSWER, Node
from incident_copilot.agent.state import AgentState, Route, RunOutcome
from tests.fakes import failing_planner, fixed_route_graph


def _new_state() -> AgentState:
    return AgentState(run_id=uuid4(), query="why is checkout failing?")


@pytest.mark.parametrize(
    ("route", "expected_outcome"),
    [
        (Route.RETRIEVAL_ONLY, RunOutcome.COMPLETED),
        (Route.INVESTIGATION, RunOutcome.COMPLETED),
        (Route.CLARIFICATION, RunOutcome.CLARIFICATION_NEEDED),
        (Route.HANDOFF, RunOutcome.HANDED_OFF),
    ],
)
def test_every_route_finishes_with_expected_outcome(
    route: Route, expected_outcome: RunOutcome
) -> None:
    initial = _new_state()

    final = run_graph(fixed_route_graph(route), initial)

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
def test_route_determines_visited_nodes(
    route: Route, expected_path: list[Node]
) -> None:
    updates = fixed_route_graph(route).stream(_new_state(), stream_mode="updates")

    visited = [node for update in updates for node in update]

    assert visited == expected_path


def test_planner_failure_hands_off_without_running_other_nodes() -> None:
    graph = build_graph(planner=failing_planner)

    visited = [
        node
        for update in graph.stream(_new_state(), stream_mode="updates")
        for node in update
    ]
    run = run_graph(graph, _new_state())

    assert visited == [Node.PLANNER]
    assert run.outcome is RunOutcome.HANDED_OFF
    assert run.answer == PLANNER_UNAVAILABLE_ANSWER
