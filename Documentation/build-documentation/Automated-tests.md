# Automated tests

The backend and frontend use separate CI workflows. The local commands below were run on the verification tag.

## Backend checks

Run from `backend/`:

~~~bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest tests -v
uv run --directory code-ingestion-pipeline --project .. pytest tests -v
uv run python -m compileall -q app shared_contracts code-ingestion-pipeline/src
~~~

The API startup check uses FastAPI's test client and enters its application lifespan:

~~~bash
uv run python -c "
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    r = client.get('/api/health')
    print(r.status_code, r.text)
    assert r.status_code == 200, r.text
"
~~~

The GitHub Actions backend workflow performs the same lint, formatting, typing, test, compile, and health checks on pushes and pull requests to `main` and `develop`.

## Frontend checks

Run from `frontend/`:

~~~bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
~~~

The GitHub Actions frontend workflow runs these checks on Node 20 and Node 22 for pushes and pull requests to `main` and `develop`. Its test command is `npm test`, which runs `vitest run`.

## Verification result

The API suite passed 28 tests. The ingestion suite passed 101 tests and skipped one optional real-reference-source test. The frontend suite passed 17 tests across five files. Lint, formatting, typing, compilation, health, and production build checks passed. The ingestion suite printed three Graphify cache-index runtime warnings while still passing.
