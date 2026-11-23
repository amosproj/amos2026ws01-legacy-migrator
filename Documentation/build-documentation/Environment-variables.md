# Environment variables

The mock provider is the default. No model endpoint or API key is required for local setup, builds, tests, or the verified Compose smoke check.

## Backend variables

| Variable | Required | Default | Read by / effect |
|---|---|---|---|
| `CORS_ORIGINS` | Optional | Backend code: localhost and 127.0.0.1 on ports 3000 and 5173. Compose overrides this to localhost and 127.0.0.1 on port 3000. | `backend/app/main.py`; comma-separated browser origins allowed by the API. |
| `LLM_BASE_URL` | Optional | Unset; mock provider is selected. | `backend/app/llm.py`; base URL of an OpenAI-compatible endpoint. |
| `LLM_NAME` | Optional | Unset; mock provider is selected. | `backend/app/llm.py`; model identifier. Both URL and name must be set to select the real provider. |
| `LLM_API_KEY` | Optional | Empty | `backend/app/llm.py`; optional for local endpoints and needed by external endpoints that require a key. Compose does not currently pass this variable into the backend container. |
| `LLM_TIMEOUT_SECONDS` | Optional | 600 seconds | `backend/app/llm.py`; provider request timeout. Compose does not currently pass this variable into the backend container. |
| `LLM_EXTRA_BODY` | Optional | Empty object | `backend/app/llm.py`; JSON object merged into completion requests. Compose passes this through. |

The backend run scripts also read `HOST`, `PORT`, and `OLLAMA_PORT`; the Linux script defaults the API to 127.0.0.1:8000 and Ollama to 11434. These script-specific overrides were not part of the verified start path.

## Compose variables

| Variable | Required | Default | Read by / effect |
|---|---|---|---|
| `BACKEND_PORT` | Optional | 8000 | `docker-compose.yml`; host port mapped to backend container port 8000. |
| `FRONTEND_PORT` | Optional | 3000 | `docker-compose.yml`; host port mapped to frontend container port 80. |

The root `.env.example` contains these port settings and sample LLM settings. Compose reads a root `.env` file when one exists; a `.env` file is unnecessary for the default mock setup. For non-Compose backend runs, set variables in the process environment: the backend does not load `backend/.env` automatically. The root and backend `.env` files are ignored by Git, while the example files remain tracked.

## Frontend Vite variables

Vite exposes only variables prefixed with `VITE_` to frontend source. The sprint-05 example file declares the following:

| Variable | Example default | Read by / effect at this tag |
|---|---|---|
| `VITE_BACKEND_URL` | `http://localhost:8000` | Read by `frontend/src/services/api.ts` and `diffApi.ts` and baked in at build time. In development, leaving it unset keeps requests relative so the Vite dev/preview proxy can forward `/api`. |
| `VITE_USE_MOCK_DIFF_API` | `true` | Declared in `frontend/.env.example`; no frontend source read was found at this tag. |
| `VITE_USE_MOCK_AUTH_API` | `true` | Declared in `frontend/.env.example`; no frontend source read was found at this tag. |
| `VITE_API_CHAT_PATH` | `/api/chat` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_DIFF_EXPLAIN_PATH` | `/api/diff/explain` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_REPOSITORIES_PATH` | `/api/repositories` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_HEALTH_PATH` | `/api/health` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_AUTH_SESSION_PATH` | `/api/auth/session` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_AUTH_START_PATH` | `/api/auth/{provider}/start` | Declared in the example; not read by frontend source at this tag. |
| `VITE_API_AUTH_LOGOUT_PATH` | `/api/auth/logout` | Declared in the example; not read by frontend source at this tag. |
| `VITE_MOCK_CHAT_DELAY_MS` | `650` | Declared in the example; no frontend source read was found at this tag. |
| `VITE_MOCK_DIFF_DELAY_MS` | `450` | Declared in the example; no frontend source read was found at this tag. |
| `VITE_MOCK_REPOSITORIES_DELAY_MS` | `250` | Declared in the example; no frontend source read was found at this tag. |

The Dockerfile default for `VITE_BACKEND_URL` is `http://localhost:8000`. The Compose file does not pass the root `.env` value as a frontend build argument. The documented default ports match that baked URL; a non-default backend host port needs a frontend build that points to that port. This non-default frontend-to-backend wiring was not verified.

Never commit real credentials. Use placeholders in examples and keep secrets in a local ignored environment file.
