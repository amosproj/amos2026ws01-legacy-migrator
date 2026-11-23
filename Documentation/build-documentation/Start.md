# Start

The following local start path was verified with the mock provider. It does not start Ollama and does not need an API key.

## Start the backend

From the repository root:

~~~bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

In a second terminal, check the health endpoint:

~~~bash
curl -fsS http://127.0.0.1:8000/api/health
~~~

The verified response was HTTP 200 with status `ok` and model `mock`.

## Start the frontend

After installing dependencies, start the development server from `frontend/`:

~~~bash
npm run dev
~~~

Open the local URL printed by Vite. The configured port is 3000; if that port is occupied, Vite tries the next available port. In the verification environment it selected 3001.

Vite's development and preview servers proxy `/api` to `http://127.0.0.1:8000`. This was checked through both servers.

## Preview the production build

After `npm run build`, the production bundle can be served locally:

~~~bash
npm run preview
~~~

Vite's preview server also proxies `/api` to port 8000. Stop the foreground server with Ctrl+C when finished.
