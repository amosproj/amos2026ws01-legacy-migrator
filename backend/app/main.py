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
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from shared_contracts.records import SnapshotIdentity

from .graph_fragments import resolve_question_fragments
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
from .source_loader_adapter import LoaderFragmentFetcher

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
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    provider = create_llm_provider()
    app.state.llm_provider = provider
    app.state.query_service = create_query_service(provider)
    fetcher, identity, config_error = await run_in_threadpool(_load_source_context)
    app.state.fragment_fetcher = fetcher
    app.state.graph_identity = identity
    app.state.graph_config_error = config_error
    yield
    await provider.aclose()


def _load_source_context() -> tuple[
    LoaderFragmentFetcher | None, SnapshotIdentity | None, str | None
]:
    run_path = os.environ.get("GRAPH_RUN_DIR", "").strip()
    source_path = os.environ.get("SOURCE_LOAD_RESULT", "").strip()
    if not run_path and not source_path:
        return None, None, None

    export = Path(run_path) / "sources.jsonl" if run_path else Path(source_path)
    try:
        fetcher = LoaderFragmentFetcher.from_export(export)
    except (OSError, ValueError) as exc:
        logger.warning("fragment fetcher disabled: %s", exc)
        return (
            None,
            None,
            "The configured graph run has no readable sources.jsonl." if run_path else None,
        )

    if not run_path:
        return fetcher, None, None
    try:
        identity = SnapshotIdentity.model_validate_json(
            (Path(run_path) / "snapshot-identity.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        logger.warning("invalid graph run manifest: %s", exc)
        return fetcher, None, "The configured graph run has no valid snapshot-identity.json."
    return fetcher, identity, None


app = FastAPI(title="SunsetTracker backend query API", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _event(kind: str, text: str, *, code: str | None = None) -> str:
    """One newline-delimited JSON stream event."""
    payload = {"type": kind, "text": text}
    if code is not None:
        payload["code"] = code
    return json.dumps(payload) + "\n"


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

    The NDJSON stream includes model labels, resolved evidence when configured,
    reasoning and answer deltas, or a visible graph, source or model error.
    """
    service: QueryService = app.state.query_service

    async def events() -> AsyncIterator[str]:
        yield _event("sources", json.dumps(service.sources()))
        try:
            config_error: str | None = app.state.graph_config_error
            if config_error:
                raise SourceFragmentError("invalid_graph_run", config_error)
            fetcher: LoaderFragmentFetcher | None = app.state.fragment_fetcher
            identity: SnapshotIdentity | None = app.state.graph_identity
            evidence: list[SourceFragment] = []
            if identity is not None and fetcher is not None:
                legacy_step = request.conversation_id or ""
                step = request.step_id or (
                    legacy_step if legacy_step.startswith("step-") else "step-06"
                )
                evidence = await run_in_threadpool(
                    resolve_question_fragments, request.query, step, identity, fetcher
                )
                yield _event(
                    "evidence",
                    json.dumps(
                        [
                            fragment.model_dump(by_alias=True, mode="json", exclude_none=True)
                            for fragment in evidence
                        ]
                    ),
                )
            async for kind, delta in service.stream_answer(request.query, evidence=evidence):
                yield _event(kind, delta)
        except SourceFragmentError as exc:
            yield _event("error", str(exc), code=exc.code)
        except LlmError as exc:
            yield _event("error", str(exc))

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.post("/api/source-fragment", response_model=SourceFragment, response_model_exclude_none=True)
def source_fragment(position: FragmentPosition) -> SourceFragment:
    """Return the pinned lines and source link for a stage and source span."""
    fetcher: LoaderFragmentFetcher | None = getattr(app.state, "fragment_fetcher", None)
    try:
        if fetcher is None:
            raise SourceFragmentError(
                "fetcher_unavailable",
                "no reference source is loaded. Set SOURCE_LOAD_RESULT to a sources.jsonl export",
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
