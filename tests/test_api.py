import pytest
from fastapi.testclient import TestClient

from incident_copilot.api.app import create_app
from incident_copilot.api.schemas import MAX_QUERY_LENGTH


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_assist_returns_run_id_and_answer(client: TestClient) -> None:
    response = client.post("/assist", json={"query": "why is checkout failing?"})

    assert response.status_code == 200
    assert response.json()["answer"]


def test_assist_rejects_whitespace_query(client: TestClient) -> None:
    response = client.post("/assist", json={"query": "  "})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "query"]


def test_assist_accepts_query_at_max_length(client: TestClient) -> None:
    response = client.post("/assist", json={"query": "a" * MAX_QUERY_LENGTH})

    assert response.status_code == 200


def test_assist_rejects_query_over_max_length(client: TestClient) -> None:
    response = client.post("/assist", json={"query": "a" * (MAX_QUERY_LENGTH + 1)})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "query"]


def test_health_returns_status_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assist_returns_outcome_of_finished_run(client: TestClient) -> None:
    response = client.post("/assist", json={"query": "why is checkout failing?"})

    assert response.json()["outcome"] == "completed"
