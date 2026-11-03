#!/usr/bin/env bash
# Start the SunsetTracker backend plus a local Ollama server for development.
# Ollama is started as a child of this script (if not already running), so
# closing this terminal stops both the backend and the LLM server.
set -euo pipefail

cd "$(dirname "$0")"
FRONTEND_DIR="$(cd ../frontend && pwd)"

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

# Fail early when the local model is missing; skipped for remote providers.
if [[ "$LLM_BASE_URL" == *127.0.0.1* || "$LLM_BASE_URL" == *localhost* ]]; then
    if ! ollama list 2>/dev/null | awk 'NR > 1 { print $1 }' | grep -qx "$LLM_NAME"; then
        echo "error: model '$LLM_NAME' is not pulled. Run: ollama pull $LLM_NAME" >&2
        exit 1
    fi
fi

# Start the frontend in a second terminal window: build, then preview.
# The preview server is a child of that window, so closing it stops the frontend.
start_frontend_window() {
    if ! command -v npm >/dev/null 2>&1; then
        echo "note: npm not found; skipping the frontend window (backend only)."
        return 0
    fi
    local cmd="cd '$FRONTEND_DIR' && { [ -d node_modules ] || npm install; } && npm run build && npm run preview"
    if command -v foot >/dev/null 2>&1; then
        foot -- /bin/sh -c "$cmd" >/dev/null 2>&1 &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- /bin/sh -c "$cmd" >/dev/null 2>&1 &
    elif command -v konsole >/dev/null 2>&1; then
        konsole -e /bin/sh -c "$cmd" >/dev/null 2>&1 &
    elif command -v xterm >/dev/null 2>&1; then
        xterm -T "SunsetTracker Frontend" -e /bin/sh -c "$cmd" >/dev/null 2>&1 &
    else
        echo "note: no supported terminal (foot/gnome-terminal/konsole/xterm) found;"
        echo "      running the frontend in this window's background instead."
        ( cd "$FRONTEND_DIR" && { [ -d node_modules ] || npm install; } && npm run build && npm run preview ) &
    fi
    return 0
}
start_frontend_window

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "Starting backend on http://${HOST}:${PORT} (model: ${LLM_NAME})"
echo "Frontend preview: http://localhost:3000 (once the build in the other window finishes)"
uv run uvicorn app.main:app --host "$HOST" --port "$PORT"