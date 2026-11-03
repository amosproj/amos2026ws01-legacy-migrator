"""LLM provider seam (ticket #25).

LLM access is abstracted behind the ``LlmProvider`` protocol so that no
application component depends on one specific provider. Two implementations
ship with this ticket:

- ``MockLlmProvider`` — deterministic stand-in used when no provider is
  configured, so development and tests run without any model endpoint.
- ``OpenAiCompatibleProvider`` — talks to any OpenAI-compatible
  ``/chat/completions`` endpoint (a local Ollama server or a future external
  API provider). Supports both non-streaming and streaming completion calls.

Provider selection is externalized via environment variables; there is no
default target, so an unconfigured deployment never falls back to a public
endpoint. Server/model-specific request fields (e.g. a reasoning toggle such
as ``{"think": false}`` for thinking models) live in the external
``LLM_EXTRA_BODY`` config, never as model-specific logic in this module:
switching models or servers only means changing that config.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx2
from pydantic import BaseModel

REQUEST_TIMEOUT = httpx2.Timeout(float(os.environ.get("LLM_TIMEOUT_SECONDS", "600")), connect=15.0)


class LlmError(Exception):
    """The LLM provider could not produce an answer (transport or HTTP error)."""


def _load_extra_body() -> dict[str, Any]:
    """Server/model-specific request fields, merged into every completion call.

    Set ``LLM_EXTRA_BODY`` to a JSON object, e.g. ``{"think": false}``.
    """
    raw = os.environ.get("LLM_EXTRA_BODY", "").strip()
    if not raw:
        return {}
    return json.loads(raw)


class LlmProvider(Protocol):
    """Minimal contract every LLM provider must fulfil."""

    name: str

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        """Return one non-streaming completion for the given chat messages."""
        ...

    def stream_reply(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Yield answer text deltas as they arrive from the model."""
        ...

    async def aclose(self) -> None: ...


class _Message(BaseModel):
    content: str | None = None


class _Choice(BaseModel):
    message: _Message


class _Completion(BaseModel):
    choices: list[_Choice] = []


class MockLlmProvider:
    """Development stand-in so the application runs without a model endpoint."""

    name = "mock"

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        return (
            "Mock LLM reply: no LLM provider is configured, so the prompt was not "
            f"sent anywhere. Echo of the last user message: {str(last_user)[:120]!r}."
        )

    async def stream_reply(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        yield await self.complete(messages)

    async def aclose(self) -> None:
        pass


class OpenAiCompatibleProvider:
    """Calls an OpenAI-compatible ``/chat/completions`` endpoint (ticket #25).

    Works with a local Ollama server (``http://127.0.0.1:11434/v1``) and, later,
    with any external API provider that exposes the same contract — swapping
    providers only changes configuration, not this class.
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = f"openai-compatible ({model_name})"
        self._model_name = model_name
        self._url = base_url.rstrip("/") + "/chat/completions"
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client_kwargs: dict[str, Any] = {"timeout": REQUEST_TIMEOUT, "headers": headers}
        if transport is not None:
            client_kwargs["transport"] = transport
        self._http = httpx2.AsyncClient(**client_kwargs)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            **_load_extra_body(),
        }
        try:
            response = await self._http.post(self._url, json=payload)
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            raise LlmError(f"LLM provider request failed: {exc}") from exc
        completion = _Completion.model_validate(response.json())
        if not completion.choices:
            return ""
        return (completion.choices[0].message.content or "").strip()

    async def stream_reply(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": True,
            **_load_extra_body(),
        }
        try:
            async with self._http.stream("POST", self._url, json=payload) as response:
                if response.status_code != 200:
                    detail = (await response.aread()).decode("utf-8", "replace")
                    raise LlmError(
                        f"LLM provider error (HTTP {response.status_code}): {detail[:300]}"
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    content = delta.get("content")
                    if content:
                        yield content
        except httpx2.HTTPError as exc:
            raise LlmError(f"LLM provider request failed: {exc}") from exc


def create_llm_provider() -> LlmProvider:
    """Build the configured provider; falls back to the mock when unset.

    ``LLM_BASE_URL`` and ``LLM_NAME`` select a real provider. ``LLM_API_KEY`` is
    optional for local servers (e.g. Ollama) and required for external APIs.
    """
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model_name = os.environ.get("LLM_NAME", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if base_url and model_name:
        return OpenAiCompatibleProvider(base_url, model_name, api_key)
    return MockLlmProvider()
