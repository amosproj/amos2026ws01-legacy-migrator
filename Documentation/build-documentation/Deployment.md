# Deployment

The tag provides a local Docker Compose deployment for a single machine. No cloud or Kubernetes production deployment path is defined in the verified tree.

## Default ports and images

| Service | Host URL | Container port | Image name |
|---|---|---:|---|
| Backend | `http://localhost:8000` | 8000 | `ghcr.io/amosproj/amos2026ws01-legacy-migrator-backend:latest` |
| Frontend | `http://localhost:3000` | 80 | `ghcr.io/amosproj/amos2026ws01-legacy-migrator-frontend:latest` |

Compose builds both images from the checked-out source. By default, the backend uses the mock provider. Ollama is outside the images.

## Start and verify Compose

The default host ports are 8000 and 3000. In the verification environment, port 8000 was already occupied, so the successful smoke check used 8001 and 3001:

~~~bash
FRONTEND_PORT=3001 BACKEND_PORT=8001 docker compose up --build -d
curl -fsS http://localhost:8001/api/health
curl -fsS http://localhost:3001/
docker compose down
~~~

The build completed and both containers started. The backend health endpoint and frontend document each returned HTTP 200. The default-port attempt could not bind port 8000; see [Troubleshooting](Troubleshooting).

Changing the backend host port alone does not reconfigure the URL baked into the frontend bundle. The Dockerfile defaults `VITE_BACKEND_URL` to `http://localhost:8000`, and this Compose file does not pass a custom build argument. The successful alternate-port check verified the two published endpoints separately; it did not verify a frontend chat call to the backend at port 8001.

## LLM configuration

No LLM settings are needed for the mock provider. Compose forwards `LLM_BASE_URL`, `LLM_NAME`, and `LLM_EXTRA_BODY` to the backend. It does not forward `LLM_API_KEY` or `LLM_TIMEOUT_SECONDS`; those variables are available to non-container backend runs, but are not wired through this Compose file at this tag.

## Scope

This procedure is for local deployment. Do not treat the GHCR image workflow as evidence of a cloud deployment. The workflow builds and publishes container images on configured branch and version-tag events.
