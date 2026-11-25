#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == --help || $# -gt 1 ]]; then
    printf 'Usage: %s [path-to-legacy-example-stages]\n' "$0"
    if (( $# > 1 )); then exit 2; fi
    exit 0
fi

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
reference="${1:-$root/../legacy-example-stages}"
if [[ ! -e "$reference/.git" ]]; then
    printf 'Reference checkout missing: %s. See SETUP.md.\n' "$reference" >&2
    exit 1
fi
export REFERENCE_SOURCE
REFERENCE_SOURCE="$(cd -- "$reference" && pwd -P)"
cd -- "$root"

for program in docker ollama curl; do
    command -v "$program" >/dev/null || { printf 'Install %s first. See SETUP.md.\n' "$program" >&2; exit 1; }
done

wait_for() {
    for (( attempt = 1; attempt <= 60; attempt++ )); do
        if "$@" >/dev/null 2>&1; then return 0; fi
        sleep 1
    done
    return 1
}

platform="$(uname -s)"
if ! docker info >/dev/null 2>&1; then
    case "$platform" in
        Darwin) open -a Docker ;;
        Linux)
            if [[ "$(docker context show)" == desktop-linux ]]; then
                systemctl --user start docker-desktop
            else
                systemctl --user start docker 2>/dev/null || sudo systemctl start docker
            fi
            ;;
        *) printf 'Start Docker first. See SETUP.md.\n' >&2; exit 1 ;;
    esac
    wait_for docker info || { printf 'Docker did not become ready.\n' >&2; exit 1; }
fi
docker compose version >/dev/null

compose=(docker compose --project-name "sunsettracker-tester-$$" -f docker-compose.tester.yml)
if [[ "$platform" == Linux && "$(docker context show)" != desktop-linux ]]; then
    compose+=(-f docker-compose.tester.linux.yml)
fi

ollama_pid=
compose_started=
cleanup() {
    if [[ -n "$compose_started" ]]; then "${compose[@]}" down --volumes || true; fi
    if [[ -n "$ollama_pid" ]]; then kill "$ollama_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export OLLAMA_HOST=127.0.0.1:11434
ollama_health=(curl -fsS --max-time 2 http://127.0.0.1:11434/api/version)
if ! "${ollama_health[@]}" >/dev/null 2>&1; then
    ollama serve &
    ollama_pid=$!
    wait_for "${ollama_health[@]}" || { printf 'Ollama did not become ready.\n' >&2; exit 1; }
fi

export LLM_NAME="${LLM_NAME:-qwen3.5:2b}"
if ! ollama show "$LLM_NAME" >/dev/null 2>&1; then ollama pull "$LLM_NAME"; fi

printf 'Importing step-06. Open http://localhost:3000 when the frontend starts.\n'
image_options=(--no-build)
if [[ -z "${SUNSETTRACKER_BACKEND_IMAGE:-}" && -z "${SUNSETTRACKER_FRONTEND_IMAGE:-}" ]]; then
    image_options+=(--pull always)
fi
compose_started=1
"${compose[@]}" up "${image_options[@]}"
