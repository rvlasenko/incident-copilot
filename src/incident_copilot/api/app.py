from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI

from incident_copilot.agent.graph import AgentGraph, run_graph
from incident_copilot.agent.state import AgentState
from incident_copilot.api.schemas import AssistRequest, AssistResponse


class HealthStatus(StrEnum):
    OK = "ok"


def create_app(graph: AgentGraph) -> FastAPI:
    app = FastAPI(title="incident-copilot")

    @app.get("/health")
    def health() -> dict[str, HealthStatus]:
        return {"status": HealthStatus.OK}

    @app.post("/assist")
    def assist(request: AssistRequest) -> AssistResponse:
        run = run_graph(graph, AgentState(run_id=uuid4(), query=request.query))
        return AssistResponse(
            run_id=run.run_id,
            outcome=run.outcome,
            answer=run.answer,
        )

    return app
