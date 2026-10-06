"""What each step of the graph does. Nodes return partial state updates.

Only the planner is real so far; the other nodes are stubs filled in by later weeks.
Nodes that wait on I/O are async so a run can be cancelled while they wait.
"""

import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, Protocol

from incident_copilot.agent.planner import PLANNER_PROMPT_VERSION
from incident_copilot.agent.state import AgentState, Plan, RunOutcome
from incident_copilot.llm.base import LLMError

logger = logging.getLogger(__name__)

type Planner = Callable[[AgentState], Awaitable[Plan]]
type StateUpdate = dict[str, Any]

PLANNER_UNAVAILABLE_ANSWER = (
    "The planner is unavailable right now, so this request was not analysed. "
    "Please investigate manually or retry later."
)


class AsyncNodeFunction(Protocol):
    # A Protocol, not Callable: LangGraph requires the parameter to be named `state`.
    async def __call__(self, state: AgentState) -> StateUpdate: ...


class Node(StrEnum):
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    ANSWER = "answer"
    CLARIFY = "clarify"
    HANDOFF = "handoff"


def make_plan_node(planner: Planner) -> AsyncNodeFunction:
    """The planner is a dependency, so its node is built by a factory."""

    async def plan_node(state: AgentState) -> StateUpdate:
        try:
            return {"plan": await planner(state)}
        except LLMError as exc:
            # A planner failure ends the run cleanly instead of failing the request.
            logger.warning(
                "Planner failed, handing off: run_id=%s prompt_version=%s error_type=%s status_code=%s",
                state.run_id,
                PLANNER_PROMPT_VERSION,
                exc.error_type,
                exc.status_code,
            )
            return {
                "outcome": RunOutcome.HANDED_OFF,
                "answer": PLANNER_UNAVAILABLE_ANSWER,
            }

    return plan_node


def retrieval_node(state: AgentState) -> StateUpdate:
    return {}


def executor_node(state: AgentState) -> StateUpdate:
    return {}


def verifier_node(state: AgentState) -> StateUpdate:
    return {}


def answer_node(state: AgentState) -> StateUpdate:
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
        "answer": f"Handed off to a human: {state.require_plan().rationale}",
    }
