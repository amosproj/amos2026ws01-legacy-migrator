# Deployment

Docker Compose builds and runs the backend, frontend, and Neo4j for local use.

## Services and ports

| Service | Host port | Container port |
|---|---:|---:|
| Backend | 8000 | 8000 |
| Frontend | 3000 | 80 |
| Neo4j Bolt | 7687 | 7687 |

## Start the application

From the repository root:

~~~bash
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:3000/
~~~

The Compose defaults publish the backend on 8000 and frontend on 3000. The frontend image uses `http://localhost:8000` as its backend URL.

Stop the services with:

~~~bash
docker compose down
~~~

## Ingest step-06 facts into Neo4j

The step-06 pipeline writes canonical entities and relationships to Neo4j and saves the run handoff under `backend/code-ingestion-pipeline/.cache/ingestion/`. The private reference repository configured for the pipeline must be readable through Git before running `ingest`.

Start Neo4j from the repository root:

~~~bash
docker compose up -d neo4j
docker compose exec -T neo4j cypher-shell -u neo4j -p change-this "RETURN 1;"
~~~

Install the backend environment and run the step-06 ingest:

~~~bash
cd backend
uv sync --locked
cd code-ingestion-pipeline
uv run --project .. ingest --stage step-06
~~~

The command prints the run directory and snapshot counts. Keep the handoff directory if it may need to be imported again.

To import a handoff that already exists without rerunning checkout and extraction, run from `backend/code-ingestion-pipeline/` and replace `<existing-run>` with its directory name:

~~~bash
uv run --project .. persist-handoff --handoff-dir .cache/ingestion/<existing-run>
~~~

 `backend/app/symbol_query.py` reads source-backed symbol records from an `entities.jsonl` handoff and returns typed symbol results with source spans. This is a backend helper exercised by the step-06 tests, separate from the Neo4j persistence command.
