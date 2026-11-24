# Build

## Backend environment

From the repository root:

~~~bash
cd backend
uv sync --locked
~~~

The backend API and code-ingestion pipeline use the same locked Python environment.

## Frontend bundle

From the repository root:

~~~bash
cd frontend
npm ci
npm run build
~~~

The build runs TypeScript compilation followed by Vite. The production files are written to `frontend/dist/`.

## Container images

From the repository root:

~~~bash
docker compose build
~~~

Compose builds the backend and frontend images. The Neo4j service uses the image declared in `docker-compose.yml`.
