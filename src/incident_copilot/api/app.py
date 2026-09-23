from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI

from incident_copilot.api.schemas import AssistRequest, AssistResponse


class HealthStatus(StrEnum):
    OK = "ok"


def create_app() -> FastAPI:
    app = FastAPI(title="incident-copilot")

    @app.get("/health")
    def health() -> dict[str, HealthStatus]:
        return {"status": HealthStatus.OK}

    @app.post("/assist")
    def assist(request: AssistRequest) -> AssistResponse:
        return AssistResponse(
            run_id=uuid4(),
            answer=f"Received: {request.query}",
        )

    return app


app = create_app()
