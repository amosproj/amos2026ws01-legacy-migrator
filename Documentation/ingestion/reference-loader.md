> **Deprecated documentation:** The reference loader is now set up as part of the
> complete ingestion pipeline. Follow the [pipeline setup guide](../../backend/code-ingestion-pipeline/README.md)
> instead of the standalone setup instructions below.

# Reference loader

Loads one stage of the reference system into the prototype so its source code can be analysed. Part of Issue #17.

## Purpose

The loader prepares a local, pinned copy of the reference source and reads the relevant files from it. It does not parse code and does not write to a database.

```text
Repository  ->  local checkout  ->  load files  ->  parser  ->  knowledge base
(GitHub or      (workspace          (this loader)    (not part     (not part
 local copy)     cache folder)                        of #17)       of #17)
```

In `Documentation/SBOM/sbom-a-architecture.mmd` this matches three boxes:

| Box | Role there | What the loader does |
|---|---|---|
| RES | Resolve a ref to a full commit SHA | Resolves the stage tag to a full SHA and checks that each component is at the SHA in `stage.json` |
| CO | Ingest worker / local Git CLI, reads an exact SHA, no builds or code execution | Runs git with safe settings and only reads files |
| RC | Local repo cache | The `workspace` folder (default `.cache/reference`, so `backend/code-ingestion-pipeline/.cache/reference` when run from `backend/code-ingestion-pipeline/`) |

A local source needs no network. An `https://` source is fetched once into the cache; the diagram expects that preparation to happen before offline use.

## Setup

The reference loader is part of the independent ingestion subproject at
`backend/code-ingestion-pipeline/`. Its code, configuration, tests, environment and
cache live there, separate from the backend web application.

1. Install Python 3.12 (see `.python-version`) and Git.
2. From the repository root, enter the ingestion subproject, then create and
   activate its own virtual environment. Do not reuse or move the web application's
   environment.

   ```bash
   cd backend/code-ingestion-pipeline
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

   PowerShell equivalent:

   ```powershell
   cd backend/code-ingestion-pipeline
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   No `py` launcher? Use conda only to obtain Python 3.12, then run
   `python -m venv .venv` inside the subproject and activate that `.venv`.

3. Install the loader dependencies:

   ```bash
   python -m pip install "pydantic>=2" "pyyaml>=6"
   python -m pip install "pytest>=8"  # optional, for tests
   ```

   The project has no build backend configured; keep using its source directory
   directly. Set the import path for bootstrap and Python loader usage:

   ```bash
   export PYTHONPATH=src
   ```

   ```powershell
   $env:PYTHONPATH = "src"
   ```

All commands below run from `backend/code-ingestion-pipeline/` with its `.venv`
active. When loader setup is complete, follow the
[pipeline guide](../../backend/code-ingestion-pipeline/README.md) to install
Graphify into this same environment. The bootstrap CLI always runs the full pipeline
and requires Graphify. The independent loader functions below do not require it.

## Configuration

Default file: `backend/code-ingestion-pipeline/config/reference-source.yaml` (committed). Relative paths in this guide are relative to `backend/code-ingestion-pipeline/`.

| Field | Meaning |
|---|---|
| `source` | `https://` URL or local path of the umbrella repository (`legacy-example-stages`) |
| `public_url` | Base URL of the GitHub organisation, used to build links |
| `stage` | Stage tag to load, for example `step-00` or `step-04a`. Any tag name is allowed; letters, digits, `.`, `_`, `/`, `-`, and it must not start with `-` |
| `components` | Optional component filter, for example `[monolith]`. Omit it or use `[]` (the committed default) to load every component in the selected stage |
| `workspace` | Cache folder for the checkout, relative to where the command runs (git-ignored, default `.cache/reference`) |
| `include` | File extensions (`.java`) and exact file names (`Dockerfile`) to load |
| `exclude` | Glob patterns on repository-relative paths, `/` separated. `**` crosses folders. Checked before `include` |
| `max_file_size_kb` | Larger files are skipped. Default 1024 |

**Local copy (recommended for the offline demo).** Create `backend/code-ingestion-pipeline/config/reference-source.local.yaml` (git-ignored) with the same fields and your local path as `source`. If this file exists it is used instead of the default file. It replaces the default file completely; nothing is merged.

Command-line options:

| Option | Effect |
|---|---|
| `--config PATH` | Use this config file. Default: the local file if it exists, otherwise `config/reference-source.yaml` |
| `--stage STAGE` | Override `stage` for this run only |
| `--components A B ...` | Override `components` for this run only |
| `--out PATH` | Also write the loaded files as JSONL to the chosen path |
| `--output-dir PATH` | Parent directory for pipeline runs; default `.cache/ingestion` in the ingestion subproject |
| `--verbose` | Show the full traceback on errors |

The config file itself is never changed by these options.

Without `--components`, the YAML filter applies. If that filter is omitted or `[]`,
the loader reads all entries in the selected stage's `stage.json` under `komponenten`
and checks out each component at its pinned commit before continuing the pipeline.

## Usage

Bootstrap checks out and loads the selected source, generates a separate `graph.json`
and `graph.html` for every component with loaded files, then writes canonical entity
and relationship JSONL. It does not perform clustering, community labeling, analysis
or report generation. Loader-only usage is available through Python, not the CLI.

```powershell
# Default run: configured stage, all its components unless filtered in YAML
.\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli

# Another stage, two components
.\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli --stage step-04a --components monolith catalog-service

# Also write the files as JSONL
.\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli --out .cache/output/step-00.jsonl
```

Example loader summary from a default pipeline run (local copy, stage `step-00`):

```text
config: config/reference-source.local.yaml
stage: step-00
umbrella: refs/tags/step-00 8dd3f5286de673fda29af9370c890249cdfe1d89
component: legacy-example-monolith ddcd96502943c1cda4cbb2fa5a6be3a87c04933e
files loaded: 85
  html: 10
  java: 30
  javascript: 7
  sql: 6
  xml: 32
files skipped: 119
  excluded: 86
  not_included: 33
```

The summary is followed by the run folder, component graph progress and canonical
fact counts. Each invocation creates a new run directory. Changing `--stage` in the
same workspace is fine. See the [pipeline guide](../../backend/code-ingestion-pipeline/README.md)
for the output layout and failure diagnostics.

## Use from Python

The loader remains independent of Graphify and the rest of the pipeline:

```python
from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.domain.reference_source import default_config_path, load_config

config = load_config(default_config_path())
checkout = LocalGitAdapter().checkout(config)
result = load_sources(config, checkout)

for file in result.files:
    print(file.path, file.language, file.github_url)
```

After the checkout the code is a normal folder at the pinned commit, so a parser can also run directly on a component folder (`checkout.members[0].local_path`) instead of using the loaded file contents.

The pipeline does exactly this: it combines each member's `local_path` with the
selected `result.files` paths and passes those original files to Graphify, separately
for each component. No source reconstruction or JSONL reload is necessary.

## Output

`--out` writes one JSON object per line, one per loaded file, sorted by component and path. Keys are camelCase.

| Field | Meaning |
|---|---|
| `repoId` | Component repository, for example `legacy-example-monolith` |
| `origin` | `legacy` |
| `stage` | Stage that was loaded |
| `commitSha` | Full commit SHA of the component |
| `publicUrl` | `public_url` + `/` + `repoId` |
| `path` | Path relative to the component root, `/` separated |
| `language` | `java`, `xml`, `properties`, `sql`, `yaml`, `javascript`, `vue`, `html`, `shell`, `nginx-conf` or `dockerfile` |
| `sizeBytes` | Size of the file |
| `contentSha256` | SHA-256 of the raw file bytes |
| `encoding` | `utf-8`, or `latin-1` if the file is not valid UTF-8 |
| `content` | File text |
| `githubUrl` | `{publicUrl}/blob/{commitSha}/{path}` |

Example `githubUrl`:
`https://github.com/legacy-modernization-example/legacy-example-monolith/blob/ddcd96502943c1cda4cbb2fa5a6be3a87c04933e/Common/InventoryData.sql`

Files that are not loaded are listed with a reason (and, for read errors, the OS error): `excluded`, `not_included`, `too_large`, `binary`, `symlink`, `outside_component`, `unreadable`, `unreadable_dir`. The normal output shows only the counts.

## Errors

Errors print one line to stderr, starting with `ERROR:`. Config problems with several fields are joined with ` ; `.

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Expected error (table below) |
| 2 | Unexpected failure (`ERROR: unexpected failure, rerun with --verbose`), or wrong command-line arguments |

| Message (shortened) | Cause |
|---|---|
| `Config file not found: <path>` | `--config` or the default file is missing |
| `Missing field '<f>' in <file>` / `Unknown field` / `Invalid value for field '<f>'` | Config does not validate |
| `Unknown stage '<s>': no tag '<s>' in the source` | The stage is not a tag of the umbrella repository |
| `Component '<c>' is not in stage '<s>' (available: ...)` | `stage.json` of that stage does not list the component |
| `Source not found: <path>` / `Source is not a Git repository` | Local `source` is wrong |
| `Only https:// URLs (without credentials) and local paths are supported as source` | `http://`, `ssh://`, `file://`, or credentials in the URL |
| `git was not found on PATH` | Git is not installed |
| `Submodule '<c>' is missing in the source` / `is not declared in .gitmodules` | Component folder or declaration missing |
| `Submodule '<c>' is at <sha>, but stage.json pins <sha>` | Checked-out commit differs from `stage.json` |
| `The workspace ... was created from a different source` | Cache was made from another `source`; delete the workspace folder |
| `Component '<c>' has local changes and does not match commit <sha>` | Someone edited files in the cache |
| `Graph generation failed for component ...` | Graphify dependency, extraction or export failure; partial run is retained |
| `git <command> failed: <git message>` | Git itself failed (for example no network) |

## Safety

- Clones, fetches and checkouts happen in the configured workspace. Developers keep this workspace separate from the original source repository.
- The workspace (`backend/code-ingestion-pipeline/.cache/reference`) is git-ignored and can be deleted at any time.
- Directory placement and Git ignore rules are managed by developers. The loader and pipeline do not check whether configured locations are ignored, tracked or inside the source repository. Choose output paths that do not overwrite source files. Temporary directories use Python's standard OS temporary location.
- Every Git call uses an argument list (never a shell). Checkout and source-status commands use `core.hooksPath` pointing at an empty folder (hooks off), `core.fsmonitor=false`, `core.longpaths=true` and no terminal prompts.
- Only the selected submodules are initialised, never recursively.
- An `https://` source uses the https transport only (`protocol.allow=never`, `protocol.https.allow=always`). Other URL types are refused.
- The loader checks that the cache is clean (`git status --porcelain`) before reading, so files match the pinned commit.
- Symlinks and paths that leave the component folder are skipped. On Windows, files are read with the extended-length path prefix so deep folders work.
- The loader only reads files. It does not build or execute any code of the reference system.

## Tests

```powershell
python -m pytest tests -v
```

The suite builds a small fake reference setup with real git in a temporary folder
and does not use the network. Pipeline tests also run Graphify when it is installed
in the active environment.

Optional integration test against your real local copy (skipped when the variable is not set):

```powershell
$env:REFERENCE_SOURCE = "D:/path/to/legacy-example-stages"
python -m pytest tests/test_real_reference_source.py -v
```

```bash
REFERENCE_SOURCE=/path/to/legacy-example-stages python -m pytest tests/test_real_reference_source.py -v
```

## Acceptance criteria

| # | Criterion | Test file |
|---|---|---|
| 1 | The reference repository can be configured as an input source | `backend/code-ingestion-pipeline/tests/test_configuration.py` |
| 2 | Relevant source files are detected and loaded | `backend/code-ingestion-pipeline/tests/test_load_sources.py` |
| 3 | The loading process can be executed repeatedly | `backend/code-ingestion-pipeline/tests/test_repeatable.py` |
| 4 | Errors during loading are reported clearly | `backend/code-ingestion-pipeline/tests/test_clear_errors.py` (and the error cases in `backend/code-ingestion-pipeline/tests/test_configuration.py`) |
| 5 | The original reference repository is not modified | `backend/code-ingestion-pipeline/tests/test_original_unchanged.py` |

## Known limitations

- A real clone from GitHub has not been tested yet. If the organisation is private, a plain clone needs git credentials already stored on the machine; credentials inside the URL are refused.
- The relocated suite has been tested on Linux; Windows/macOS execution after the move remains unverified.
- Read errors on files and folders are tested with simulated errors only.
- The ingestion package has no build backend, so use `PYTHONPATH=src` instead of installing it with pip.
- The workspace is tied to one source. Switching `source` needs a new or emptied workspace folder.
