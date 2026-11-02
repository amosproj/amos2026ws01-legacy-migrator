"""SunsetTracker backend query API (ticket #24).

Minimal FastAPI application exposing the query endpoint the frontend needs:

- ``POST /api/chat``        submit a query, get a structured answer
- ``GET  /api/health``      liveness check
- ``GET  /api/repositories`` repository list for the frontend picker (mock stub)

The frontend (ticket #27, branch ``create-basic-query-interface``) is hosted
separately (no single origin), so CORS is enabled for the configured origins
instead of serving the frontend from this process.

The LLM provider interface (ticket #25) is intentionally NOT implemented here;
answers currently come from the mock query service.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .query_service import QueryService, create_query_service
from .repositories import list_repositories
from .schemas import ChatRequest, ChatResponse, HealthResponse

SERVICE_NAME = "sunsettracker-backend"
VERSION = "0.1.0"

# Comma-separated list of allowed origins, e.g. "http://localhost:5173".
# Defaults to the Vite dev server origin.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.query_service = create_query_service()
    yield


app = FastAPI(title="SunsetTracker backend query API", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, version=VERSION)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Submit one migration-status query and receive a structured answer.

    Invalid requests (empty/oversized query, wrong types) are rejected with
    HTTP 422 by the Pydantic request model.
    """
    service: QueryService = app.state.query_service
    result = service.answer(request.query, request.conversation_id)
    return ChatResponse(
        answer=result.answer,
        conversation_id=request.conversation_id,
        sources=list(result.sources),
    )


@app.get("/api/repositories")
def repositories() -> list[dict]:
    """Mock repository list so the frontend picker works end to end.

    Real repository loading belongs to ticket #17; this stub only keeps the
    vertical slice testable.
    """
    return [repo.model_dump(by_alias=True) for repo in list_repositories()]
