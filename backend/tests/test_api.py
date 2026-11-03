"""Pytest coverage for the query API request/response contract (tickets #24/#25)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _mock_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No provider configured: the API must run on the mock LLM provider."""
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_NAME", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def _parse_events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_health_returns_ok_with_model() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sunsettracker-backend"
    assert isinstance(body["version"], str)
    assert body["model"] == "mock"


def test_chat_streams_sources_then_content() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": "How far along is the migration?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _parse_events(response)
    assert events[0]["type"] == "sources"
    assert json.loads(events[0]["text"]) == ["llm:mock"]
    content = "".join(e["text"] for e in events if e["type"] == "content")
    assert "Mock LLM reply" in content


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
