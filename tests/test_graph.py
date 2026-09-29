from uuid import uuid4

import pytest

from incident_copilot.agent.graph import AgentGraph, Node, build_graph, run_graph
from incident_copilot.agent.state import AgentState, Plan, Route, RunOutcome


def _graph_with_route(route: Route) -> AgentGraph:
    return build_graph(
        planner=lambda _state: Plan(route=route, rationale=f"forced {route}")
    )


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

    final = run_graph(_graph_with_route(route), initial)

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
    updates = _graph_with_route(route).stream(_new_state(), stream_mode="updates")

    visited = [node for update in updates for node in update]

    assert visited == expected_path
