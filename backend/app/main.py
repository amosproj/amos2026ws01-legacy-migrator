"""SunsetTracker backend query API (tickets #24 and #25).

Minimal FastAPI application exposing the query endpoint the frontend needs:

- ``POST /api/chat``        submit a query, receive an NDJSON answer stream
- ``GET  /api/health``      liveness check (includes the active model name)
- ``GET  /api/repositories`` repository list for the frontend picker (mock stub)

The frontend (ticket #27, branch ``create-basic-query-interface``) is hosted
separately (no single origin), so CORS is enabled for the configured origins
instead of serving the frontend from this process.

LLM access (ticket #25) goes through the provider-agnostic ``LlmProvider``
seam: without ``LLM_BASE_URL``/``LLM_NAME`` a mock provider answers, with them
any OpenAI-compatible endpoint (local Ollama or a future external API).
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .llm import LlmError, create_llm_provider
from .query_service import QueryService, create_query_service
from .repositories import list_repositories
from .schemas import ChatRequest, DiffFile, DiffRequest, DiffResponse, HealthResponse

SERVICE_NAME = "sunsettracker-backend"
VERSION = "0.2.0"
logger = logging.getLogger(__name__)

# Comma-separated list of allowed origins, e.g. "http://localhost:3000,http://localhost:5173".
# Defaults to the Vite dev server origins.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    provider = create_llm_provider()
    app.state.llm_provider = provider
    app.state.query_service = create_query_service(provider)
    yield
    await provider.aclose()


app = FastAPI(title="SunsetTracker backend query API", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _event(kind: str, text: str) -> str:
    """One newline-delimited JSON stream event."""
    return json.dumps({"type": kind, "text": text}) + "\n"


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=VERSION,
        model=app.state.llm_provider.name,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """Submit one migration-status query and receive a streamed answer.

    The response is newline-delimited JSON: a ``sources`` event with the
    evidence labels, then ``content`` events with answer text deltas, or a
    single ``error`` event when the LLM provider fails. Invalid requests
    (empty/oversized query, wrong types) are rejected with HTTP 422 by the
    Pydantic request model.
    """
    service: QueryService = app.state.query_service

    async def events() -> AsyncIterator[str]:
        yield _event("sources", json.dumps(service.sources()))
        try:
            async for delta in service.stream_answer(request.query):
                yield _event("content", delta)
        except LlmError as exc:
            yield _event("error", str(exc))

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/api/repositories")
def repositories() -> list[dict]:
    """Mock repository list so the frontend picker works end to end.

    Real repository loading belongs to ticket #17; this stub only keeps the
    vertical slice testable.
    """
    return [repo.model_dump(by_alias=True) for repo in list_repositories()]


@app.post("/api/diff/explain", response_model=DiffResponse)
async def explain_diff(request: DiffRequest) -> DiffResponse:
    """Return a deterministic comparison until provider-backed Git access exists."""
    logger.info(
        "diff request received provider=%s repository=%s base=%s head=%s",
        request.provider,
        request.repository,
        request.base,
        request.head,
    )
    return DiffResponse(
        summary=(
            "Moves account lookups from the legacy service to the target API "
            "while preserving the billing worker contract."
        ),
        risk="medium",
        files=[
            DiffFile(
                path="src/account/account-service.ts",
                status="modified",
                additions=24,
                deletions=8,
                explanation=(
                    "Replaces the direct legacy database lookup with the typed "
                    "target Account API client."
                ),
                patch=(
                    "- const account = legacyDb.findAccount(accountId)\n"
                    "+ const account = await accountApi.getAccount(accountId)\n"
                    "+ return account"
                ),
            ),
            DiffFile(
                path="src/account/account-api.ts",
                status="added",
                additions=38,
                deletions=0,
                explanation="Adds the HTTP boundary used by the migrated account service.",
                patch=(
                    "+ export async function getAccount(accountId: string) {\n"
                    "+   return client.get(`/accounts/${accountId}`)\n"
                    "+ }"
                ),
            ),
        ],
        warnings=["The billing worker still calls the legacy account service directly."],
    )
