# Sunset Tracker Team WS 2026/27

SunsetTracker is a prototype that helps software teams migrate legacy systems:
a knowledge base of legacy code, target code, domain knowledge and system
dependencies, queryable in natural language and visualized as arc42 views.

## Prototype (query API + frontend)

Vertical slice from tickets #24, #25, #27, #28: ask a migration question in the
browser and receive a streamed LLM answer.

- Backend (FastAPI): see [backend/README.md](backend/README.md)
- Frontend (React): see [frontend/README.md](frontend/README.md)
- One-command start: `./backend/run.sh` (Linux) or `.\backend\run.ps1` (Windows)
- Docker images: see [Documentation/containers.md](Documentation/containers.md)
  (`docker compose up` from the repo root)

## Ingestion Pipeline

Ingestion pipeline (including the reference loader): see the [setup guide](backend/code-ingestion-pipeline/README.md).
## SBOM and legal notices

The committed SPDX SBOM and frontend Legal Notices are generated from
`backend/uv.lock` and `frontend/package-lock.json`:

```bash
scripts/sbom/regenerate_sbom.sh                 # regenerate on the current OS
scripts/sbom/regenerate_sbom.sh --check          # verify generated files
scripts/sbom/regenerate_sbom.sh --docker         # regenerate in Linux/amd64, matching CI
scripts/sbom/regenerate_sbom.sh --docker --check # verify in Linux/amd64, matching CI
```

Use the Docker mode on macOS or Windows so platform-specific package license
metadata matches the Linux GitHub Actions runner. The CI job checks the SBOM,
notices, and dependency license policy on pull requests to `develop`.
