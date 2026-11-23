# Prerequisites

These versions were used for the verification unless described as optional.

| Tool | Version used | Required for |
|---|---|---|
| Git | 2.46.2 | Clone and checkout |
| Python | 3.12.0 | Backend and ingestion pipeline |
| uv | 0.13.6 | Backend environment and locked dependencies |
| Node.js | 22.23.5 | Frontend install, checks, and build |
| npm | 10.9.2 | Frontend dependencies and scripts |
| Docker Engine | 24.0.6 | Optional container deployment |
| Docker Compose | v2.22.0-desktop.2 | Optional container deployment |

Python 3.12 is pinned in `.python-version`. The frontend CI workflow runs Node 20 and Node 22; Node 22.23.5 was used here. Several locked frontend packages report unsupported-engine warnings under Node 23, so use the CI-supported versions.

Docker Engine and Compose are optional for local development. Docker Desktop is not a requirement; use an Engine and Compose v2 installation supported by your operating system. The verified environment used Docker Desktop on macOS.

Podman and Podman Compose were not used or verified; the container instructions below use Docker Compose v2.

Ollama is optional. The backend starts with a mock provider when no model endpoint is configured. A real provider needs an OpenAI-compatible endpoint and a model name. Tests use local fixtures and do not require the partner reference repositories.
