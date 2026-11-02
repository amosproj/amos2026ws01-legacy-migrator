"""Pytest coverage for the query API request/response contract (tickets #24/#25)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _mock_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No provider configured: the API must run on the mock LLM provider."""
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_NAME", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sunsettracker-backend"
    assert isinstance(body["version"], str)


def test_chat_returns_structured_mock_answer() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": "How far along is the migration?"})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["answer"], str) and body["answer"]
    assert "Mock LLM reply" in body["answer"]
    assert isinstance(body["sources"], list)
    assert all(isinstance(source, str) for source in body["sources"])


def test_chat_echoes_conversation_id() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/chat", json={"query": "What is coupled?", "conversation_id": "conv-1"}
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conv-1"


def test_chat_rejects_empty_query() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": ""})

    assert response.status_code == 422


def test_chat_rejects_missing_query() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={})

    assert response.status_code == 422


def test_chat_rejects_oversized_query() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": "x" * 32_001})

    assert response.status_code == 422


def test_chat_rejects_wrong_type() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": ["not", "a", "string"]})

    assert response.status_code == 422


def test_repositories_returns_camel_case_list() -> None:
    with TestClient(app) as client:
        response = client.get("/api/repositories")

    assert response.status_code == 200
    repositories = response.json()
    assert isinstance(repositories, list) and repositories
    first = repositories[0]
    # The frontend Repository type expects camelCase field names.
    for key in ("id", "provider", "providerLabel", "fullName", "defaultBranch", "isPrivate"):
        assert key in first
