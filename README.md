# Sunset Tracker Team WS 2026/27

SunsetTracker is a prototype that helps software teams migrate legacy systems:
a knowledge base of legacy code, target code, domain knowledge and system
dependencies, queryable in natural language and visualized as arc42 views.

## Try the mid-project demo

Follow the [tester setup](SETUP.md) to prepare the reference checkout and start
the app from prebuilt images with one command. The launcher imports `step-06`
into Neo4j, then serves the migration chat at <http://localhost:3000>.

## Develop from source

- [Development setup](SETUP.md#development-setup)
- [Backend (FastAPI)](backend/README.md)
- [Frontend (React)](frontend/README.md)
- [Build and publish Docker images](Documentation/containers.md)

## Ingestion Pipeline

Ingestion pipeline (including the reference loader): see the [setup guide](backend/code-ingestion-pipeline/README.md).
