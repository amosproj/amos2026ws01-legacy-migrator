#!/usr/bin/env bash
set -euo pipefail
MODE=write
USE_DOCKER=false
for arg in "$@"; do
  case "$arg" in
    --check) MODE=check ;;
    --docker) USE_DOCKER=true ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
if [[ "$USE_DOCKER" == true && "${SBOM_DOCKER_INNER:-}" != 1 ]]; then
  command -v docker >/dev/null || { echo "docker is required for --docker" >&2; exit 1; }
  docker build --platform linux/amd64 -t sunsettracker-sbom:local -f scripts/sbom/Dockerfile scripts/sbom
  if [[ "$MODE" == check ]]; then
    docker run --rm --platform linux/amd64 -v "$ROOT:/work" \
      -v sunsettracker-sbom-uv-cache:/root/.cache/uv \
      -v sunsettracker-sbom-npm-cache:/root/.npm -w /work \
      -e SBOM_DOCKER_INNER=1 sunsettracker-sbom:local \
      bash scripts/sbom/regenerate_sbom.sh --check
  else
    docker run --rm --platform linux/amd64 -v "$ROOT:/work" \
      -v sunsettracker-sbom-uv-cache:/root/.cache/uv \
      -v sunsettracker-sbom-npm-cache:/root/.npm -w /work \
      -e SBOM_DOCKER_INNER=1 sunsettracker-sbom:local \
      bash scripts/sbom/regenerate_sbom.sh
  fi
  exit $?
fi
for tool in syft uv npm python3; do command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }; done
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
UV_PROJECT_ENVIRONMENT="$OUT/venv" uv sync --project backend --python 3.12 --frozen --no-dev --no-install-project --quiet
"$OUT/venv/bin/python" scripts/sbom/sbom_tool.py inspect-dists --out "$OUT/python-dists.json"
NPM_ROOT="$OUT/npm-project"
mkdir -p "$NPM_ROOT"
cp frontend/package.json frontend/package-lock.json "$NPM_ROOT/"
npm ci --prefix "$NPM_ROOT" --ignore-scripts --no-audit --no-fund --quiet
export SBOM_FRONTEND_NODE_MODULES="$NPM_ROOT/node_modules"
syft scan dir:. --source-name SunsetTracker --source-version 0.1.0 --exclude './.git/**' --exclude './.venv/**' --exclude './.github/**' --exclude '**/.github/**' --exclude './Documentation/**' --exclude './frontend/node_modules/**' --exclude './backend/.venv/**' --exclude './backend/ba/**' --exclude './backend/code-ingestion-pipeline/.cache/**' --exclude './.venv/lib/python3.15/site-packages/pip/_vendor/distlib/w64.exe' --exclude './backend/.venv/**/pip/_vendor/distlib/w64.exe' --output "spdx-json=$OUT/sbom.spdx.json"
python3 scripts/sbom/enrich_sbom.py "$OUT/sbom.spdx.json" "$OUT/python-dists.json" "$ROOT" "$OUT/THIRD_PARTY_NOTICES.md"
if [[ "$MODE" == check ]]; then
  python3 scripts/sbom/compare_sbom.py sbom.spdx.json "$OUT/sbom.spdx.json"
  diff -u frontend/public/legal/THIRD_PARTY_NOTICES.md "$OUT/THIRD_PARTY_NOTICES.md"
else
  cp "$OUT/sbom.spdx.json" sbom.spdx.json
  cp "$OUT/THIRD_PARTY_NOTICES.md" frontend/public/legal/THIRD_PARTY_NOTICES.md
fi
