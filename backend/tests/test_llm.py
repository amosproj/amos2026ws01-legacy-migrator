"""Pytest coverage for the LLM provider seam (ticket #25)."""

import asyncio
import json
from typing import Any

import httpx2
import pytest

from app.llm import (
    LlmError,
    LlmProvider,
    MockLlmProvider,
    OpenAiCompatibleProvider,
    create_llm_provider,
)
from app.query_service import LlmQueryService


@pytest.fixture(autouse=True)
def _clean_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_NAME", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_EXTRA_BODY", raising=False)


def _completion_transport(answer: str, status_code: int = 200) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["stream"] is False
        assert request.headers.get("Authorization") == "Bearer test-key"
        return httpx2.Response(status_code, json={"choices": [{"message": {"content": answer}}]})

    return httpx2.MockTransport(handler)


def test_mock_provider_echoes_last_user_message() -> None:
    provider = MockLlmProvider()

    reply = asyncio.run(
        provider.complete(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]
        )
    )

    assert "Mock LLM reply" in reply
    assert "'hello'" in reply
    asyncio.run(provider.aclose())


def test_openai_compatible_provider_returns_completion() -> None:
    provider = OpenAiCompatibleProvider(
        "http://fake/v1", "test-model", "test-key", transport=_completion_transport("42%")
    )

    reply = asyncio.run(provider.complete([{"role": "user", "content": "progress?"}]))

    assert reply == "42%"
    assert provider.name == "openai-compatible (test-model)"
    asyncio.run(provider.aclose())


def test_openai_compatible_provider_raises_llm_error_on_http_error() -> None:
    provider = OpenAiCompatibleProvider(
        "http://fake/v1",
        "test-model",
        "test-key",
        transport=_completion_transport("", status_code=500),
    )

    with pytest.raises(LlmError):
        asyncio.run(provider.complete([{"role": "user", "content": "boom"}]))
    asyncio.run(provider.aclose())


def test_extra_body_is_merged_into_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Server/model-specific fields from LLM_EXTRA_BODY reach the request."""
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"think": false}')
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(json.loads(request.content))
        return httpx2.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAiCompatibleProvider(
        "http://fake/v1", "test-model", "", transport=httpx2.MockTransport(handler)
    )

    asyncio.run(provider.complete([{"role": "user", "content": "x"}]))

    assert seen["think"] is False
    assert seen["model"] == "test-model"
    asyncio.run(provider.aclose())


def test_openai_compatible_provider_handles_empty_choices() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"choices": []})

    provider = OpenAiCompatibleProvider(
        "http://fake/v1", "test-model", "", transport=httpx2.MockTransport(handler)
    )

    assert asyncio.run(provider.complete([{"role": "user", "content": "x"}])) == ""
    asyncio.run(provider.aclose())


def test_factory_returns_mock_without_configuration() -> None:
    provider = create_llm_provider()
    assert isinstance(provider, MockLlmProvider)


def test_factory_returns_openai_compatible_with_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LLM_NAME", "qwen3.5:2b")

    provider = create_llm_provider()

    assert isinstance(provider, OpenAiCompatibleProvider)
    assert provider.name == "openai-compatible (qwen3.5:2b)"


def test_provider_protocol_is_satisfied_by_both_implementations() -> None:
    """Both implementations fulfil the seam; consumers depend only on it."""
    providers: list[LlmProvider] = [MockLlmProvider()]
    assert all(hasattr(p, "complete") and hasattr(p, "aclose") for p in providers)


def test_query_service_sends_system_and_user_messages() -> None:
    """The query service sends system + user messages in OpenAI chat format."""
    captured: list[list[dict[str, Any]]] = []

    class RecordingProvider:
        name = "recording"

        async def complete(self, messages: list[dict[str, Any]]) -> str:
            captured.append(messages)
            return "ok"

        async def aclose(self) -> None:
            pass

    service = LlmQueryService(RecordingProvider())
    result = asyncio.run(service.answer("What is coupled?", None))

    assert result.answer == "ok"
    assert result.sources == ["llm:recording"]
    assert captured[0][0]["role"] == "system"
    assert captured[0][1] == {"role": "user", "content": "What is coupled?"}
