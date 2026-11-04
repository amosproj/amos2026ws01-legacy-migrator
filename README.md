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

## Reference loader

Reference loader (Issue #17): see [Documentation/ingestion/reference-loader.md](Documentation/ingestion/reference-loader.md).
