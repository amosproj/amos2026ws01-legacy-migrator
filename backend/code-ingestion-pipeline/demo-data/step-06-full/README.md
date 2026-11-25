# step-06 run data (all components)

Pre-generated ingestion output for `step-06`, so the data can be loaded into Neo4j
without running the ingest. The full ingest fails on Windows because
`components/proxy` contains a file name that Windows does not allow
(`nginx.conf needed?`).

- Stage: `step-06` (umbrella `5387027`), all components
- Snapshot ID: `13ecec1f35c7da91a6801b1be81d691207b30d172b629073e038fab09defe899`
- 754 entities, 1,890 relationships
- Generated on Linux (WSL Ubuntu 24.04) with `ingest --stage step-06`

## Run the Windows demo

From the SunsetTracker repo root, run `.\run-tester.ps1`. It loads this export
into Neo4j and starts the app. See the [tester setup](../../../../SETUP.md).

## Load into Neo4j manually

Start Neo4j from the repository root, then load the data from
`backend/code-ingestion-pipeline/` (same commands in PowerShell and bash):

```bash
docker compose up -d neo4j
uv run --project .. persist-handoff --handoff-dir demo-data/step-06-full
```

Tested on Windows (PowerShell): the import succeeds and Neo4j returns the
30 Catalog symbols of this run.

## Run SunsetTracker from source with this data

After the manual import, point the backend at this folder
(see "Catalog chat demo with Neo4j" in
`backend/README.md`). On Windows (PowerShell), from `backend/`:

```powershell
$env:GRAPH_RUN_DIR = (Resolve-Path "code-ingestion-pipeline\demo-data\step-06-full").Path
.\run.ps1
```

Then choose `step-06` and ask: *Where are the Product and Category endpoints
implemented in the Catalog service?*

`sources.jsonl` contains the source code of the analysed example system
(IBM's public example, Apache 2.0).
