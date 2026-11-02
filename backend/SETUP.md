# Backend setup

What you need: **Python 3.12**, **uv**, **Ollama** (local LLM server).

## Linux

```bash
# Python 3.12 (via uv, no system package needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:0.8b
```

## Windows

```powershell
# uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12

# Ollama: download the installer from https://ollama.com/download/windows
ollama pull qwen3.5:0.8b
```

## Dependencies and start

```bash
cd backend
uv sync          # creates .venv and installs pinned dependencies
```

Then start everything with one command:

- Linux: `./run.sh` — starts Ollama (if not running) and the backend in this terminal
- Windows: `.\run.ps1` — opens one Windows Terminal window with a tab per process

Both scripts wire the backend to the local Ollama server automatically
(`LLM_BASE_URL`, `LLM_NAME`, `LLM_EXTRA_BODY`). Without Ollama the backend still
runs and answers with a mock provider.

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