# Running SunsetTracker with Docker

Reproducible from source: one image for the FastAPI backend, one for the
nginx-served frontend. Both are published automatically to GHCR on every push
to `main` or `develop`, on version tags (`v1.2.3`) and from a clean checkout
via `docker compose up`. Ollama is **not** part of these images: the LLM server
stays an external dependency, wired exactly like `backend/run.sh` wires it.

## Quick start (whole app from the repo root)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (health: `curl localhost:8000/api/health`)

**Out of the box, the backend starts with the built-in mock provider** — no
model endpoint, no Ollama, no configuration needed. The frontend loads, the
chat answers with a deterministic mock reply, and the whole stack is smoke-testable.

To use a real LLM (Ollama or any OpenAI-compatible endpoint), copy
[`.env.example`](.env.example) to `.env`, uncomment the `LLM_BASE_URL` and
`LLM_NAME` lines, and restart:

```bash
cp .env.example .env   # then edit .env to uncomment LLM_BASE_URL / LLM_NAME
docker compose up
```

### With Ollama on the host

Ollama itself: install via `curl -fsSL https://ollama.com/install.sh | sh`
(Linux/macOS) or the installer from <https://ollama.com/download> (Windows).
Then pull the model and start Ollama so the container can reach it:

```bash
ollama pull qwen3.5:0.8b
```

On Linux, Ollama's default `127.0.0.1` bind is not reachable from a container.
Start it listening on all interfaces:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

> **Linux firewall note.** If the container can reach `host.docker.internal`
> via DNS but TCP to port 11434 times out, a host firewall is dropping the
> container→host traffic. With UFW:
> `sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp`.
> This is a host setting, not part of the images.

## Operating systems and architectures

| Platform | amd64 (x86_64) | arm64 (Apple Silicon, AWS Graviton) | Notes |
| --- | :---: | :---: | --- |
| Linux | ✓ | ✓ | `host.docker.internal` needs `extra_hosts: host-gateway` (compose includes it); firewall may need the rule above |
| macOS (Docker Desktop) | ✓ | ✓ | `host.docker.internal` works natively; no firewall tweaks needed |
| Windows (Docker Desktop) | ✓ | ✓ | `host.docker.internal` works natively; use WSL2 backend |

All three base images are multi-arch (`uv:python3.12-bookworm-slim`, `node:22-alpine`,
`nginx:1.27-alpine`). The 32-bit ARM variant (`arm/v7`) is available for the
frontend images only — the backend base image does not ship an arm/v7 manifest.

Ollama itself supports Linux, macOS, and Windows (preview) on amd64 and arm64.
The default model (`qwen3.5:0.8b`, ~0.5 GB) fits on any machine with ≥ 2 GB RAM
and runs on CPU — no GPU required.

## Decoupled architecture (why no API proxy)

Frontend and backend are hosted separately, per the architecture contract: the
browser calls the FastAPI API directly at `VITE_BACKEND_URL` (default
`http://localhost:8000`), no nginx `/api` proxying, no single origin. The
backend enables CORS for the frontend origins (`CORS_ORIGINS` in
`backend/app/main.py`).

This means the backend URL baked into the frontend build must be reachable
**from the user's browser**, not from the container. For a public deployment,
set `VITE_BACKEND_URL` to the public API URL in `.env` and rebuild — the
default works for a single-machine demo.

## Published images

| Image | Contents | Build context |
| --- | --- | --- |
| `ghcr.io/amosproj/amos2026ws01-legacy-migrator-backend` | FastAPI query API on Python 3.12 (uv-managed deps) | [backend/](backend/) |
| `ghcr.io/amosproj/amos2026ws01-legacy-migrator-frontend` | React SPA served by nginx on port 80 (container) → 3000 (host) | [frontend/](frontend/) |

Tags:

- `type=sha` — every build gets its git short SHA (immutable, traceable).
- `main` / `develop` — per-branch rolling tags.
- `1.2.3` — on `v1.2.3` git tags, the image is tagged with the version number.

The workflow is [`.github/workflows/container-images.yml`](.github/workflows/container-images.yml);
it authenticates to GHCR with the workflow-scoped `GITHUB_TOKEN` only — no
credentials are stored in this repository.

## Running a single image manually

```bash
# Backend (mock provider — no model endpoint needed):
docker run --rm -p 8000:8000 \
  ghcr.io/amosproj/amos2026ws01-legacy-migrator-backend:latest

# Backend with Ollama on the host (add --add-host on Linux):
docker run --rm -p 8000:8000 \
  -e LLM_BASE_URL=http://host.docker.internal:11434/v1 \
  -e LLM_NAME=qwen3.5:0.8b \
  --add-host host.docker.internal:host-gateway \
  ghcr.io/amosproj/amos2026ws01-legacy-migrator-backend:latest

# Frontend only (from the frontend/ directory):
docker build -t sunsettracker-frontend frontend && docker run --rm -p 3000:80 sunsettracker-frontend
```

## Local development

The container setup is intentionally not involved in day-to-day development —
[`backend/run.sh`](backend/run.sh) (Linux) / [`backend/run.ps1`](backend/run.ps1)
(Windows) remain the one-command start for development with hot reload. Use
`docker compose` when you specifically want the published-image experience or
when the host has no Python/Node toolchain installed.

## Manual end-to-end test

Prerequisites: Docker. For real LLM answers, additionally Ollama on the host
with the model pulled and `.env` configured (see "With Ollama on the host"
above).

### Steps

1. Start the stack from the repository root:

   ```bash
   docker compose up --build
   ```

   Expected: two containers start (`backend`, `frontend`), no build errors.

2. Check the backend is up and which provider it selected:

   ```bash
   curl -s http://localhost:8000/api/health
   ```

   Expected: `{"status":"ok",...,"model":"mock"}` (the default).
   With Ollama configured via `.env`, the model field shows
   `"openai-compatible (qwen3.5:0.8b)"`.

3. Open the frontend at <http://localhost:3000>.

   Expected: the SunsetTracker UI loads (title "SunsetTracker · Legacy
   Migration Knowledge Base"), no console errors about failed `/api` calls.

4. In the chat, ask a migration-status question, e.g.
   *"Which components are still on the legacy stack?"*

   Expected (mock): a deterministic reply starting with "Mock LLM reply: no LLM
   provider is configured…". Expected (Ollama): the answer streams in token by
   token. With a thinking model the collapsible reasoning block appears first,
   then the answer text. The first request is the slowest (model load); on
   CPU-only hardware allow 1–3 minutes.

5. Verify the decoupled wiring: open the browser dev tools → Network tab and
   confirm the chat request goes to `http://localhost:8000/api/chat` directly
   (not through the frontend origin), and the response is `application/x-ndjson`.

6. Stop the stack:

   ```bash
   docker compose down
   ```

### Failure modes to watch for

| Symptom | Cause | Fix |
| --- | --- | --- |
| Chat shows an error event, health says `openai-compatible` | Container cannot reach Ollama | Start Ollama with `OLLAMA_HOST=0.0.0.0:11434`; check the firewall note above |
| Frontend loads but chat calls fail with CORS | Frontend origin not in `CORS_ORIGINS` | Set `CORS_ORIGINS` in `.env` to include `http://localhost:3000` |
| `docker compose up` fails to build | Stale cache / missing lockfile | `docker compose build --no-cache` |

