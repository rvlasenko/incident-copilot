"""Test doubles shared by several test modules."""

from dataclasses import dataclass, field

from pydantic import BaseModel

from incident_copilot.agent.graph import AgentGraph, build_graph
from incident_copilot.agent.state import AgentState, Plan, Route
from incident_copilot.llm.base import LLMError


def fixed_route_graph(route: Route) -> AgentGraph:
    return build_graph(
        planner=lambda _state: Plan(route=route, rationale=f"forced {route}")
    )


def failing_planner(state: AgentState) -> Plan:
    raise LLMError("simulated provider outage")


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

    def generate[ModelT: BaseModel](
        self, *, system: str, user: str, schema: type[ModelT]
    ) -> ModelT:
        self.calls.append(ProviderCall(system=system, user=user, schema=schema))
        if isinstance(self.result, LLMError):
            raise self.result
        assert isinstance(self.result, schema)
        return self.result
