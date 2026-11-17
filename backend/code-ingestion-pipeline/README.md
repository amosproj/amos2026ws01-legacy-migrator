# Reference source to graph pipeline

The CLI loads a pinned reference stage and extracts a separate graph for each
selected component. It reads selected files directly from checkout, without source
reconstruction, clustering, or graph reports. Canonical handoff models are shared
with the backend in `../shared_contracts/`.

## Setup and run

Install Python 3.12 and Git. The loader and Graphify are installed together by the
subproject's setup script. Run from the repository root:

Linux/macOS:

```bash
cd backend/code-ingestion-pipeline
python3.12 -m venv .venv
source .venv/bin/activate
python setup.py
export PYTHONPATH=src:..
python -m migration_assistant.bootstrap.cli
```

Windows PowerShell:

```powershell
cd backend/code-ingestion-pipeline
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python setup.py
$env:PYTHONPATH = "src;.."
python -m migration_assistant.bootstrap.cli
```

The import path includes `src` for the ingestion package and `..` for the incoming
backend shared contracts. Setup installs `requirements.txt`, including the pinned
Graphify requirements in `requirements-graphify.txt`. Normal pipeline runs never
install dependencies. No API key is needed for local AST extraction.

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
python -m migration_assistant.bootstrap.cli --stage step-04a
python -m migration_assistant.bootstrap.cli --components monolith catalog-service
python -m migration_assistant.bootstrap.cli --config config/reference-source.local.yaml
python -m migration_assistant.bootstrap.cli --output-dir .cache/ingestion --verbose
python -m migration_assistant.bootstrap.cli --out .cache/export/sources.jsonl
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
python -m shared_contracts.schema
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

Use the same Python 3.12 environment and import path as the CLI:

```bash
python -m pip install pytest
python -m pytest tests -q
```

CI also runs the ingestion suite through the backend's existing uv environment:

```bash
uv run --project .. pytest tests -q
```

Tests use temporary local Git repositories and need no GitHub connection. Real
Graphify integration and frozen develop output fixtures check canonical byte
compatibility. Tests never build or execute downloaded reference source code.
Windows/macOS execution remains unverified.
