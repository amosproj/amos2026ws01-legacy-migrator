#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# regenerate_sbom.sh: regenerate the SBOM from uv.lock and run the licence gate.
#
# Usage:
#   scripts/sbom/regenerate_sbom.sh                   # regenerate files in sbom/
#   scripts/sbom/regenerate_sbom.sh --check           # fail if committed files are stale
#   scripts/sbom/regenerate_sbom.sh --docker [--check] # same, inside linux/amd64 container
#                                                     # (use on macOS/Windows: the SBOM is
#                                                     #  generated from an installed environment
#                                                     #  and must match the Linux CI runner)
#
# Steps:
#   1. Verify uv.lock is consistent with pyproject.toml (uv lock --check).
#   2. Install runtime and dev dependencies from uv.lock into isolated
#      throw-away environments (never the developer's .venv).
#   3. Generate CycloneDX 1.6 SBOMs with cyclonedx-py (licence data comes from
#      installed package metadata; uv's own CycloneDX export has no licences).
#   4. Merge the runtime SBOM with the manual supplement (containers, models,
#      external services that are not in uv.lock).
#   5. Licence gate: project LICENSE file + dependency licences + licence files.
#   6. Render THIRD_PARTY_LICENSES.md and SBOM.md (table for the planning doc).
#
# Requirements: bash, git, uv, python3 >= 3.11 (stdlib only).
#
# Environment variables (all optional):
#   SBOM_DIR                  output directory              (default: sbom)
#   SBOM_SUPPLEMENT           manual supplement             (default: $SBOM_DIR/supplement.cdx.json)
#   SBOM_POLICY               licence policy                (default: scripts/sbom/licence-policy.json)
#   SBOM_EXCEPTIONS           approved licence exceptions   (default: scripts/sbom/licence-exceptions.json)
#   PROJECT_LICENSE           SPDX override while the project licence is undecided
#                             (e.g. "Apache-2.0"); ignored if LICENSE/pyproject declare one
#   SBOM_REQUIRE_PROJECT_LICENSE  "true" -> fail if the project has no LICENSE (use on releases)
#   CYCLONEDX_BOM_VERSION     pinned cyclonedx-bom version  (default: 7.3.1)
#   PYTHON_VERSION            interpreter for the envs      (default: from .python-version or 3.12)
# -----------------------------------------------------------------------------
set -euo pipefail

MODE="write"
USE_DOCKER="false"
for arg in "$@"; do
  case "$arg" in
    --check)  MODE="check" ;;
    --docker) USE_DOCKER="true" ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ "$USE_DOCKER" == "true" ]]; then
  command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
  UV_IMAGE="${UV_IMAGE:-ghcr.io/astral-sh/uv:python3.12-bookworm-slim}"
  EPOCH="$(git log -1 --format=%ct -- uv.lock pyproject.toml "${SBOM_SUPPLEMENT:-sbom/supplement.cdx.json}" 2>/dev/null || echo 0)"
  ARGS=(); [[ "$MODE" == "check" ]] && ARGS+=(--check)
  exec docker run --rm --platform linux/amd64 \
    -v "$ROOT":/work -w /work \
    -e SOURCE_DATE_EPOCH="$EPOCH" -e PROJECT_LICENSE -e SBOM_SUPPLEMENT -e SBOM_POLICY \
    -e SBOM_EXCEPTIONS -e SBOM_REQUIRE_PROJECT_LICENSE -e CYCLONEDX_BOM_VERSION -e PYTHON_VERSION \
    --user "$(id -u):$(id -g)" -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache \
    "$UV_IMAGE" bash scripts/sbom/regenerate_sbom.sh "${ARGS[@]}"
fi

SCRIPT_DIR="scripts/sbom"
SBOM_DIR="${SBOM_DIR:-sbom}"
SBOM_SUPPLEMENT="${SBOM_SUPPLEMENT:-$SBOM_DIR/supplement.cdx.json}"
SBOM_POLICY="${SBOM_POLICY:-$SCRIPT_DIR/licence-policy.json}"
SBOM_EXCEPTIONS="${SBOM_EXCEPTIONS:-$SCRIPT_DIR/licence-exceptions.json}"
CYCLONEDX_BOM_VERSION="${CYCLONEDX_BOM_VERSION:-7.3.1}"
if [[ -z "${PYTHON_VERSION:-}" ]]; then
  if [[ -f .python-version ]]; then PYTHON_VERSION="$(head -n1 .python-version)"; else PYTHON_VERSION="3.12"; fi
fi
TOOL="python3 $SCRIPT_DIR/sbom_tool.py"

log()  { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

command -v uv >/dev/null      || fail "uv not found (https://docs.astral.sh/uv/)"
command -v python3 >/dev/null || fail "python3 not found"
[[ -f uv.lock ]]        || fail "uv.lock not found in $ROOT"
[[ -f pyproject.toml ]] || fail "pyproject.toml not found in $ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
OUT_DIR="$WORK/out"
mkdir -p "$OUT_DIR"

# Timestamp: last commit touching the dependency inputs (informational only; the
# --check comparison ignores metadata.timestamp, because committing the regenerated
# files changes this value).
if [[ -z "${SOURCE_DATE_EPOCH:-}" ]]; then
  SOURCE_DATE_EPOCH="$(git log -1 --format=%ct -- uv.lock pyproject.toml "$SBOM_SUPPLEMENT" 2>/dev/null || true)"
fi
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"

log "1/6 Checking that uv.lock matches pyproject.toml"
uv lock --check || fail "uv.lock is out of date. Run 'uv lock' and commit the result."

log "2/6 Installing locked dependencies into isolated environments (Python $PYTHON_VERSION)"
UV_PROJECT_ENVIRONMENT="$WORK/venv-runtime" \
  uv sync --frozen --no-dev --no-install-project --python "$PYTHON_VERSION" --quiet
UV_PROJECT_ENVIRONMENT="$WORK/venv-dev" \
  uv sync --frozen --only-dev --no-install-project --python "$PYTHON_VERSION" --quiet

# Package list straight from the lockfile, used to cross-check the environment SBOM
uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements.txt \
  --output-file "$WORK/lock-runtime.txt" --quiet

log "3/6 Generating CycloneDX SBOMs with cyclonedx-bom $CYCLONEDX_BOM_VERSION"
CDX=(uvx --quiet --from "cyclonedx-bom==$CYCLONEDX_BOM_VERSION" cyclonedx-py environment
     --pyproject pyproject.toml --mc-type application
     --sv 1.6 --of JSON --output-reproducible)
"${CDX[@]}" -o "$WORK/runtime.cdx.json" "$WORK/venv-runtime"
"${CDX[@]}" -o "$WORK/dev.cdx.json"     "$WORK/venv-dev"

# Licence metadata and licence files as seen by the installed distributions
"$WORK/venv-runtime/bin/python" "$SCRIPT_DIR/sbom_tool.py" inspect-dists --out "$WORK/dists-runtime.json"
"$WORK/venv-dev/bin/python"     "$SCRIPT_DIR/sbom_tool.py" inspect-dists --out "$WORK/dists-dev.json"

log "4/6 Merging with manual supplement ($SBOM_SUPPLEMENT)"
$TOOL merge \
  --runtime "$WORK/runtime.cdx.json" \
  --dev "$WORK/dev.cdx.json" \
  --supplement "$SBOM_SUPPLEMENT" \
  --lock uv.lock --lock-export "$WORK/lock-runtime.txt" \
  --out "$OUT_DIR/sbom.cdx.json" --dev-out "$OUT_DIR/sbom-dev.cdx.json"

# Keep the committed file (and its timestamp) when nothing but the timestamp changed,
# so regeneration does not create timestamp-only commits.
for f in sbom.cdx.json sbom-dev.cdx.json; do
  if [[ -f "$SBOM_DIR/$f" ]] && $TOOL compare "$OUT_DIR/$f" "$SBOM_DIR/$f"; then
    cp "$SBOM_DIR/$f" "$OUT_DIR/$f"
  fi
done

log "5/6 Licence gate"
set +e
$TOOL check \
  --sbom "$OUT_DIR/sbom.cdx.json" --dev-sbom "$OUT_DIR/sbom-dev.cdx.json" \
  --dists "$WORK/dists-runtime.json" --dev-dists "$WORK/dists-dev.json" \
  --policy "$SBOM_POLICY" --exceptions "$SBOM_EXCEPTIONS" \
  --project-root "$ROOT" \
  --report-out "$OUT_DIR/licence-report.md" \
  --notices-out "$OUT_DIR/THIRD_PARTY_LICENSES.md"
GATE=$?
set -e
if [[ -n "${GITHUB_STEP_SUMMARY:-}" && -f "$OUT_DIR/licence-report.md" ]]; then
  cat "$OUT_DIR/licence-report.md" >> "$GITHUB_STEP_SUMMARY"
fi

log "6/6 Rendering SBOM.md"
$TOOL render-md --sbom "$OUT_DIR/sbom.cdx.json" --out "$OUT_DIR/SBOM.md"

# Copy reports for CI artifacts regardless of the mode
mkdir -p "$ROOT/.sbom-work"
cp "$OUT_DIR"/* "$ROOT/.sbom-work/"

GENERATED=(sbom.cdx.json sbom-dev.cdx.json THIRD_PARTY_LICENSES.md SBOM.md licence-report.md)
# Content that must match the committed files (derived Markdown views are not compared)
COMPARED=(sbom.cdx.json sbom-dev.cdx.json THIRD_PARTY_LICENSES.md)
if [[ "$MODE" == "check" ]]; then
  STALE=0
  for f in "${COMPARED[@]}"; do
    if ! $TOOL compare "$OUT_DIR/$f" "$SBOM_DIR/$f"; then
      echo "stale or missing: $SBOM_DIR/$f"
      STALE=1
    fi
  done
  if [[ $STALE -ne 0 ]]; then
    echo
    echo "The committed SBOM does not match uv.lock."
    echo "Run 'scripts/sbom/regenerate_sbom.sh' (on macOS/Windows: add --docker) and commit $SBOM_DIR/,"
    echo "or download the 'sbom' artifact of this CI run and commit its sbom/ files."
    [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && \
      printf '\n### SBOM is stale\nRun `scripts/sbom/regenerate_sbom.sh` and commit `%s/`.\n' "$SBOM_DIR" >> "$GITHUB_STEP_SUMMARY"
    exit 1
  fi
  echo "SBOM files are up to date."
else
  mkdir -p "$SBOM_DIR"
  for f in "${GENERATED[@]}"; do cp "$OUT_DIR/$f" "$SBOM_DIR/$f"; done
  echo "Wrote ${GENERATED[*]} to $SBOM_DIR/"
fi

[[ $GATE -eq 0 ]] || fail "licence gate failed (see $SBOM_DIR/licence-report.md or .sbom-work/licence-report.md)"
log "Done"
