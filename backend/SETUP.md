# Backend setup

What you need: **Python 3.12**, **uv**, **Ollama** (local LLM server), and
**Node.js** (for the frontend).

## Linux

```bash
# Python 3.12 (via uv, no system package needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:0.8b

# Node.js (frontend)
# e.g. via your distribution's package manager or https://nodejs.org
```

## Windows

```powershell
# uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12

# Ollama: download the installer from https://ollama.com/download/windows
ollama pull qwen3.5:0.8b

# Node.js: download the installer from https://nodejs.org
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

For a remote/cloud LLM provider instead of Ollama, set the environment
variables before starting (see `backend/.env.example`):

```bash
LLM_BASE_URL="https://your-provider/v1" LLM_NAME="model-name" \
  LLM_API_KEY="your-key" ./run.sh
```

## Verify

```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" \
     -d '{"query": "Hello"}'
```

## Tests

```bash
uv run pytest
```