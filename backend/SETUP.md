# Backend setup

What you need: **Python 3.12**, **uv**, **Ollama** (local LLM server), and
**Node.js 20 or 22** (for the frontend; these are the versions the CI runs).

## Linux

```bash
# Python 3.12 (via uv, no system package needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:0.8b

# Node.js 20 or 22 (frontend)
# e.g. via your distribution's package manager or https://nodejs.org
```

## Windows

```powershell
# uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12

# Ollama: download the installer from https://ollama.com/download/windows
ollama pull qwen3.5:0.8b

# Node.js 20 or 22: download the installer from https://nodejs.org
```

## Dependencies and start

```bash
cd backend
uv sync          # creates .venv and installs pinned dependencies
```

Then start everything with one command:

- Linux: `./run.sh` — starts Ollama (if not running) and the backend in this
  terminal, and opens a second terminal window for the frontend
  (`npm run build` then `npm run preview`)
- Windows: `.\run.ps1` — opens one Windows Terminal window with three tabs:
  Ollama, backend and frontend

Both scripts wire the backend to the local Ollama server automatically
(`LLM_BASE_URL`, `LLM_NAME`, `LLM_EXTRA_BODY`). Without Ollama the backend still
runs and answers with a mock provider. The frontend is served at
`http://localhost:3000` and proxies `/api` to the backend on port 8000.

Both scripts check that the configured model is pulled before starting and stop
with an `ollama pull <model>` hint otherwise.

For a remote/cloud LLM provider instead of Ollama, set the environment
variables before starting (see `backend/.env.example`):

```bash
LLM_BASE_URL="https://your-provider/v1" LLM_NAME="model-name" \
  LLM_API_KEY="your-key" ./run.sh
```

## Verify

```bash
curl http://127.0.0.1:8000/api/health
```

Expected: `{"status":"ok","service":"sunsettracker-backend","version":"0.2.0","model":"openai-compatible (qwen3.5:0.8b)"}`

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" \
     -d '{"query": "Hello"}'
```

Expected: one `sources` line, then `content` lines as the answer streams in.
The first request loads the model and can take minutes on CPU; `qwen3.5:0.8b`
is a thinking model, so most of that time goes into reasoning that the current
frontend does not display yet.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `error: model 'qwen3.5:0.8b' is not pulled` | Run `ollama pull qwen3.5:0.8b` |
| `error: ollama not found in PATH` | Install Ollama, then reopen the terminal |
| `error: uv is required` | Install uv (see above) |
| `note: npm not found; skipping the frontend window` | Install Node.js 20 or 22 |
| Frontend window closes immediately | Run `npm run build` in `frontend/` to see the error |
| Port 8000 or 3000 already in use | Stop the other process, or set `PORT` |
| Chat shows an error event instead of an answer | Ollama is not running or the model is missing |

## Tests

```bash
uv run pytest
```