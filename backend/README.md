# Backend

Python/FastAPI application server of SunsetTracker. Built and hosted separately
from the frontend (no single origin).

This is the minimal query API from ticket #24 ("Create Backend Query API").
The LLM provider interface (ticket #25) is not implemented here yet; answers
currently come from a mock query service.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Submit a query: `{"query": "...", "conversation_id"?: "..."}` → `{"answer": "...", "conversation_id"?: "...", "sources": [...]}` |
| `/api/health` | GET | Liveness check (`{"status": "ok", ...}`) |
| `/api/repositories` | GET | Mock repository list for the frontend picker (real loading is ticket #17) |

The request/response contract matches the frontend adapters on the
`create-basic-query-interface` branch (`frontend/src/lib/chatAdapter.ts`,
`frontend/src/config/env.ts`). Invalid requests are rejected with HTTP 422.

## Setup and start

```bash
# from the repository root
./backend/run.sh          # creates .venv (uv), installs deps, runs uvicorn on :8000
```

Or manually:

```bash
cd backend
uv sync                   # or: python -m venv .venv && pip install -e .
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Tests

```bash
cd backend
uv run pytest
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins allowed to call this API (the separately hosted frontend) |

## Structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app, routes, CORS
│   ├── schemas.py         # Pydantic request/response models
│   ├── query_service.py   # QueryService seam + mock implementation
│   └── repositories.py    # mock repository list (ticket #17 stub)
├── tests/
│   └── test_api.py        # API contract tests
├── pyproject.toml
└── run.sh                 # one-command local start
```

The `QueryService` protocol in `app/query_service.py` is the seam where the
LLM provider interface (ticket #25) and the knowledge-graph query logic will
be plugged in later without changing the API layer.