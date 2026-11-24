# Dependencies

The lockfiles define the dependency versions. Install them from the repository root as described on [Clone and setup](Clone-and-setup).

## Backend

The backend API and ingestion pipeline share `backend/pyproject.toml` and `backend/uv.lock`. The environment includes FastAPI, Uvicorn, Pydantic, the Neo4j driver, Graphify, and Tree-sitter parsers. Ruff, ty, and pytest provide the backend checks.

## Frontend

The frontend uses React, Vite, and TypeScript. Run `npm ci` in `frontend/` to install the versions pinned by `package-lock.json`. Its checks use ESLint, TypeScript, and Vitest.

## Containers

Docker Compose builds the backend and frontend images and starts the Neo4j service. The backend image uses Python 3.12. The frontend image builds with Node 22 and serves the static bundle with nginx.
