from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI

from incident_copilot.agent.graph import AgentGraph, build_graph, run_graph
from incident_copilot.agent.state import AgentState
from incident_copilot.api.schemas import AssistRequest, AssistResponse


class HealthStatus(StrEnum):
    OK = "ok"


# В тестах можно передать граф с фейковым planner.
def create_app(graph: AgentGraph | None = None) -> FastAPI:
    agent_graph = graph if graph is not None else build_graph()
    app = FastAPI(title="incident-copilot")

    @app.get("/health")
    def health() -> dict[str, HealthStatus]:
        return {"status": HealthStatus.OK}

    @app.post("/assist")
    def assist(request: AssistRequest) -> AssistResponse:
        run = run_graph(agent_graph, AgentState(run_id=uuid4(), query=request.query))
        return AssistResponse(run_id=run.run_id, outcome=run.outcome, answer=run.answer)

    return app


app = create_app()
