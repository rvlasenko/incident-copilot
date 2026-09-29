"""Week-1 skeleton of the agent graph: real routing, stub node logic.

planner -> retrieval_only: retrieval -> answer
        -> investigation:  retrieval -> executor -> verifier -> answer
        -> clarification:  clarify
        -> handoff:        handoff
"""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agent.state import (
    AgentState,
    FinishedRun,
    Plan,
    Route,
    RunOutcome,
)

type Planner = Callable[[AgentState], Plan]
type StateUpdate = dict[str, Any]
type AgentGraph = CompiledStateGraph[AgentState, None, AgentState, AgentState]


class Node(StrEnum):
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    ANSWER = "answer"
    CLARIFY = "clarify"
    HANDOFF = "handoff"


class GraphInvariantError(RuntimeError):
    """The graph reached a state its own wiring should make impossible."""


def stub_planner(state: AgentState) -> Plan:
    return Plan(
        route=Route.RETRIEVAL_ONLY, rationale="Stub planner: always retrieval-only"
    )


def build_graph(planner: Planner = stub_planner) -> AgentGraph:
    """The planner is injected so tests can force any route without an LLM."""

    def plan_node(state: AgentState) -> StateUpdate:
        return {"plan": planner(state)}

    def retrieval_node(state: AgentState) -> StateUpdate:
        return {}

    def executor_node(state: AgentState) -> StateUpdate:
        return {}

    def verifier_node(state: AgentState) -> StateUpdate:
        return {}

    def answer_node(state: AgentState) -> StateUpdate:
        # Ноды возвращают частичное обновление, например {"plan": ...}, а LangGraph сам сливает его со state
        return {
            "outcome": RunOutcome.COMPLETED,
            "answer": f"Stub answer for: {state.query}",
        }

    def clarify_node(state: AgentState) -> StateUpdate:
        return {
            "outcome": RunOutcome.CLARIFICATION_NEEDED,
            "answer": "Please clarify which service and time window you mean.",
        }

    def handoff_node(state: AgentState) -> StateUpdate:
        return {
            "outcome": RunOutcome.HANDED_OFF,
            "answer": f"Handed off to a human: {_require_plan(state).rationale}",
        }

    graph = StateGraph(AgentState)
    graph.add_node(Node.PLANNER, plan_node)
    graph.add_node(Node.RETRIEVAL, retrieval_node)
    graph.add_node(Node.EXECUTOR, executor_node)
    graph.add_node(Node.VERIFIER, verifier_node)
    graph.add_node(Node.ANSWER, answer_node)
    graph.add_node(Node.CLARIFY, clarify_node)
    graph.add_node(Node.HANDOFF, handoff_node)

    graph.add_edge(START, Node.PLANNER)
    graph.add_conditional_edges(Node.PLANNER, _route_after_planner)
    graph.add_conditional_edges(Node.RETRIEVAL, _route_after_retrieval)
    graph.add_edge(Node.EXECUTOR, Node.VERIFIER)
    graph.add_edge(Node.VERIFIER, Node.ANSWER)
    graph.add_edge(Node.ANSWER, END)
    graph.add_edge(Node.CLARIFY, END)
    graph.add_edge(Node.HANDOFF, END)
    return graph.compile()


def run_graph(graph: AgentGraph, state: AgentState) -> FinishedRun:
    # invoke() returns a plain dict, and the last node's update is never validated
    # on the way in to another node, so the result is validated here explicitly.
    final = AgentState.model_validate(graph.invoke(state))
    if final.outcome is None or final.answer is None:
        raise GraphInvariantError(f"Run {final.run_id} ended without an outcome")
    return FinishedRun(run_id=final.run_id, outcome=final.outcome, answer=final.answer)


def _require_plan(state: AgentState) -> Plan:
    if state.plan is None:
        raise GraphInvariantError(
            f"Run {state.run_id} has no plan after the planner node"
        )
    return state.plan


# LLM выбирает маршрут, код решает, куда идти. Это принцип «LLM предлагает, код решает».
def _route_after_planner(state: AgentState) -> Node:
    match _require_plan(state).route:
        case Route.RETRIEVAL_ONLY | Route.INVESTIGATION:
            return Node.RETRIEVAL
        case Route.CLARIFICATION:
            return Node.CLARIFY
        case Route.HANDOFF:
            return Node.HANDOFF


def _route_after_retrieval(state: AgentState) -> Node:
    match _require_plan(state).route:
        case Route.INVESTIGATION:
            return Node.EXECUTOR
        case Route.RETRIEVAL_ONLY:
            return Node.ANSWER
        case route:
            raise GraphInvariantError(f"Route {route} must not reach retrieval")
