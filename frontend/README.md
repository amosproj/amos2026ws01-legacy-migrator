# Sunset Tracker frontend

The frontend is a standalone Vite + React + TypeScript application. It runs
independently from the backend and defaults to a deterministic mock API so the
chat flow can be developed without any backend services.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

## Deploy to Vercel

The project is configured for Vercel with `vercel.json`. Set these environment
variables in the Vercel project settings:

```env
VITE_USE_MOCK_API=false
VITE_BACKEND_URL=https://your-backend.example.com
```

`VITE_*` values are public build-time configuration. Never put OAuth secrets,
provider tokens, or other credentials in them.

Before opening a pull request, run:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

GitHub Actions runs these same frontend checks on pushes and pull requests
that change `frontend/`, using Node.js 20 and 22.

## Run the demo with Docker

The frontend can be started independently as a production container:

```bash
docker compose up --build
```

Open `http://localhost:8080`. The demo uses mock responses by default, so no
backend is required. To build the container against a running backend:

```bash
VITE_USE_MOCK_API=false \
VITE_BACKEND_URL=http://host.docker.internal:8000 \
docker compose up --build
```

Use `FRONTEND_PORT=8081` to expose it on another local port. Vite environment
values are build-time values in this image; rebuild after changing them.

Run the UI unit tests with:

```bash
npm test
```

The tests cover the welcome state, starter prompts, keyboard and button
submission, loading feedback, adapter errors, starting a new conversation, and
the diff review form, explanation rendering, warnings, and adapter contract.

## Backend adapter

Mock mode is enabled by default. To use the backend adapter, create
`frontend/.env.local`:

```env
VITE_USE_MOCK_API=false
VITE_BACKEND_URL=http://localhost:8000
```

The adapter sends `POST /api/chat` with `{ "query": "...", "conversation_id": "..." }`
and accepts an answer in `answer`, `response`, or `message` in the JSON response.
It also preserves an optional `conversation_id` and `sources` array.
Sources with an `http` or `https` URL are rendered as links; source labels such
as `llm:openai-compatible (qwen3.5:0.8b)` are rendered as badges. Backend
errors expose the server's `detail` message when available.

The backend may take several minutes for its first CPU request while the model
loads. The chat shows an additional wait hint after a few seconds and supports
request cancellation when the page is left or a conversation is reset.

Runtime API paths and mock delays are configurable through the `VITE_API_*` and
`VITE_MOCK_*` variables in `.env.local`; `.env.example` contains the complete
set of defaults. If `VITE_BACKEND_URL` is omitted, backend requests use the
frontend origin, which is useful when a reverse proxy serves both applications.

The chat interaction follows the familiar LibreChat pattern (conversation
history, starter prompts, and an Enter-to-send composer) while keeping the
backend boundary isolated in `src/lib/chatAdapter.ts`.

The **Change explanations** view uses the same pattern for Git comparisons.
Mock mode returns a representative migration diff. Backend mode sends
`POST /api/diff/explain` with `{ "repository": "...", "base": "...", "head": "..." }`
and expects a structured summary, risk, changed files, patches, and warnings.

The repository field is an interactive provider-neutral repository picker. In
mock mode it shows GitHub, GitLab, and Bitbucket examples; backend mode loads
the authenticated user's repositories from `GET /api/repositories`. Each
repository carries its provider, display label, default branch, and stable
identifier, so adding another hosting service does not require changing the
diff UI. Provider credentials should remain server-side and must not be put in
frontend environment variables.

The top bar includes a GitHub sign-in entry point. In backend mode it redirects
to the server's `/api/auth/github/start` route; OAuth credentials and the
resulting access token remain server-side.

The current backend slice only exposes chat. Diff explanations and
authentication remain mocked by default even when `VITE_USE_MOCK_API=false`;
set `VITE_USE_MOCK_DIFF_API=false` or `VITE_USE_MOCK_AUTH_API=false` only after
the corresponding backend routes are available.

## Source structure

```text
src/
  components/
    chat/            Chat view, composer, messages, and useChat state hook
    diff/            Diff explanation components
    layout/          Config-driven navigation and auth-aware page chrome
    repositories/    Provider-neutral repository controls
  lib/               Typed backend adapters
  tests/unit/        Unit and component tests, separate from production code
```