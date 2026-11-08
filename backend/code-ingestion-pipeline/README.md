# Reference source to graph prototype

This is an independent subproject inside the backend. It contains the reference
loader, Graphify integration, configuration, dependencies, tests and local outputs.
It does not use the web application's `app/`, `tests/` or Python environment.

```text
backend/code-ingestion-pipeline/
  pyproject.toml             reference-loader dependencies and test configuration
  requirements-graphify.txt  Graphify requirements
  setup.py                  add Graphify after reference-loader setup
  run_pipeline.py           full pipeline command
  src/migration_assistant/  reference-loader implementation
  config/                   reference-source configuration
  tests/                    loader and pipeline tests
  .venv/                    one local environment for this subproject (ignored)
  .cache/                   checkouts and graph outputs (ignored)
```

The flow remains:

```text
reference repository → bootstrap → sources.jsonl → analysis copies → Graphify
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
```

PowerShell equivalent:

```powershell
cd backend/code-ingestion-pipeline
.\.venv\Scripts\Activate.ps1
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
# One graph containing all configured components
python run_pipeline.py

# A separate graph for each component
python run_pipeline.py --graph-mode per-component

# Select a stage and its components
python run_pipeline.py --stage step-04a --components monolith catalog-service

# Use a local reference source configuration
python run_pipeline.py --config config/reference-source.local.yaml
```

Runs never install packages. Bootstrap may fetch reference code from GitHub using
existing Git credentials. Its configuration controls the source, stage, components,
filters and checkout workspace. It prefers `config/reference-source.local.yaml`
if present, otherwise `config/reference-source.yaml`. Source and workspace paths
inside configuration files are relative to this subproject's working directory.
If reusing a local configuration from before the move, adjust relative source paths.
The standalone bootstrap CLI remains `python -m migration_assistant.bootstrap.cli`
with `PYTHONPATH=src`, as described in the reference-loader guide.

The pipeline reads bootstrap's JSONL, including complete selected file contents,
and reconstructs those files for Graphify. This extra source copy remains intentional
for the prototype. Graphify runs locally with `--code-only` and `GRAPHIFY_BACKEND=none`.
It may parse only a subset of selected formats; optional SQL grammars are not installed.
No manifests or separate Graphify runner are used.

## Results

The default checkout workspace is `.cache/reference/`; the pipeline prints its new
run folder on each invocation:

```text
.cache/ingestion/<UTC-time>-<unique-suffix>/
  sources.jsonl
  bootstrap.log
  sources/<repoId>/<original-path>
  graphs/combined/                     # or graphs/<repoId>/
    extract.log
    cluster.log
    graphify-out/
      graph.json
      graph.html
      GRAPH_REPORT.md
```

Open `graph.html` in a browser. Each run gets a new folder. On failure, inspect the
printed log path; partial output remains for diagnosis. Use `--verbose` for tracebacks.
`--output-dir PATH` overrides the parent folder for runs. Explicit config and output
paths are relative to the terminal's current directory. Output inside this repository
must be Git-ignored. Graphify does not modify reference checkouts.

Old environments and cached outputs elsewhere in the repository have not been moved
or deleted; new runs use the subproject's own `.cache/`.

## Code Entity Extraction (Issue #19)

Extracts structured structural code entities (classes, interfaces, methods, constructors,
and database tables) conforming to Section 3.1 & 3.2 of the Architecture Contract.

### Standalone CLI

To extract entities from a bootstrap `sources.jsonl` file:

```bash
# Working directory: backend/code-ingestion-pipeline/
python -m migration_assistant.bootstrap.extract_entities_cli \
    --sources .cache/ingestion/<run>/sources.jsonl \
    --out .cache/ingestion/<run>/entities.jsonl \
    --snapshot-id <snapshotId>
```

To extract entities from predefined/mock parser output for decoupled development (AC4):

```bash
python -m migration_assistant.bootstrap.extract_entities_cli \
    --mock path/to/mock_records.json \
    --out .cache/ingestion/mock-entities.jsonl \
    --snapshot-id <snapshotId>
```

Each record in `entities.jsonl` is formatted as a canonical `FactRecord` (JSONL) with:
- `schemaVersion`: `"1.0.0"`
- `recordType`: `"SymbolObservation"`
- `recordId`: deterministic SHA-256 observation hash
- `snapshotId`: snapshot identity scoping the observation
- `payload`: typed attributes (`kind`, `name`, `qualifiedName`, `sourceSpan`, `modifiers`, `signature`, `docstring`, `metadata`)
- `evidenceReferences`: exact git source span URI (`git:<repoId>@<commitSha>:<path>#L<start>-L<end>`)

## Tests

Install the loader's test dependencies, activate this project's environment, and run:

```bash
# Working directory: backend/code-ingestion-pipeline/
python -m pytest tests -q
```

The subproject's `pyproject.toml` supplies the source import path and test configuration.
Tests cover the reference loader using temporary local Git fixtures and need no GitHub
connection. They do not build or execute downloaded source code. The backend web
application should run its own tests separately rather than collect the entire backend.
Windows/macOS execution remains unverified. SBOM work remains deferred.
