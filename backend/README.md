# Backend

Python backend of SunsetTracker. It has two parts:

1. **Query API** (FastAPI, tickets #24/#25): the application server the
   frontend talks to. It streams LLM-backed answers through a provider-agnostic
   seam: without configuration a mock provider answers; with configuration any
   OpenAI-compatible endpoint is used (a local Ollama server or a future
   external API provider).
2. **Ingestion pipeline**, including the reference loader (ticket #17): checks
   out a reference stage, loads its files, and generates component graphs and
   canonical facts. Setup, configuration, usage and tests are described in the
   [pipeline setup guide](code-ingestion-pipeline/README.md).

Run all commands from this folder.

## API (query server)

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

## Tests and CI checks

The GitHub Actions workflow (`.github/workflows/backend-tests.yml`) runs
automatically on pull requests and pushes to `main` and `develop` when files in
`backend/` or the workflow file change. It checks formatting, linting, types,
both unit test suites, bytecode compilation, and API startup.

Run the same checks from `backend/`:

```bash
cd backend
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest tests -v
uv run --directory code-ingestion-pipeline --project .. pytest tests -v
uv run python -m compileall -q app shared_contracts code-ingestion-pipeline/src
uv run python -c "
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    r = client.get('/api/health')
    assert r.status_code == 200, r.text
"
```

The symbol-query tests use the Catalog exports in `tests/fixtures/` from PR #125.
To run the same checks against a fresh export of the full `step-06` stage, point
`REFERENCE_SOURCE` at your local reference checkout with its submodules initialized.
The test writes its checkout and exports to pytest's temporary directory.

```bash
REFERENCE_SOURCE=/path/to/legacy-example-stages uv run --locked pytest tests/test_symbol_query.py -q
```

### Compare Catalog queries with Neo4j

Run this opt-in test on a local test merge with #94. Sync the merged lockfile
with `uv sync --locked` and start a disposable Neo4j instance with the ingestion
login described in the [pipeline guide](code-ingestion-pipeline/README.md#neo4j-connection).
From `backend/` in Bash, point the test at that database and your local reference
checkout.

```bash
REFERENCE_SOURCE=/path/to/legacy-example-stages \
  NEO4J_QUERY_TEST_URI=bolt://127.0.0.1:17687 \
  uv run --locked pytest tests/test_symbol_query.py -k matches_neo4j -q
```

The test runs the full `step-06` ingestion into the test database, reads the
`snapshotId` from that run, and compares the typed Catalog result from Neo4j
with the JSONL result. It also checks that every returned span resolves against
`sources.jsonl` from the same run.

Backend callers pass a reader for the selected snapshot to
`app.symbol_query.query_snapshot_symbols`. Use the migration step associated
with that run, the exact `snapshotId` from `snapshot-identity.json` and the repo
ID (for example `legacy-example-catalog-service`). The #94 reader supplies the
entities via `load_snapshot(snapshot_id).all_entities.values()`.

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
├── app/                      # query API (FastAPI)
│   ├── main.py               # app, routes, CORS, provider lifecycle
│   ├── schemas.py            # Pydantic request/response models
│   ├── query_service.py      # QueryService seam (mock + LLM-backed)
│   ├── llm.py                # LlmProvider seam (mock + OpenAI-compatible)
│   └── repositories.py       # mock repository list
├── code-ingestion-pipeline/  # loader, Graphify adapters, configuration and tests
├── shared_contracts/         # canonical ingestion and graph/query contracts
├── tests/                    # query API and graph contract tests
├── pyproject.toml
├── run.sh                    # one-command start (Linux)
├── run.ps1                   # one-command start (Windows Terminal)
└── SETUP.md                  # installation instructions (Linux and Windows)
```

The `LlmProvider` protocol in `app/llm.py` is the seam for ticket #25: adding a
new provider (e.g. an external API) only requires a new implementation plus
configuration — consuming components never change. The `QueryService` protocol
in `app/query_service.py` is where the knowledge-graph query logic will be
plugged in later without changing the API layer.

## Ingestion pipeline

The `code-ingestion-pipeline/` directory contains the loader and Graphify
integration. It shares `backend/.venv`, `pyproject.toml`, and `uv.lock` with the API.
After `uv sync --locked`, run it from that directory with `uv run --project .. ingest`.
Follow the [complete setup guide](code-ingestion-pipeline/README.md) for configuration
and canonical output details.

## Known limitations / future work

- **No knowledge-graph context yet.** Answers come from the LLM alone; the
  deterministic ingestion and graph query logic (ticket #52 and follow-ups)
  will feed evidence into the prompt later.

