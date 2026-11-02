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
| RC | Local repo cache | The `workspace` folder (default `.cache/reference`, so `backend/.cache/reference` when run from `backend/`) |

A local source needs no network. An `https://` source is fetched once into the cache; the diagram expects that preparation to happen before offline use.

## Setup

1. Python 3.12 (see `.python-version`).
2. In the repository root, create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   No `py` launcher? Use conda only to get Python 3.12, then create the same `.venv`:

   ```powershell
   conda create -n py312 python=3.12 -y
   conda activate py312
   python -m venv .venv
   conda deactivate
   .venv\Scripts\Activate.ps1
   ```

3. Install the dependencies listed in `backend/pyproject.toml`:

   ```powershell
   pip install "pydantic>=2" "pyyaml>=6"   # runtime
   pip install "pytest>=8"                  # dev group, only needed for the tests
   ```

   `backend/pyproject.toml` has no build backend yet, so `pip install .` is not supported. That is why the source folder is put on the path.
   The code is in `backend/`: run all commands below from there. The `.venv` stays in the repository root, which is why the commands use `..\.venv\...`.

   ```powershell
   cd backend
   $env:PYTHONPATH = "src"     # PowerShell
   ```

   ```bash
   cd backend
   export PYTHONPATH=src       # bash
   ```

## Configuration

Default file: `backend/config/reference-source.yaml` (committed). Relative paths in this guide are relative to `backend/`.

| Field | Meaning |
|---|---|
| `source` | `https://` URL or local path of the umbrella repository (`legacy-example-stages`) |
| `public_url` | Base URL of the GitHub organisation, used to build links |
| `stage` | Stage tag to load, for example `step-00` or `step-04a`. Any tag name is allowed; letters, digits, `.`, `_`, `/`, `-`, and it must not start with `-` |
| `components` | Component repositories to load, for example `[monolith]` |
| `workspace` | Cache folder for the checkout, relative to where the command runs (git-ignored, default `.cache/reference`) |
| `include` | File extensions (`.java`) and exact file names (`Dockerfile`) to load |
| `exclude` | Glob patterns on repository-relative paths, `/` separated. `**` crosses folders. Checked before `include` |
| `max_file_size_kb` | Larger files are skipped. Default 1024 |

**Local copy (recommended for the offline demo).** Create `backend/config/reference-source.local.yaml` (git-ignored) with the same fields and your local path as `source`. If this file exists it is used instead of the default file. It replaces the default file completely; nothing is merged.

Command-line options:

| Option | Effect |
|---|---|
| `--config PATH` | Use this config file. Default: the local file if it exists, otherwise `config/reference-source.yaml` |
| `--stage STAGE` | Override `stage` for this run only |
| `--components A B ...` | Override `components` for this run only |
| `--out PATH` | Also write the loaded files as JSONL. Refused inside the source repository or the workspace |
| `--verbose` | Show the full traceback on errors |

The config file itself is never changed by these options.

## Usage

```powershell
# Default run: stage and components from the config file
..\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli

# Another stage, two components
..\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli --stage step-04a --components monolith catalog-service

# Also write the files as JSONL
..\.venv\Scripts\python.exe -m migration_assistant.bootstrap.cli --out .cache/output/step-00.jsonl
```

Example output of the default run (local copy, stage `step-00`):

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

Running it again gives the same result. Changing `--stage` in the same workspace is fine.

## Use from Python

The ingestion pipeline can call the loader directly:

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
| `--out must not be inside the source repository` / `...the workspace` | Unsafe output path |
| `git <command> failed: <git message>` | Git itself failed (for example no network) |

## Safety

- The original repository is never modified. All clones, fetches and checkouts happen in the workspace folder, and git is refused if its working directory is inside a local source.
- The workspace (`backend/.cache/reference`) is git-ignored and can be deleted at any time.
- Every git call uses an argument list (never a shell), with `core.hooksPath` pointing at an empty folder (hooks off), `core.fsmonitor=false`, `core.longpaths=true` and no terminal prompts.
- Only the selected submodules are initialised, never recursively.
- An `https://` source uses the https transport only (`protocol.allow=never`, `protocol.https.allow=always`). Other URL types are refused.
- The loader checks that the cache is clean (`git status --porcelain`) before reading, so files match the pinned commit.
- Symlinks and paths that leave the component folder are skipped. On Windows, files are read with the extended-length path prefix so deep folders work.
- The loader only reads files. It does not build or execute any code of the reference system.

## Tests

```powershell
..\.venv\Scripts\python.exe -m pytest -v
```

52 tests are collected. The suite builds a small fake reference setup with real git in a temporary folder and does not use the network.

Optional integration test against your real local copy (skipped when the variable is not set):

```powershell
$env:REFERENCE_SOURCE = "D:/path/to/legacy-example-stages"
..\.venv\Scripts\python.exe -m pytest tests/test_real_reference_source.py -v
```

```bash
REFERENCE_SOURCE=/path/to/legacy-example-stages python -m pytest tests/test_real_reference_source.py -v
```

## Acceptance criteria

| # | Criterion | Test file |
|---|---|---|
| 1 | The reference repository can be configured as an input source | `backend/tests/test_configuration.py` |
| 2 | Relevant source files are detected and loaded | `backend/tests/test_load_sources.py` |
| 3 | The loading process can be executed repeatedly | `backend/tests/test_repeatable.py` |
| 4 | Errors during loading are reported clearly | `backend/tests/test_clear_errors.py` (and the error cases in `backend/tests/test_configuration.py`) |
| 5 | The original reference repository is not modified | `backend/tests/test_original_unchanged.py` |

## Known limitations

- A real clone from GitHub has not been tested yet. If the organisation is private, a plain clone needs git credentials already stored on the machine; credentials inside the URL are refused.
- The test suite takes about 90 seconds.
- Only tested on Windows. Linux and macOS have not been tried.
- The exit-code-2 path and `--verbose` are not covered by a test.
- Read errors on files and folders are tested with simulated errors only.
- `pyproject.toml` has no build backend, so the package cannot be installed with pip yet.
- The workspace is tied to one source. Switching `source` needs a new or emptied workspace folder.
