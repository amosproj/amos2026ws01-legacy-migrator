# Reference source to graph prototype

This is an independent subproject inside the backend. It contains the reference
loader, Graphify integration, configuration, dependencies, tests and local outputs.
It does not use the web application's `app/`, `tests/` or Python environment.

```text
backend/code-ingestion-pipeline/
  requirements.txt          complete loader and Graphify runtime
  requirements-graphify.txt  Graphify requirements
  setup.py                  install the complete pipeline into its virtual environment
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

Run commands from `backend/code-ingestion-pipeline/`, except the initial `cd`
from the repository root. The loader and Graphify share this subproject's `.venv`.

## Prerequisites

- Python **3.12**, matching the repository's `.python-version` and setup script.
- Git available on `PATH`; check with `git --version`.
- Network access for the initial Python dependency installation. An HTTPS reference
  source also needs network access and any Git credentials required by that source.

## Install the complete pipeline

`setup.py` installs `requirements.txt`, which includes Pydantic for the loader and
the pinned Graphify dependencies from `requirements-graphify.txt`. Those dependencies
also supply PyYAML for reading the reference configuration. There is no separate
loader installation step. Setup installs packages only; it does not check out
reference code or run the pipeline.

### Linux and macOS

From the repository root:

```bash
cd backend/code-ingestion-pipeline
python3.12 -m venv .venv
.venv/bin/python setup.py
export PYTHONPATH=src
```

### Windows PowerShell

From the repository root:

```powershell
cd backend/code-ingestion-pipeline
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe setup.py
$env:PYTHONPATH = "src"
```

If the `py` launcher is unavailable, use `python -m venv .venv` after confirming
`python --version` reports Python 3.12.

These commands call the virtual environment's Python directly, so activation and
PowerShell execution-policy changes are unnecessary. If you prefer activation,
use `source .venv/bin/activate` on Linux/macOS or
`.\.venv\Scripts\Activate.ps1` in PowerShell, then use `python` in subsequent commands.

The package is imported from `src`; `setup.py` is a dependency installer, not a
package build script. `PYTHONPATH` applies to the current terminal. In each new
terminal, return to the ingestion subproject and set it again.

## Configure the reference source

The committed `config/reference-source.yaml` uses the HTTPS umbrella repository.
Bootstrap uses it unless `config/reference-source.local.yaml` exists or you provide
`--config PATH`.

For a local reference copy, copy the full configuration first:

```bash
cp config/reference-source.yaml config/reference-source.local.yaml
```

PowerShell:

```powershell
Copy-Item config/reference-source.yaml config/reference-source.local.yaml
```

Edit `source` in that local file to point to the umbrella repository, whose selected
component submodules must already be initialized. For example:

```yaml
# Linux/macOS example
source: '/home/developer/reference/legacy-example-stages'
```

```yaml
# Windows example: forward slashes avoid YAML backslash escaping
source: 'D:/reference/legacy-example-stages'
```

Keep the remaining fields from the copied file. The local file replaces the
committed configuration completely; it is not merged with it.

| Setting | Purpose |
|---|---|
| `stage` | Stage tag to check out, such as `step-00` |
| `components` | `[]` selects all components in the stage; a list selects specific components |
| `workspace` | Checkout cache, default `.cache/reference` |
| `public_url` | Base URL used for revision-pinned source links |
| `include`, `exclude` | File selection rules |
| `max_file_size_kb` | Maximum loaded file size |

Relative source and workspace paths are resolved from the terminal's working
directory. Keep the workspace separate from the original reference repository.
The default `.cache/`, `.venv/`, and local configuration are Git-ignored. Developers
manage appropriate paths and ignore rules for any custom locations; the pipeline
does not enforce them.

## Run


Linux/macOS:

```bash
export PYTHONPATH=src
.venv/bin/python -m migration_assistant.bootstrap.cli
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli
```

Append the same options on either platform:

```text
--stage step-04a --components monolith catalog-service
--config config/reference-source.local.yaml
--output-dir .cache/ingestion
--out .cache/output/sources.jsonl
--verbose
```

No API key is required for this local AST pipeline.

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


Install pytest into the same environment, then run the ingestion suite.

Linux/macOS:

```bash
.venv/bin/python -m pip install "pytest>=8"
export PYTHONPATH=src
.venv/bin/python -m pytest tests -q
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install "pytest>=8"
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest tests -q
```

Tests cover the reference loader using temporary local Git fixtures and need no GitHub
connection. CLI and adapter contract tests use stubs without requiring Graphify;
the real Graphify integration test runs when installed. Tests also cover custom
output paths and independent component graphs. They do not build or execute downloaded
source code. The backend web application should run its own tests separately rather
than collect the entire backend.
Windows/macOS execution remains unverified. SBOM work remains deferred.

## Updating or recreating the environment


Rerun the platform's `setup.py` command when runtime requirements change. Recreate
the subproject's `.venv` when changing its Python version or moving the checkout;
virtual environments should not be copied between machines or operating systems.
