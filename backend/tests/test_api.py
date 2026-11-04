"""Pytest coverage for the query API request/response contract (tickets #24/#25)."""

import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.llm import LlmError
from app.main import app
from app.query_service import LlmQueryService


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


def test_chat_streams_thinking_events_from_provider() -> None:
    """Reasoning deltas from the provider surface as thinking events."""
    class ThinkingMockProvider:
        name = "thinking-mock"

        async def complete(self, messages):
            return "done"

        async def stream_reply(self, messages):
            yield ("thinking", "reasoning step")
            yield ("content", "Answer")
            yield ("content", " text")

        async def aclose(self) -> None:
            pass

    original_state = dict(app.state._state)
    try:
        with TestClient(app) as client:
            app.state.query_service = LlmQueryService(ThinkingMockProvider())
            response = client.post("/api/chat", json={"query": "q"})
    finally:
        app.state._state.clear()
        app.state._state.update(original_state)

    events = _parse_events(response)
    kinds = [e["type"] for e in events]
    assert kinds == ["sources", "thinking", "content", "content"]
    assert events[1] == {"type": "thinking", "text": "reasoning step"}
    content = "".join(e["text"] for e in events if e["type"] == "content")
    assert content == "Answer text"


def test_chat_passes_query_to_query_service() -> None:
    calls: list[str] = []

    class RecordingQueryService:
        def sources(self) -> list[str]:
            return ["test:source"]

        def stream_answer(self, query: str):
            calls.append(query)
            async def stream():
                yield ("content", "recorded")

            return stream()

    with TestClient(app) as client:
        app.state.query_service = RecordingQueryService()
        response = client.post(
            "/api/chat", json={"query": "test", "conversation_id": "step-06"}
        )

    assert response.status_code == 200
    assert calls == ["test"]
    assert "recorded" in response.text


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


def test_chat_maps_llm_abort_error_to_actionable_gateway_error() -> None:
    class FailingQueryService:
        def sources(self) -> list[str]:
            return []

        def stream_answer(self, query: str) -> AsyncIterator[str]:
            async def stream() -> AsyncIterator[str]:
                raise LlmError("signal is aborted without reason")
                yield ""

            return stream()

    with TestClient(app) as client:
        app.state.query_service = FailingQueryService()
        response = client.post("/api/chat", json={"query": "test"})

    assert response.status_code == 200
    events = _parse_events(response)
    assert events[-1] == {"type": "error", "text": "signal is aborted without reason"}


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
    assert first["branches"]


def test_diff_explain_returns_structured_comparison() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/diff/explain",
            json={
                "repository": "amosproj/example",
                "provider": "github",
                "base": "main",
                "head": "feature/account-api",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["risk"] == "medium"
    assert body["files"][0]["path"] == "src/account/account-service.ts"
    assert body["warnings"]


def test_diff_explain_rejects_invalid_provider() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/diff/explain",
            json={
                "repository": "amosproj/example",
                "provider": "unknown",
                "base": "main",
                "head": "feature",
            },
        )

    assert response.status_code == 422
