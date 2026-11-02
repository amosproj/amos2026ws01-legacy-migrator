#!/usr/bin/env bash
# Start the SunsetTracker backend plus a local Ollama server for development.
# Ollama is started as a child of this script (if not already running), so
# closing this terminal stops both the backend and the LLM server.
set -euo pipefail

cd "$(dirname "$0")"

command -v uv >/dev/null 2>&1 || { echo "error: uv is required (https://docs.astral.sh/uv/)" >&2; exit 1; }

# LLM wiring: point the backend at the local Ollama server. Override any of these.
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
export LLM_BASE_URL="${LLM_BASE_URL:-http://127.0.0.1:${OLLAMA_PORT}/v1}"
export LLM_NAME="${LLM_NAME:-qwen3.5:0.8b}"
export LLM_EXTRA_BODY="${LLM_EXTRA_BODY:-{\"think\": false}}"

uv sync

# Start Ollama only if nothing is listening on its port yet (e.g. a system service).
OLLAMA_PID=""
cleanup() { [ -n "$OLLAMA_PID" ] && kill "$OLLAMA_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM HUP
if curl -sf "http://127.0.0.1:${OLLAMA_PORT}/api/version" >/dev/null 2>&1; then
    echo "Ollama already running on :${OLLAMA_PORT}, reusing it."
else
    command -v ollama >/dev/null 2>&1 || { echo "error: ollama not found in PATH" >&2; exit 1; }
    echo "Starting Ollama on :${OLLAMA_PORT} ..."
    OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}" ollama serve &
    OLLAMA_PID=$!
    for _ in $(seq 1 30); do
        curl -sf "http://127.0.0.1:${OLLAMA_PORT}/api/version" >/dev/null 2>&1 && break
        sleep 1
    done
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "Starting backend on http://${HOST}:${PORT} (model: ${LLM_NAME})"
uv run uvicorn app.main:app --host "$HOST" --port "$PORT"