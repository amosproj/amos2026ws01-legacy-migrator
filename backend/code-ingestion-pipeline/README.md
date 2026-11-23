# Reference source to graph pipeline

The ingestion pipeline shares the backend's uv environment, dependencies, and
lockfile. The CLI loads a pinned reference stage and extracts a separate graph
for each selected component. It reads selected files directly from checkout;
it does not reconstruct source copies, run clustering, or generate graph reports.

## Setup and run

Install uv, Python 3.12, Git, and Docker with Compose. From the repository root:

```bash
docker compose up -d neo4j
docker compose exec -T neo4j cypher-shell -u neo4j -p change-this "RETURN 1;"
cd backend
uv sync --locked
cd code-ingestion-pipeline
uv run --project .. ingest --stage step-06
```

Run the connectivity check once Neo4j has started. Use `docker compose logs -f
neo4j` from the repository root to check startup if the connection fails.

The commands are the same in Linux/macOS terminals and Windows PowerShell.
`uv sync --locked` installs the API, loader, Graphify, Neo4j driver, CLI, and
development tools into `backend/.venv`. No separate ingestion environment, pip
setup script, or `PYTHONPATH` configuration is needed. The module entry point
remains available:

```bash
uv run --project .. python -m migration_assistant.bootstrap.cli
```

Runs do not invoke package installers. Use `uv sync --locked` after dependency
changes. Normal uv commands may synchronize the environment before invoking the
CLI; use `uv run --locked --no-sync --project .. ingest` after setup when an
explicitly preinstalled environment is required.

No API key is needed for local AST extraction. Fetching an HTTPS reference source
uses Git and any existing Git credentials.

### Neo4j connection

| Setting | Default | Used by |
| --- | --- | --- |
| `NEO4J_PORT` | `7687` | Docker Compose host port. Set it in the repository root `.env` or in the shell that starts Compose. |
| `NEO4J_URI` | `bolt://localhost:7687` | Ingestion CLI. Export it in the shell that runs ingestion when the Bolt address differs. |
| Username and password | `neo4j` / `change-this` | Fixed development login in Compose and the CLI on this branch. |

For example, if Compose publishes port `17687`, run the following from
`backend/code-ingestion-pipeline/` in Bash.

```bash
NEO4J_URI=bolt://localhost:17687 uv run --project .. ingest --stage step-06
```

In PowerShell, set `$env:NEO4J_URI = 'bolt://localhost:17687'` before running
`uv run --project .. ingest --stage step-06`. The Compose `.env` sets the Compose
port. The CLI reads `NEO4J_URI` from its process environment.

The CLI checks connectivity before extraction. It writes the canonical files and
then stores the observations and relationships in Neo4j. Re-running the same
snapshot replaces its records. Compose keeps the data in the `neo4j-data` volume
when you run `docker compose stop neo4j`.

To inspect a run, copy `snapshotId` from its `snapshot-identity.json` and open
`docker compose exec neo4j cypher-shell -u neo4j -p change-this` from the root.
Set the parameter and check the Catalog observations for that exact snapshot.

```cypher
:param snapshot => 'paste-snapshotId-here';
MATCH (n:SymbolObservation {
  snapshot_id: $snapshot, repo_id: 'legacy-example-catalog-service'
})
RETURN count(n) AS catalog_symbols;
```

## Configuration

Run the commands below from `backend/code-ingestion-pipeline/`. The default
configuration is `config/reference-source.yaml`. A Git-ignored
`config/reference-source.local.yaml`, if present, replaces it completely.
Alternatively, pass `--config PATH`.

To configure a local source, copy the default configuration and edit `source`:

```bash
cp config/reference-source.yaml config/reference-source.local.yaml
```

In PowerShell, use `Copy-Item` instead of `cp`. Example source paths:

```yaml
# Linux/macOS
source: /home/developer/reference/legacy-example-stages
# Windows: forward slashes avoid YAML escape sequences
# source: D:/reference/legacy-example-stages
```

The local umbrella repository must have its selected component submodules initialized.

| Setting | Meaning |
|---|---|
| `stage` | Stage tag, such as `step-00` or `step-04a` |
| `components` | Omit or use `[]` to select every component in that stage; a list restricts selection |
| `source` | HTTPS URL or local umbrella repository path |
| `workspace` | Checkout cache, default `.cache/reference` |
| `public_url` | Base URL used for revision-pinned source links |
| `include`, `exclude` | File selection rules |
| `max_file_size_kb` | Maximum loaded file size |

Each component is checked out at the commit pinned by the selected stage.
Components are processed sequentially; selecting all components does not enable
parallel downloads. Relative configuration paths are resolved from the current
working directory.

CLI overrides:

```bash
uv run --project .. ingest --stage step-04a
uv run --project .. ingest --components monolith catalog-service
uv run --project .. ingest --config config/reference-source.local.yaml
uv run --project .. ingest --output-dir .cache/ingestion --verbose
uv run --project .. ingest --out .cache/export/sources.jsonl
```

`--out` writes an additional source export. Every run saves its own `sources.jsonl`
regardless of that option. There is no graph-mode option: extraction always runs
separately for each component with loaded files. An entirely empty selection fails
before extraction.

To persist an already-written handoff without repeating checkout or extraction:

```bash
uv run --project .. persist-handoff --handoff-dir .cache/ingestion/<existing-run>
```

This reads `snapshot-identity.json`, `entities.jsonl`, and `relationships.jsonl`
from the run folder and uses the same Neo4j connection settings as `ingest`.
It replaces the observations and relationships for that snapshot. Add `--verbose`
to show a traceback on failure.

Developers control output and checkout locations and their Git ignore rules. The
pipeline does not enforce output placement or refuse Git commands based on the
original source directory. Keep the configured workspace separate from that source
and choose output paths that do not overwrite source files. Default `.cache/`
locations are Git-ignored.

## Python interface for backend callers

Import the operations directly from `migration_assistant.api`. For example,
with paths relative to `backend/`:

```python
from pathlib import Path

from migration_assistant.api import ingest_step, load_snapshot, persist_handoff
from migration_assistant.domain.reference_source import load_config

config = load_config(Path("code-ingestion-pipeline/config/reference-source.yaml"))
result = ingest_step(config, Path("code-ingestion-pipeline/.cache/ingestion"))
snapshot = load_snapshot(result.snapshot_id)

# Replay an existing run without extracting again:
handoff = persist_handoff(result.run_directory)
```

The configuration selects the stage and components. `ingest_step` returns a
`PipelineResult` and accepts optional `source_export`, `on_loaded`, and `progress`
arguments matching `PipelineService.run`. `persist_handoff` and `load_snapshot`
return a `RelationshipHandoffResult` with `snapshot_id`, `all_entities`,
`all_relationships`, `entity_count`, and `relationship_count`. An absent snapshot
returns empty dictionaries and zero counts.

These synchronous functions use the same Neo4j settings as the CLI, open and close
a connection for each operation, and propagate exceptions to the caller. Importing
the module does not connect to Neo4j. Reads require an explicit snapshot ID;
stage-to-snapshot lookup is not part of this interface. The CLI commands wrap
these functions and retain their existing arguments and exit codes.

## Pipeline and artifacts

```text
CLI -> pinned checkout -> selected source files -> sources.jsonl
    -> Graphify per component -> graph.json + graph.html
    -> canonical handoff + snapshot identity
```

Dependencies are checked before graph extraction. Graphify receives the selected
original checkout paths and uses each component as its extraction root. This
preserves develop's per-component relative paths and node IDs. Graphify may parse
only a subset of selected formats; unparsed files are logged while the extracted
portion is retained. No clustering, community labeling, analysis, LLM calls, or
reports are generated.

Each successful source load creates a unique run directory:

```text
.cache/ingestion/<UTC-time>-<unique-suffix>/
  sources.jsonl
  bootstrap.log
  snapshot-identity.json
  code-graphs.jsonl
  entities.jsonl
  relationships.jsonl
  relationship-issues.jsonl       # only when normalization reports issues
  graphs/<repoId>/
    extract.log
    graphify-out/
      graph.json
      graph.html
      cache/
```

`bootstrap.log` records loading diagnostics. Each `extract.log` captures Python
extraction output, logging, and failure tracebacks in place of the former subprocess
log. There is no `cluster.log`. Extraction and handoff failures retain partial
outputs and report their location. Use `--verbose` for a terminal traceback. If HTML
export fails, any already-generated JSON remains available.

## Canonical handoff

The relationship adapter preserves develop's canonical handoff behavior in
per-component mode, including its existing path-resolution behavior. Its outputs are:

- `entities.jsonl`: source-backed, external, and unresolved observations.
- `relationships.jsonl`: canonical relationships and original edge provenance.
- `code-graphs.jsonl`: repository roots with member and file observation IDs.
- `snapshot-identity.json`: source revisions, extractor versions, extraction
  configuration, and the deterministic snapshot ID shared by all facts.
- `relationship-issues.jsonl`: diagnostics with raw edge data, when present.

The normalizer and serialization use `../shared_contracts/`; the generated schema
is `../schemas/project-contract.schema.json`. Regenerate it from `backend/` with:

```bash
uv run python -m shared_contracts.schema
```

Snapshot configuration records `graphMode: per-component` even though the CLI no
longer exposes a mode switch. Only repositories represented by selected source
files contribute source revisions, matching develop. Known relationship labels use
the shared dictionary; unknown labels and original edge data are retained. Missing
locations become unresolved observations, and unresolvable edges are diagnosed.

Compatibility intentionally retains a known develop issue: for a component-relative
path such as `src/Main.java`, normalization can interpret `src` as the repository ID.
This can produce unresolved observations, missing relationship evidence, and empty
repository membership. Fixing it requires a separate output-contract change.

## Tests

From `backend/code-ingestion-pipeline/`:

```bash
uv run --locked --project .. pytest tests -q
```

From `backend/`, run API tests separately:

```bash
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ty check
```

Tests use temporary local Git repositories and need no GitHub connection. They
cover the loader, pipeline, Graphify adapters, and canonical handoff, including
real Graphify extraction. Tests never build or execute downloaded reference
source code. Windows/macOS execution remains unverified.

The CLI and pipeline unit tests run without a live Neo4j connection. The
persistence integration tests use a separate disposable Neo4j instance. Start
one from the repository root.

```bash
docker run --rm -d --name amos-neo4j-persistence-test \
  -p 127.0.0.1:17687:7687 --tmpfs /data \
  -e NEO4J_AUTH=neo4j/test-only-password neo4j:2026.10.2
```

Once it is ready, run from `backend/code-ingestion-pipeline/` in Bash.

```bash
NEO4J_TEST_URI=bolt://localhost:17687 uv run --locked --project .. pytest tests -q
```

In PowerShell, set `$env:NEO4J_TEST_URI` before invoking pytest. Stop the test
server with `docker stop amos-neo4j-persistence-test` when done.
