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
| `/api/chat` | POST | Submit `query` and optional `step_id`. The NDJSON stream carries model labels, source evidence when configured, and streamed answer text or an error. |
| `/api/health` | GET | Liveness check (`{"status": "ok", ..., "model": "..."}`) |
| `/api/repositories` | GET | Mock repository list for the frontend picker (real loading is ticket #17) |
| `/api/source-fragment` | POST | Resolve a stage and `SourceSpan` to full source lines and a commit-pinned GitHub link |

The chat answer is streamed as newline-delimited JSON so the frontend can
render tokens as they arrive and cancel long-running generations. Invalid
requests are rejected with HTTP 422; LLM failures arrive as an `error` event
inside the stream.

## Setup and start

See the [development setup](../SETUP.md#development-setup) for prerequisites.
For the demo with prebuilt images, follow the [tester setup](../SETUP.md).

- Linux: `./run.sh` starts Ollama if needed and runs the backend in this terminal.
  It can open the frontend in a separate terminal.
- Windows: `.\run.ps1` opens Ollama, the backend, and the frontend in Windows Terminal.

Both developer launchers expect the configured Ollama model to be installed.
`uv run uvicorn app.main:app` starts just the API and uses the mock provider
when no LLM is configured.

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
| `SOURCE_LOAD_RESULT` | *(unset)* | Path to the `sources.jsonl` from an ingestion run, loaded at API startup |
| `GRAPH_RUN_DIR` | *(unset)* | Imported ingestion run containing `snapshot-identity.json` and `sources.jsonl`. Enables chat evidence and takes precedence over `SOURCE_LOAD_RESULT`. |

Example — run against a local Ollama server (thinking disabled for speed):

```bash
LLM_BASE_URL=http://127.0.0.1:11434/v1 LLM_NAME=qwen3.5:2b \
  LLM_EXTRA_BODY='{"think": false}' ./run.sh
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
└── run.ps1                   # one-command start (Windows Terminal)
```

The `LlmProvider` protocol in `app/llm.py` is the seam for ticket #25: adding a
new provider (e.g. an external API) only requires a new implementation plus
configuration — consuming components never change. `QueryService` receives the
resolved excerpts from the chat route and passes them to the model.

## Ingestion pipeline

The `code-ingestion-pipeline/` directory contains the loader and Graphify
integration. It shares `backend/.venv`, `pyproject.toml`, and `uv.lock` with the API.
After `uv sync --locked`, run it from that directory with `uv run --project .. ingest`.
Follow the [complete setup guide](code-ingestion-pipeline/README.md) for configuration
and canonical output details.

### Try a source fragment from step-06

With the reference source configured as described in the pipeline guide, run
these commands from `backend/` in a Bash terminal.

```bash
cd code-ingestion-pipeline
uv run --project .. ingest --stage step-06 --components catalog-service \
  --out .cache/catalog-step-06.jsonl
cd ..
SOURCE_LOAD_RESULT=code-ingestion-pipeline/.cache/catalog-step-06.jsonl \
  uv run uvicorn app.main:app
```

In a second terminal, send the position of `ProductCategory` in that stage.
`catalog-service` is the ingestion selector and `legacy-example-catalog-service`
is the `repoId` in the export.

```bash
curl -fsS http://127.0.0.1:8000/api/source-fragment \
  -H 'Content-Type: application/json' \
  -d '{
    "stage": "step-06",
    "repoId": "legacy-example-catalog-service",
    "path": "src/main/java/com/ibm/catalog/ProductCategory.java",
    "commitSha": "474422cf156eb9bcce4267578b089a15edcc3733",
    "startLine": 7,
    "endLine": 7
  }'
```

The response contains `@Entity` and a link ending in `ProductCategory.java#L7-L7`.
The lookup returns inclusive Git line ranges for LF and CRLF files. Each
repository has one pinned revision per stage in the source export.
Changing the commit to another valid SHA returns HTTP 404 with the
`commit_sha_mismatch` error code.

## Catalog chat demo with Neo4j

From the repo root, start Neo4j and run the pipeline with the local reference
source configured. The ingest command prints the run folder.

```bash
docker compose up -d neo4j
(cd backend/code-ingestion-pipeline && uv run --project .. ingest --stage step-06)
```

Set `GRAPH_RUN_DIR` to that run folder and start the app with the tested local
Ollama model:

```bash
export GRAPH_RUN_DIR="$(realpath 'backend/code-ingestion-pipeline/.cache/ingestion/<run-id>')"
LLM_NAME=qwen3.5:2b LLM_EXTRA_BODY='{"reasoning_effort":"none","think":false,"temperature":0}' \
  ./backend/run.sh
```

Alternatively, build and start the containers with the same run mounted
read-only. Configure a model URL reachable from the backend container as
described in [the container guide](../Documentation/containers.md).

```bash
docker compose -f docker-compose.yml -f docker-compose.graph.yml up --build
```

Choose `step-06` and ask **Where are the Product and Category endpoints
implemented in the Catalog service?** Both excerpts go into the model request
and appear below the answer with links to `ProductResource.java:28` and
`CategoryResource.java:17` at the imported commit.

This lookup covers named Catalog symbols and route questions for the configured
run. A missing stage, missing hit or mismatched revision produces a visible
chat error. With no graph run configured, the chat uses the model alone.

To automate the example against a disposable Neo4j, run from `backend/`:

```bash
REFERENCE_SOURCE=/path/to/legacy-example-stages NEO4J_QUERY_TEST_URI=bolt://127.0.0.1:17687 \
  uv run --locked pytest tests/test_graph_fragments.py -k persisted_catalog -q
```

