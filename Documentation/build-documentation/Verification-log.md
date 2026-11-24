# Verification log

## Snapshot and environment

| Item | Recorded value |
|---|---|
| Verification date | 2026-11-24 |
| Branch snapshot | `develop`, commit `ed26dd80d27c235c862b21ddcca6c3abcce37251` |
| Operating system | macOS 26.3.1, Apple silicon |
| Python / uv | Python 3.12.0 / uv 0.13.6 |
| Docker / Compose | Docker Engine 24.0.6 / Compose v2.22.0-desktop.2 |
| Frontend runtime | Node 22.23.5 / npm 10.9.9 |

## Backend

| Command | Result |
|---|---|
| `uv sync --locked` | Passed |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | 69 files formatted |
| `uv run --locked ty check` | Passed |
| `uv run --locked pytest tests -q` | 36 passed |
| `uv run --locked --directory code-ingestion-pipeline --project .. pytest tests -q` | 128 passed, 16 skipped; three Graphify cache warnings |
| `NEO4J_TEST_URI=bolt://localhost:17687 uv run --locked --directory code-ingestion-pipeline --project .. pytest tests/test_neo4j_persistence.py -v` | 15 passed against a disposable Neo4j 2026.10.2 instance |
| `uv run --locked python -m compileall -q app shared_contracts code-ingestion-pipeline/src` | Passed |

## Frontend

Frontend checks ran with Node 22 in the `node:22-alpine` container:

| Command | Result |
|---|---|
| `npm ci` | Passed |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm test` | 17 passed across 5 files |
| `npm run build` | Passed |

## Step-06 and Compose

| Command | Result |
|---|---|
| `docker compose config` | Passed; ports map backend 8000, frontend 3000, and Neo4j 7687 |
| `docker compose --progress quiet -p docs-step06-verify build` | Passed; backend and frontend images built from the checked-out develop snapshot |
| `docker compose -p docs-step06-verify up -d neo4j` | Started Neo4j 2026.10.2; `cypher-shell` returned 1 for `RETURN 1` |
| `NEO4J_URI=bolt://localhost:7687 uv run --locked --project .. ingest --stage step-06` | Passed; loaded 143 files and persisted 754 entities and 1,890 relationships |
| `NEO4J_URI=bolt://localhost:7687 uv run --locked --project .. persist-handoff --handoff-dir .cache/ingestion/20261124T154255Z-9abjhyyi` | Passed; imported the same 754 entities and 1,890 relationships |
| Neo4j count query for the resulting snapshot | Returned 754 observations and 1,890 relationships |

The default application ports 3000 and 8000 were occupied by another local Compose stack, so this verification did not start the full application stack on those ports.
