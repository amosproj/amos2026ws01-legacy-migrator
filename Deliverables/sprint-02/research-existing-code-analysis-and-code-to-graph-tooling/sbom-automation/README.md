# SBOM Automation Scripts

This directory contains the local tooling for generating a CycloneDX Software Bill of Materials (SBOM) from `uv.lock` and checking dependency licences against the project licence policy.

The main entry point is:

```bash
./regenerate_sbom.sh
```

## Contents

| File | Purpose |
|---|---|
| `regenerate_sbom.sh` | Main script: regenerates the SBOM, runs the licence gate, and renders Markdown reports |
| `sbom_tool.py` | Python helper for merging SBOMs, evaluating licence compatibility, and rendering reports |
| `licence-policy.json` | Defines which dependency licences are acceptable for each candidate project licence |
| `licence-exceptions.json` | Optional approved exceptions for individual components and versions |
| `README.md` | This documentation |

## Requirements

- Bash
- Git
- [`uv`](https://docs.astral.sh/uv/)
- Python 3.11 or newer
- Docker, only if using `--docker`

The Python tool uses only the standard library.

## Important: project root

`regenerate_sbom.sh` automatically changes to the Git repository root:

```bash
git rev-parse --show-toplevel
```

It therefore expects these files in the **repository root**:

```text
pyproject.toml
uv.lock
```

It does not look for them in the directory from which the script is started.

For this repository, the expected root is:

```text
amos2026ws01-legacy-migrator/
```

So `pyproject.toml` and `uv.lock` must be located there:

```text
amos2026ws01-legacy-migrator/pyproject.toml
amos2026ws01-legacy-migrator/uv.lock
```

## Usage

Run from this directory:

```bash
./regenerate_sbom.sh
```

Other modes:

```bash
./regenerate_sbom.sh --check
```

Checks whether the committed SBOM files match the current `uv.lock` and supplement. This is the mode intended for CI.

```bash
./regenerate_sbom.sh --docker
```

Runs the same process inside a Linux `amd64` container. This is useful on macOS or Windows, where the locally installed Python environment may differ from the Linux CI environment.

```bash
./regenerate_sbom.sh --docker --check
```

Runs the CI-style stale check inside Docker.

Show help:

```bash
./regenerate_sbom.sh --help
```

## What the script does

1. Verifies that `uv.lock` matches `pyproject.toml`.
2. Installs the locked runtime and development dependencies into temporary virtual environments.
3. Generates CycloneDX 1.6 SBOMs using `cyclonedx-py`.
4. Merges the generated runtime SBOM with `sbom/supplement.cdx.json`.
5. Runs the licence gate.
6. Writes the SBOM, licence report, third-party licence notices, and Markdown SBOM table.

The script does not modify the developer’s `.venv`; it creates temporary environments instead.

## Generated output

By default, generated files are written to:

```text
amos2026ws01-legacy-migrator/sbom/
```

| Generated file | Purpose |
|---|---|
| `sbom.cdx.json` | Runtime SBOM in CycloneDX 1.6 format |
| `sbom-dev.cdx.json` | Development-dependency SBOM |
| `SBOM.md` | Human-readable SBOM table |
| `THIRD_PARTY_LICENSES.md` | Licence and notice texts for runtime dependencies |
| `licence-report.md` | Result of the licence compliance check |

A temporary copy of all generated files is also placed in:

```text
.sbom-work/
```

This directory is intended for CI artifacts and should be ignored by Git.

## Licence checking

The licence gate evaluates:

- The project licence, detected from `LICENSE` or `COPYING`
- Dependency licences from SBOM metadata and installed package metadata
- SPDX expressions containing `OR`, `AND`, and `WITH`
- Approved exceptions from `licence-exceptions.json`
- Whether installed Python packages include licence text

If no project licence has been chosen, the tool can evaluate dependencies against all configured candidate licences.

## Manual supplement

`sbom/supplement.cdx.json` contains components that are not Python dependencies in `uv.lock`, such as:

- Container images
- Machine-learning models
- External tools
- External services

Add entries there when those components become part of the delivered system.

## Common issues

### `uv.lock not found in <repository root>`

The script expects `uv.lock` in the Git repository root, not in `scripts/sbom/`.

Run:

```bash
cd /path/to/amos2026ws01-legacy-migrator
uv lock
```

Then rerun the SBOM script.

### `pyproject.toml not found in <repository root>`

Create or move `pyproject.toml` to the repository root:

```bash
cd /path/to/amos2026ws01-legacy-migrator
uv init
```

Then run:

```bash
uv lock
```

### `unknown argument: render-md`

`render-md` is not an argument of `regenerate_sbom.sh`. It is a subcommand of `sbom_tool.py`, and the shell script calls it automatically.

To render an existing SBOM manually:

```bash
python3 sbom_tool.py render-md \
  --sbom ../../sbom/sbom.cdx.json \
  --out ../../sbom/SBOM.md
```

Adjust the relative paths according to the location of the generated `sbom.cdx.json`.

## Notes

- The licence policy is an engineering aid, not legal advice.
- The generated SBOM reflects the platform on which dependencies were installed.
- The script is designed to produce reproducible output; unrelated timestamp-only changes should not create commits.