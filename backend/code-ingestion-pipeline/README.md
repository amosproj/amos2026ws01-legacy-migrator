# Reference source to graph pipeline

The ingestion pipeline shares the backend's uv environment, dependencies, and
lockfile. The CLI loads a pinned reference stage and extracts a separate graph
for each selected component. It reads selected files directly from checkout;
it does not reconstruct source copies, run clustering, or generate graph reports.

## Setup and run

Install uv, Python 3.12, and Git. From the repository root:

```bash
cd backend
uv sync --locked
cd code-ingestion-pipeline
uv run --project .. ingest
```

The commands are the same in Linux/macOS terminals and Windows PowerShell.
`uv sync --locked` installs the API, loader, Graphify, CLI, and development tools
into `backend/.venv`. No separate ingestion environment, pip setup script, or
`PYTHONPATH` configuration is needed. The module entry point remains available:

```bash
uv run --project .. python -m migration_assistant.bootstrap.cli
```

Runs do not invoke package installers. Use `uv sync --locked` after dependency
changes. Normal uv commands may synchronize the environment before invoking the
CLI; use `uv run --locked --no-sync --project .. ingest` after setup when an
explicitly preinstalled environment is required.

No API key is needed for local AST extraction. Fetching an HTTPS reference source
uses Git and any existing Git credentials.

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

Developers control output and checkout locations and their Git ignore rules. The
pipeline does not enforce output placement or refuse Git commands based on the
original source directory. Keep the configured workspace separate from that source
and choose output paths that do not overwrite source files. Default `.cache/`
locations are Git-ignored.

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
