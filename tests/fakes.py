"""Test doubles shared by several test modules."""

import asyncio
from dataclasses import dataclass, field

from pydantic import BaseModel

from incident_copilot.agent.graph import AgentGraph, build_graph
from incident_copilot.agent.state import AgentState, Plan, Route
from incident_copilot.llm.base import LLMError


def fixed_route_graph(route: Route) -> AgentGraph:
    async def planner(state: AgentState) -> Plan:
        return Plan(route=route, rationale=f"forced {route}")

    return build_graph(planner=planner)


async def hanging_planner(state: AgentState) -> Plan:
    """Never answers, like an LLM API that accepted the request and went silent."""
    await asyncio.sleep(3600)
    raise AssertionError("unreachable: the run must be cancelled first")


async def failing_planner(state: AgentState) -> Plan:
    raise LLMError("SimulatedOutage", status_code=503)


@dataclass(frozen=True)
class ProviderCall:
    system: str
    user: str
    schema: type[BaseModel]


@dataclass
class FakeProvider:
    """Returns a canned result (or raises it) and records every call."""

    result: BaseModel | LLMError
    calls: list[ProviderCall] = field(default_factory=list)

    async def generate[ModelT: BaseModel](
        self, *, system: str, user: str, schema: type[ModelT]
    ) -> ModelT:
        self.calls.append(ProviderCall(system=system, user=user, schema=schema))
        if isinstance(self.result, LLMError):
            raise self.result
        assert isinstance(self.result, schema)
        return self.result
