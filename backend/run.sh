#!/usr/bin/env bash
# One-command local start for the SunsetTracker backend (ticket #24).
# Creates a local venv, installs dependencies and starts the API on :8000.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required (https://docs.astral.sh/uv/)" >&2
    exit 1
fi

uv sync

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "Starting SunsetTracker backend on http://${HOST}:${PORT}"
exec uv run uvicorn app.main:app --host "$HOST" --port "$PORT"