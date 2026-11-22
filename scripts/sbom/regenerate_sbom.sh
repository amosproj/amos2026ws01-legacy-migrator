#!/usr/bin/env bash
set -euo pipefail
MODE=write
USE_DOCKER=false
REFRESH_REGISTRY=false
for arg in "$@"; do
  case "$arg" in
    --check) MODE=check ;;
    --docker) USE_DOCKER=true ;;
    --refresh-registry-snapshot) REFRESH_REGISTRY=true ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if [[ "$MODE" == check && "$REFRESH_REGISTRY" == true ]]; then echo "cannot refresh registry snapshot in --check mode" >&2; exit 2; fi
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
    if [[ "$REFRESH_REGISTRY" == true ]]; then EXTRA_ARG=--refresh-registry-snapshot; else EXTRA_ARG=; fi
    docker run --rm --platform linux/amd64 -v "$ROOT:/work" \
      -v sunsettracker-sbom-uv-cache:/root/.cache/uv \
      -v sunsettracker-sbom-npm-cache:/root/.npm -w /work \
      -e SBOM_DOCKER_INNER=1 sunsettracker-sbom:local \
      bash scripts/sbom/regenerate_sbom.sh ${EXTRA_ARG:+"$EXTRA_ARG"}
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
syft scan dir:. --source-name SunsetTracker --source-version 0.1.0 --exclude './.git/**' --exclude './.venv/**' --exclude './.github/**' --exclude '**/.github/**' --exclude './Documentation/**' --exclude './frontend/node_modules/**' --exclude './backend/.venv/**' --exclude './backend/ba/**' --exclude './backend/code-ingestion-pipeline/.cache/**' --exclude './.venv/lib/python3.15/site-packages/pip/_vendor/distlib/w64.exe' --exclude './backend/.venv/**/pip/_vendor/distlib/w64.exe' --output "spdx-json@3.0=$OUT/sbom.spdx.json"
if [[ "$REFRESH_REGISTRY" == true ]]; then python3 scripts/sbom/refresh_registry_snapshot.py "$OUT/sbom.spdx.json" "$OUT/python-dists.json"; fi
python3 scripts/sbom/enrich_sbom.py "$OUT/sbom.spdx.json" "$OUT/python-dists.json" "$ROOT" "$OUT/THIRD_PARTY_NOTICES.md"
python3 scripts/sbom/check_completeness.py "$OUT/sbom.spdx.json"
uv tool run --from 'ntia-conformance-checker==6.0.0' sbomcheck -s spdx3 -c bsi "$OUT/sbom.spdx.json"
python3 scripts/sbom/check_licenses.py "$OUT/sbom.spdx.json"
if [[ "$MODE" == check ]]; then
  python3 scripts/sbom/compare_sbom.py sbom.spdx.json "$OUT/sbom.spdx.json"
  if [[ -f Deliverables/sprint-06/sbom.spdx.json ]]; then
    python3 scripts/sbom/compare_sbom.py Deliverables/sprint-06/sbom.spdx.json "$OUT/sbom.spdx.json"
  fi
  diff -u frontend/public/legal/THIRD_PARTY_NOTICES.md "$OUT/THIRD_PARTY_NOTICES.md"
else
  cp "$OUT/sbom.spdx.json" sbom.spdx.json
  if [[ -d Deliverables/sprint-06 ]]; then cp "$OUT/sbom.spdx.json" Deliverables/sprint-06/sbom.spdx.json; fi
  cp "$OUT/THIRD_PARTY_NOTICES.md" frontend/public/legal/THIRD_PARTY_NOTICES.md
fi
