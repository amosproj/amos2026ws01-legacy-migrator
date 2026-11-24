# Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Git | Installed | Clone and fetch the project and configured reference source |
| Python | 3.12 | Backend and ingestion pipeline |
| uv | Installed | Install the locked backend environment |
| Node.js | 20 or 22 | Frontend install, checks, and build |
| npm | Bundled with Node.js | Frontend dependencies and scripts |
| Docker Desktop with Compose v2 | Current version | Run the backend, frontend, and Neo4j services |

Use Node 20 or 22 for frontend commands. The frontend CI workflow checks both versions; its container image is built with Node 22.

The step-06 `ingest` command fetches the private reference repository configured for the pipeline. Ensure Git has read access before running it.

Ollama is optional. The backend starts with a mock provider when no model endpoint is configured. A real provider needs an OpenAI-compatible endpoint and a model name. Tests use local fixtures and do not require the partner reference repositories.
On Windows, start Docker Desktop before Compose commands. The full step-06 `ingest` run fails on Windows because a filename under `proxy` is not allowed. Use WSL for the full ingest, or run `persist-handoff` on an existing handoff. Enable Windows long paths before running the pipeline tests.
