# Automated tests

The backend and frontend have separate test and check commands.

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

The ingestion suite covers step-06 extraction, canonical handoff files, Neo4j persistence, and typed symbol-query data with source spans. Its Neo4j integration tests run when `NEO4J_TEST_URI` points to a disposable Neo4j instance.

To run the persistence integration tests, start the disposable test server from the repository root using Bash or WSL:

~~~bash
docker run --rm -d --name neo4j-test \
  -p 127.0.0.1:17687:7687 \
  -e NEO4J_AUTH=neo4j/test-only-password \
  neo4j:2026.10.2
~~~

From `backend/`, set `NEO4J_TEST_URI` and run the persistence tests:

~~~bash
NEO4J_TEST_URI=bolt://localhost:17687 uv run --directory code-ingestion-pipeline --project .. pytest tests/test_neo4j_persistence.py -v
~~~

In PowerShell, set `$env:NEO4J_TEST_URI = 'bolt://localhost:17687'` first, then run `uv run --directory code-ingestion-pipeline --project .. pytest tests/test_neo4j_persistence.py -v`.

Stop the temporary server when the tests finish:

~~~bash
docker stop neo4j-test
~~~

## Frontend checks

Run from `frontend/` with Node 20 or 22:

~~~bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
~~~

The GitHub Actions frontend workflow runs these checks on Node 20 and Node 22. The backend workflow runs the backend checks on pushes and pull requests to `main` and `develop.
