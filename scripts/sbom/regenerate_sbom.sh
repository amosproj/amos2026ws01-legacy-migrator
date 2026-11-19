#!/usr/bin/env bash
set -euo pipefail
MODE=write
[[ "${1:-}" == --check ]] && MODE=check
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
for tool in syft uv npm python3; do command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }; done
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
UV_PROJECT_ENVIRONMENT="$OUT/venv" uv sync --project backend --frozen --no-dev --no-install-project --quiet
"$OUT/venv/bin/python" scripts/sbom/sbom_tool.py inspect-dists --out "$OUT/python-dists.json"
if [[ ! -d frontend/node_modules ]]; then (cd frontend && npm ci); fi
syft scan dir:. --source-name SunsetTracker --source-version 0.1.0 --exclude './.git/**' --exclude './.venv/**' --exclude './.github/**' --exclude '**/.github/**' --exclude './Documentation/**' --exclude './frontend/node_modules/**' --exclude './backend/.venv/**' --exclude './backend/ba/**' --exclude './backend/code-ingestion-pipeline/.cache/**' --exclude './.venv/lib/python3.15/site-packages/pip/_vendor/distlib/w64.exe' --exclude './backend/.venv/**/pip/_vendor/distlib/w64.exe' --output "spdx-json=$OUT/sbom.spdx.json"
python3 scripts/sbom/enrich_sbom.py "$OUT/sbom.spdx.json" "$OUT/python-dists.json" "$ROOT" "$OUT/THIRD_PARTY_NOTICES.md"
if [[ "$MODE" == check ]]; then
  diff -u sbom.spdx.json "$OUT/sbom.spdx.json"
  diff -u frontend/public/legal/THIRD_PARTY_NOTICES.md "$OUT/THIRD_PARTY_NOTICES.md"
else
  cp "$OUT/sbom.spdx.json" sbom.spdx.json
  cp "$OUT/THIRD_PARTY_NOTICES.md" frontend/public/legal/THIRD_PARTY_NOTICES.md
fi
