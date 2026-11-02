# Backend

Python/FastAPI application server of SunsetTracker. Built and hosted separately
from the frontend (no single origin).

This is the minimal query API from ticket #24 ("Create Backend Query API")
plus the LLM provider interface from ticket #25 ("Implementation LLM Provider
Interface"). LLM access is abstracted behind a provider-agnostic seam: without
configuration a mock provider answers; with configuration any OpenAI-compatible
endpoint is used (a local Ollama server or a future external API provider).

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Submit a query: `{"query": "...", "conversation_id"?: "..."}` → NDJSON stream: `sources` event, then `content` text deltas, or an `error` event |
| `/api/health` | GET | Liveness check (`{"status": "ok", ..., "model": "..."}`) |
| `/api/repositories` | GET | Mock repository list for the frontend picker (real loading is ticket #17) |

The chat answer is streamed as newline-delimited JSON so the frontend can
render tokens as they arrive and cancel long-running generations. Invalid
requests are rejected with HTTP 422; LLM failures arrive as an `error` event
inside the stream.

## Setup and start

Full installation instructions (Linux and Windows): see [SETUP.md](SETUP.md).

Start everything with one command:

- Linux: `./run.sh` — starts Ollama (if not running) and the backend in this terminal
- Windows: `.\run.ps1` — opens one Windows Terminal window with a tab per process

Both scripts wire the backend to the local Ollama server automatically; without
Ollama the backend still runs and answers with a mock provider.

## Tests

```bash
cd backend
uv run pytest
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins allowed to call this API (the separately hosted frontend) |
| `LLM_BASE_URL` | *(unset → mock)* | Base URL of an OpenAI-compatible endpoint, e.g. `http://127.0.0.1:11434/v1` for a local Ollama server |
| `LLM_NAME` | *(unset → mock)* | Model name to request, e.g. `qwen3.5:2b` |
| `LLM_API_KEY` | *(empty)* | API key for external providers; may stay empty for local servers |
| `LLM_TIMEOUT_SECONDS` | `600` | Request timeout for LLM calls (local CPU inference can be slow) |
| `LLM_EXTRA_BODY` | *(empty)* | JSON object merged into every completion request for server/model-specific fields, e.g. `{"think": false}` to disable reasoning on thinking models |

Example — run against a local Ollama server (thinking disabled for speed):

```bash
LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_NAME=qwen3.5:0.8b \
  LLM_EXTRA_BODY='{"think": false}' ./backend/run.sh
```

## Structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app, routes, CORS, provider lifecycle
│   ├── schemas.py         # Pydantic request/response models
│   ├── query_service.py   # QueryService seam (mock + LLM-backed)
│   ├── llm.py             # LlmProvider seam (mock + OpenAI-compatible)
│   └── repositories.py    # mock repository list (ticket #17 stub)
├── tests/
│   ├── test_api.py        # API contract tests
│   └── test_llm.py        # LLM provider seam tests
├── pyproject.toml
├── run.sh                 # one-command start (Linux)
├── run.ps1                # one-command start (Windows Terminal)
└── SETUP.md               # installation instructions (Linux and Windows)
```

The `LlmProvider` protocol in `app/llm.py` is the seam for ticket #25: adding a
new provider (e.g. an external API) only requires a new implementation plus
configuration — consuming components never change. The `QueryService` protocol
in `app/query_service.py` is where the knowledge-graph query logic will be
plugged in later without changing the API layer.

## Known limitations / future work

- **No knowledge-graph context yet.** Answers come from the LLM alone; the
  ingestion and graph query logic (tickets #17, #52) will feed evidence into
  the prompt later.