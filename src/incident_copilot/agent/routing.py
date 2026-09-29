"""Where the run goes next. Routers are plain code reading the plan: the LLM proposes, code decides."""

from langgraph.graph import END

from incident_copilot.agent.nodes import Node
from incident_copilot.agent.state import AgentState, GraphInvariantError, Route


def route_after_planner(state: AgentState) -> Node | str:
    # The planner node may already have finished the run (planner failure).
    if state.is_finished:
        return END
    match state.require_plan().route:
        case Route.RETRIEVAL_ONLY | Route.INVESTIGATION:
            return Node.RETRIEVAL
        case Route.CLARIFICATION:
            return Node.CLARIFY
        case Route.HANDOFF:
            return Node.HANDOFF


def route_after_retrieval(state: AgentState) -> Node:
    match state.require_plan().route:
        case Route.INVESTIGATION:
            return Node.EXECUTOR
        case Route.RETRIEVAL_ONLY:
            return Node.ANSWER
        case route:
            raise GraphInvariantError(f"Route {route} must not reach retrieval")
