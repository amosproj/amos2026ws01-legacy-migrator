# Start

## Start the backend

From the repository root:

~~~bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

In a second terminal, check the API:

~~~bash
curl -fsS http://127.0.0.1:8000/api/health
~~~

## Start the frontend

After installing dependencies, run from `frontend/`:

~~~bash
npm run dev -- --host 127.0.0.1 --port 3000
~~~

Open [http://localhost:3000](http://localhost:3000). The frontend sends API requests to the backend on port 8000.
