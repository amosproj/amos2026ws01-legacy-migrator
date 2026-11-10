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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .llm import LlmError, create_llm_provider
from .query_service import QueryService, create_query_service
from .repositories import list_repositories
from .schemas import ChatRequest, DiffFile, DiffRequest, DiffResponse, HealthResponse
from .source_fragments import (
    FragmentPosition,
    SourceFragment,
    SourceFragmentError,
    resolve_fragment,
)

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
    # Wire the #17-backed fragment fetcher when the loader outputs exist.
    # Absence is fine: /api/source-fragment reports a structured error then.
    app.state.fragment_fetcher = _create_fragment_fetcher()
    yield
    await provider.aclose()


def _create_fragment_fetcher() -> object | None:
    """Build the #17-backed fetcher from a loader dump, if one is configured.

    The loader runs offline (ingestion is not part of request handling), so the
    API reads the last produced load-result JSON instead of checking out again.
    """
    path = os.environ.get("SOURCE_LOAD_RESULT", "").strip()
    if not path:
        return None
    try:
        import json

        from .source_loader_adapter import LoaderFragmentFetcher

        with open(path, encoding="utf-8") as handle:
            return LoaderFragmentFetcher.from_load_result_json(json.load(handle))
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("fragment fetcher disabled: %s", exc)
        return None


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
    evidence labels, then ``thinking`` events with reasoning deltas (when the
    model produces them) and ``content`` events with answer text deltas, or a
    single ``error`` event when the LLM provider fails. Invalid requests
    (empty/oversized query, wrong types) are rejected with HTTP 422 by the
    Pydantic request model.
    """
    service: QueryService = app.state.query_service

    async def events() -> AsyncIterator[str]:
        yield _event("sources", json.dumps(service.sources()))
        try:
            async for kind, delta in service.stream_answer(request.query):
                yield _event(kind, delta)
        except LlmError as exc:
            yield _event("error", str(exc))

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.post("/api/source-fragment", response_model=SourceFragment)
def source_fragment(position: FragmentPosition) -> SourceFragment:
    """Resolve one graph-node position into the concrete source fragment.

    The position comes from graph nodes (#19 ``SourceSpan``): repository,
    stage, path, pinned commit and line range. The fragment is served from the
    reference checkout loaded by the #17 loader — no indexing of the source
    itself (#67 scope revision). Unresolvable positions fail with a structured
    error instead of returning empty content.
    """
    fetcher = getattr(app.state, "fragment_fetcher", None)
    try:
        if fetcher is None:
            raise SourceFragmentError(
                "fetcher_unavailable",
                "no reference source is loaded; start the backend with the "
                "reference loader configured (ticket #17)",
            )
        return resolve_fragment(position, fetcher)
    except SourceFragmentError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "message": str(exc)}
        ) from exc


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
