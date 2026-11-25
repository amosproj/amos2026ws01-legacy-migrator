# Troubleshooting

## Docker commands cannot reach the engine

Start Docker Desktop, wait for the engine to report ready, then retry the Compose command.

## Neo4j connection fails

From the repository root, start the service and check its logs:

~~~bash
docker compose up -d neo4j
docker compose logs neo4j
~~~

The ingestion CLI runs on the host and connects to `bolt://localhost:7687`. The backend container connects to Neo4j as `bolt://neo4j:7687` on the Compose network.

## Step-06 ingest cannot fetch the reference source

Check that Git credentials can read the private repository configured in `backend/code-ingestion-pipeline/config/reference-source.yaml`.

## Windows path errors

The full step-06 `ingest` run hits a filename under `proxy` that Windows does not allow. Use WSL for that run, or use `persist-handoff` with a handoff produced elsewhere. Enable Windows long paths before running pipeline tests.

## A required port is busy

The Compose defaults use host ports 3000, 8000, and 7687. Stop the process using the required port, then retry.
