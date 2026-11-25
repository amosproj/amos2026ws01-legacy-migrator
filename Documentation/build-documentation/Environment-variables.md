# Environment variables

The documented default build and local Compose run use the checked-in defaults. A root `.env` file is only needed when changing settings.

## Compose ports and graph connection

| Variable | Default | Use |
|---|---:|---|
| `BACKEND_PORT` | `8000` | Host port for the backend container |
| `FRONTEND_PORT` | `3000` | Host port for the frontend container |
| `NEO4J_PORT` | `7687` | Host Bolt port for Neo4j |
| `NEO4J_URI` | `bolt://neo4j:7687` in Compose | Backend container connection to Neo4j |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Browser origins accepted by the backend |

The host-side ingestion CLI defaults to `bolt://localhost:7687`. The Compose Neo4j service uses the development login `neo4j` / `change-this`.

## Frontend backend URL

`VITE_BACKEND_URL` defaults to `http://localhost:8000` in the frontend Dockerfile. The default Compose ports match this URL.
