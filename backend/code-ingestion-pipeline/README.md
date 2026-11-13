# Reference source to graph prototype

This is an independent subproject inside the backend. It contains the reference
loader, Graphify integration, configuration, dependencies, tests and local outputs.
It does not use the web application's `app/`, `tests/` or Python environment.

```text
backend/code-ingestion-pipeline/
  requirements-graphify.txt  Graphify requirements
  setup.py                  add Graphify after reference-loader setup
  src/migration_assistant/
    bootstrap/              full pipeline CLI and adapter wiring
    application/            pipeline service and ports
    domain/                 source, checkout and pipeline models
    adapters/outbound/      Git, source loading, Graphify and local output adapters
  config/                   reference-source configuration
  tests/                    loader and pipeline tests
  .venv/                    one local environment for this subproject (ignored)
  .cache/                   checkouts and graph outputs (ignored)
```

The bootstrap CLI runs the complete pipeline through Python functions:

```text
reference repository → pinned checkout → load selected files
  → Graphify per component → graph.json + graph.html → canonical JSONL
```

## Setup on each developer's machine

First complete the **Setup** section of the
[reference loader guide](../../Documentation/ingestion/reference-loader.md).
Create `.venv` inside this subproject and install the loader's dependencies there.
Keep that environment active, then add Graphify:

```bash
# Working directory: backend/code-ingestion-pipeline/
python setup.py
```

When opening a new terminal, start from the repository root:

```bash
cd backend/code-ingestion-pipeline
source .venv/bin/activate
export PYTHONPATH=src
```

PowerShell equivalent:

```powershell
cd backend/code-ingestion-pipeline
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
```

`setup.py` installs only Graphify's requirements, into the already active environment.
It does not create environments or install loader/test dependencies. It downloads
packages but does not fetch reference code or generate graphs. Graphify also uses
PyYAML, so its pinned requirements may select a version of that shared package.
Every colleague follows the same order. Rerun setup when Graphify requirements change.
Recreate environments in the new location; do not move an old environment directory.

## Run

With the ingestion environment activated, from this subproject:

```bash
# One independent graph for each selected component
python -m migration_assistant.bootstrap.cli

# Select a stage and its components
python -m migration_assistant.bootstrap.cli --stage step-04a --components monolith catalog-service

# Use a local reference source configuration
python -m migration_assistant.bootstrap.cli --config config/reference-source.local.yaml

# Optionally export loaded source contents as JSONL
python -m migration_assistant.bootstrap.cli --out .cache/output/sources.jsonl
```

Runs never install packages. Bootstrap may fetch reference code from GitHub using
existing Git credentials. Its configuration controls the source, stage, components,
filters and checkout workspace. It prefers `config/reference-source.local.yaml`
if present, otherwise `config/reference-source.yaml`. Source and workspace paths
inside configuration files are relative to this subproject's working directory.
The default `components: []` loads every component in the selected stage's
`stage.json`, at its pinned commit. Omitting the YAML field has the same effect.
An explicit YAML list restricts the selection; `--components A B ...` overrides
that list for one run.
If reusing a local configuration from before the move, adjust relative source paths.

The application service passes the loader's selected original checkout paths directly
to Graphify's Python API. It never combines components or reconstructs source files.
`--out` is an optional export, not an intermediate input. Components with no loaded
files are skipped; an entirely empty selection is an error.

Graphify performs local AST extraction and exports JSON and HTML with empty community
mappings. Clustering, community labeling, analysis, learning overlays, reports and
LLM calls are omitted. A comment in the Graphify adapter identifies where optional
enrichment could be added later. With Graphify's default output settings, extraction
caches stay within each component's run folder. Graphify may parse only a subset of selected formats; missing
optional SQL grammars and empty parses produce warnings while retaining extracted nodes.

## Results

The default checkout workspace is `.cache/reference/`; the pipeline prints its new
run folder on each invocation:

```text
.cache/ingestion/<UTC-time>-<unique-suffix>/
  entities.jsonl            # canonical SymbolObservation facts
  relationships.jsonl       # canonical Relationship facts for the graph loader
  relationship-issues.jsonl # unresolved/unsupported Graphify links, when present
  graphs/<repoId>/
    graphify-out/
      graph.json
      graph.html
      cache/               # AST extraction cache
```

Open each component's `graph.html` in a browser. Each run gets a new folder. On failure,
the error identifies the component or stage and the partial run remains for diagnosis.
Use `--verbose` for tracebacks. HTML exceeding Graphify's visualization limit fails
without aggregation and leaves the generated JSON available.
`--output-dir PATH` overrides the parent folder for runs. Explicit config and output
paths are relative to the terminal's current directory. Graphify does not modify
reference checkouts.

Developers choose the workspace, output and optional export paths and manage their
Git ignore rules. The pipeline does not enforce directory placement or check whether
paths are ignored or tracked. The default `.cache/` rule covers checkouts, outputs
and extraction caches. Temporary directories use Python's standard OS temporary
location. Keep checkout workspaces separate from source repositories and choose output
paths that do not overwrite source files.

## Canonical relationship handoff

The relationship adapter converts each component's Graphify `graph.json` into canonical
JSONL files in the run folder. `entities.jsonl` contains snapshot-scoped
`SymbolObservation` facts; `relationships.jsonl` contains `Relationship` facts
whose source and target IDs refer to those observations. Both include extractor
provenance and revision-pinned source evidence. These files are the structured
handoff for the graph loader.

The adapter reads Graphify's native `nodes`/`links` schema (and the older
`nodes`/`edges` shape for fixtures), mapping `calls`, `inherits`, `implements`,
`references`, imports, and dependencies to `CALLS`, `INHERITS`, or `REFERENCES`.
Unknown, ambiguous, external, and unresolved endpoints are written to
`relationship-issues.jsonl` and never published as dangling edges. The adapter
is independent of Graphify installation in tests; mock graph JSON uses the same
normalization seam.

Old environments and cached outputs elsewhere in the repository have not been moved
or deleted; new runs use the subproject's own `.cache/`.

## Tests

Install the loader's test dependencies, activate this project's environment, and run:

```bash
# Working directory: backend/code-ingestion-pipeline/
python -m pytest tests -q
```

Set `PYTHONPATH=src` before running the tests.
Tests cover the reference loader using temporary local Git fixtures and need no GitHub
connection. CLI and adapter contract tests use stubs without requiring Graphify;
the real Graphify integration test runs when installed. Tests also cover custom
output paths and independent component graphs. They do not build or execute downloaded
source code. The backend web application should run its own tests separately rather
than collect the entire backend.
Windows/macOS execution remains unverified. SBOM work remains deferred.
