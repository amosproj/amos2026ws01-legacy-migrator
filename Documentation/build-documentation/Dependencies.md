# Dependencies

The lockfiles define the reproducible dependency sets. Install them from the repository root as described on [Clone and setup](Clone-and-setup).

## Backend

The backend and ingestion pipeline share `backend/pyproject.toml` and `backend/uv.lock`. Run `uv sync --locked` from `backend/` to install runtime and development dependencies.

The query API uses FastAPI, Uvicorn, Pydantic, and httpx2. The ingestion pipeline uses Graphify and a set of Tree-sitter language parsers. Backend development checks use Ruff, ty, and pytest. The lockfile pins the resolved package versions.

## Frontend

The frontend uses React 19, React DOM, Vite, and TypeScript. Its UI dependencies include Mermaid and lucide-react. The development and test toolchain includes Tailwind CSS, ESLint, and Vitest.

Run `npm ci` in `frontend/` to install the exact dependency versions from `package-lock.json`. Do not use `npm install` for the documented clean setup.

## Containers

The optional Compose deployment builds a Python 3.12 backend image and a Node 22-built frontend served by nginx. Container builds use the backend uv lockfile and frontend npm lockfile. Ollama is not included in either image.
