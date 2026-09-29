"""Graph wiring: which nodes exist and how they connect.

planner -> retrieval_only: retrieval -> answer
        -> investigation:  retrieval -> executor -> verifier -> answer
        -> clarification:  clarify
        -> handoff:        handoff
        -> planner failed: END (run already finished as handed_off)
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agent.nodes import (
    Node,
    Planner,
    answer_node,
    clarify_node,
    executor_node,
    handoff_node,
    make_plan_node,
    retrieval_node,
    verifier_node,
)
from incident_copilot.agent.routing import route_after_planner, route_after_retrieval
from incident_copilot.agent.state import AgentState, FinishedRun, GraphInvariantError

type AgentGraph = CompiledStateGraph[AgentState, None, AgentState, AgentState]


def build_graph(planner: Planner) -> AgentGraph:
    """The planner is injected so tests can force any route without an LLM."""
    graph = StateGraph(AgentState)
    graph.add_node(Node.PLANNER, make_plan_node(planner))
    graph.add_node(Node.RETRIEVAL, retrieval_node)
    graph.add_node(Node.EXECUTOR, executor_node)
    graph.add_node(Node.VERIFIER, verifier_node)
    graph.add_node(Node.ANSWER, answer_node)
    graph.add_node(Node.CLARIFY, clarify_node)
    graph.add_node(Node.HANDOFF, handoff_node)

    graph.add_edge(START, Node.PLANNER)
    graph.add_conditional_edges(Node.PLANNER, route_after_planner)
    graph.add_conditional_edges(Node.RETRIEVAL, route_after_retrieval)
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
