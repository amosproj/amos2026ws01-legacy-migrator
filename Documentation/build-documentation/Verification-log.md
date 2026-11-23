# Verification log

## Baseline

| Item | Recorded value |
|---|---|
| Verification dates | 2026-11-22 to 2026-11-23 (Europe/Berlin) |
| Release tag | `sprint-05-release` |
| Commit | `4ca343e28c87824856b5f5fb9d6a91cdc976d044` |
| Commit date | 2026-11-19 |
| Mid-project tag | `mid-project-release` was absent from local and remote tag refs |
| Mainline | `main`; remote HEAD points to `origin/main` |
| OS | macOS 26.3.1, Apple silicon; Darwin kernel 25.3.0 |
| Git | 2.46.2 |
| Python / uv | Python 3.12.0 / uv 0.13.6 |
| Node / npm | Node 22.23.5 / npm 10.9.2 |
| Docker | Client 26.0.0; Engine 24.0.6; Compose v2.22.0-desktop.2 |

A clean clone was checked out at the release tag. No partner reference system was run.

## Clone commands

| Command | Exit | Result |
|---|---:|---|
| `git clone --no-checkout https://github.com/amosproj/amos2026ws01-legacy-migrator.git` | 0 | Clean clone created. |
| `git checkout sprint-05-release` | 0 | Detached checkout at the release tag. |
| `git rev-parse HEAD` | 0 | Returned `4ca343e28c87824856b5f5fb9d6a91cdc976d044`. |
| `git ls-remote --tags origin refs/tags/mid-project-release` | 0 | No matching remote tag ref. |

## Backend commands

| Command (run from `backend/`) | Exit | Result |
|---|---:|---|
| `uv sync --locked` | 0 | Environment created from lockfile. |
| `uv run ruff check .` | 0 | Passed. |
| `uv run ruff format --check .` | 0 | 61 files already formatted. |
| `uv run ty check` | 0 | Passed. |
| `uv run pytest tests -v` | 0 | 28 passed. |
| `uv run --directory code-ingestion-pipeline --project .. pytest tests -v` | 0 | 101 passed, 1 skipped; three Graphify runtime warnings. |
| `uv run python -m compileall -q app shared_contracts code-ingestion-pipeline/src` | 0 | Passed. |
| FastAPI TestClient health check shown on [Automated tests](Automated-tests) | 0 | HTTP 200, model `mock`. |

## Frontend commands

Commands ran from `frontend/` with Node 22.23.5 on PATH.

| Command | Exit | Result |
|---|---:|---|
| `npm ci` | 0 | Installed 341 packages; npm reported 9 moderate audit findings. |
| `npm run typecheck` | 0 | Passed. |
| `npm run lint` | 0 | Passed. |
| `npm run test` | 0 | 17 passed across five files. |
| `npm test` | 0 | 17 passed across five files. |
| `npm run build` | 0 | Production bundle built; Vite emitted a chunk-size advisory. |
| `npm run dev` | 130 after manual stop | Started on port 3001 because 3000 was occupied; UI returned HTTP 200 and `/api/health` was proxied with HTTP 200. |
| `npm run preview` | 130 after manual stop | Started on port 3001; preview and proxied health checks returned HTTP 200. |

The long-running servers were stopped with Ctrl+C after checking their endpoints.

## Container commands

| Command | Exit | Result |
|---|---:|---|
| `docker info --format '{{.ServerVersion}}'` | 0 | Engine 24.0.6. |
| `docker compose config` | 0 | Compose configuration parsed with defaults. |
| `docker compose up --build` | 1 | Both images built; container start failed because host port 8000 was already allocated. |
| `FRONTEND_PORT=3001 BACKEND_PORT=8001 docker compose up --build -d` | 0 | Both containers started from source-built images. |
| `curl -fsS http://localhost:8001/api/health` | 0 | Backend returned status `ok`, model `mock`. |
| `curl -fsS http://localhost:3001/` | 0 | Frontend returned its HTML document. |
| `docker compose down` | 0 | Containers and Compose network removed. |
| `docker compose ps --all` | 0 | No containers remained in the verification project. |

An earlier `docker compose up --build -d` attempt was interrupted with exit 130 while BuildKit waited for base-image metadata. The later foreground build resolved metadata, built both images, and reached the port conflict above.

## Tag checks

`git ls-remote --tags origin refs/tags/mid-project-release` exited 0 and returned no ref. The clean checkout reported the verification SHA shown above.
