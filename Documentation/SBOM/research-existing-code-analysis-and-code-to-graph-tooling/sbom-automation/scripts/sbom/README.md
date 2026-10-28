# SBOM and licence automation

Regenerates the Software Bill of Materials from `uv.lock` and checks that no dependency violates the project licence. The check works even before the project licence has been chosen.

## Files

| Path | Purpose |
|---|---|
| `.github/workflows/sbom-and-licences.yml` | GitHub Actions workflow |
| `scripts/sbom/regenerate_sbom.sh` | Entry point; run it locally or in CI |
| `scripts/sbom/sbom_tool.py` | Merge, licence gate and Markdown rendering (Python standard library only, Python 3.11+) |
| `scripts/sbom/licence-policy.json` | Which dependency licences are allowed for which project licence |
| `scripts/sbom/licence-exceptions.json` | Approved exceptions, each with a justification, an approver and an expiry date |
| `sbom/supplement*.cdx.json` | Components that are not in `uv.lock`: containers, models, tools, external services |
| `sbom/sbom.cdx.json` | **Generated:** runtime SBOM (CycloneDX 1.6) |
| `sbom/sbom-dev.cdx.json` | **Generated:** development-only dependencies |
| `sbom/SBOM.md` | **Generated:** table to paste into or link from the planning document |
| `sbom/THIRD_PARTY_LICENSES.md` | **Generated:** licence and NOTICE texts of the runtime dependencies (attribution) |
| `sbom/licence-report.md` | **Generated:** result of the licence gate |

Add `.sbom-work/` to your `.gitignore` (see `gitignore.snippet`). It holds the CI working copies. If the executable bit is lost when extracting, run `git update-index --chmod=+x scripts/sbom/regenerate_sbom.sh`.

## Local use

```bash
scripts/sbom/regenerate_sbom.sh                    # Linux: regenerate sbom/ after changing dependencies
scripts/sbom/regenerate_sbom.sh --check            # what CI runs on pull requests
scripts/sbom/regenerate_sbom.sh --docker           # macOS / Windows: same, inside a linux/amd64 container
```

Requirements: `uv`, `python3` (3.11 or newer) and `git`, or only Docker when using `--docker`. The script never touches your `.venv`; it installs the locked dependencies into temporary environments.

**Why `--docker` on macOS/Windows:** the SBOM is generated from an *installed* environment (that is how licence data is obtained). Platform markers and platform-specific packages can differ from the Linux CI runner, which would make the CI `--check` fail. Running inside `linux/amd64` reproduces CI. Alternatively, download the `sbom` artifact from the CI run and commit its `sbom/` files.

## How it works

1. `uv lock --check` fails if `uv.lock` does not match `pyproject.toml`.
2. `uv sync --frozen` installs the runtime dependencies and, separately, the dev dependencies into temporary virtual environments.
3. `cyclonedx-py environment` (pinned version) creates CycloneDX 1.6 SBOMs that include licence data. uv's native `uv export --format cyclonedx1.5` is not used, because it does not yet include licence information.
4. The runtime SBOM is merged with the supplement. The serial number is derived from the hash of `uv.lock` and the supplement, so it changes exactly when the dependencies change. The timestamp is informational: `--check` ignores `metadata.timestamp`, and regeneration keeps the committed file when only the timestamp would differ, so there are no timestamp-only commits. The step warns about packages that are in `uv.lock` but not installed on this platform (platform markers).
5. The licence gate runs:
   - **Project licence:** finds `LICENSE`/`COPYING` and identifies its licence from the text. Fails if the file and `pyproject.toml` disagree, or if `pyproject.toml` declares a licence but no `LICENSE` file exists.
   - **Dependency licences:** each component is evaluated against the policy:
     - *linked*: Python packages imported by our code; the strictest rules apply.
     - *aggregate*: separate programs, containers and models. Copyleft is allowed here (`✅ᵃ`) because nothing is linked; non-OSI licences are still denied.
     - *report*: dev-only tools, listed but never blocking.

     SPDX expressions with `OR`, `AND` and `WITH` are evaluated. Unknown or missing licences fail the gate.
   - **Licence files:** warns when an installed package ships no licence text. All shipped `LICENSE`/`NOTICE` files are collected into `THIRD_PARTY_LICENSES.md`.
6. `SBOM.md` is rendered for the planning document.

## While the project licence is undecided

| Repository state | Behaviour |
|---|---|
| No `LICENSE` file, no `PROJECT_LICENSE` | **Undecided mode.** Every dependency is checked against all candidates (`MIT`, `Apache-2.0`, `GPL-3.0-or-later`, `AGPL-3.0-or-later`; configurable in the policy). The report shows which candidates are still possible. The gate fails only on unknown licences, or on dependencies that no candidate allows. |
| No `LICENSE`, repository variable `PROJECT_LICENSE=Apache-2.0` | Enforces that licence (useful to "try on" a choice) |
| `LICENSE` present | Enforces the detected licence; `PROJECT_LICENSE` is ignored |
| Tag `v*` (release) | A `LICENSE` file is mandatory |

The report's *Compatibility summary* shows the effect of each candidate. For example, adding an AGPL dependency such as repowise removes `MIT` and `Apache-2.0` from the candidates.

## Exceptions

`review` results (for example an LGPL library in a permissive project) need an entry in `licence-exceptions.json`:

```json
{"component": "psycopg", "version": "*",
 "justification": "LGPL-3.0 library imported unmodified as a replaceable package",
 "approved_by": "PO + legal contact (MIG-123)", "expires": "2027-03-31"}
```

Expired or incomplete entries are ignored and reported. The weekly scheduled run catches expiries.

## CI behaviour

| Event | Action |
|---|---|
| Pull request touching dependencies, licences or the SBOM tooling | Regenerates in a temporary directory; **fails** if the committed `sbom/` is stale or the licence gate fails |
| Push to `main` | Regenerates. If `SBOM_AUTOCOMMIT=true`, commits changes as `github-actions[bot]`; otherwise it emits a warning and uploads the result as the `sbom` artifact |
| Tag `v*` | Same as `main`, plus a `LICENSE` file is required |
| Weekly, manual | Re-check |

The report is also written to the job summary. If the workflow is a *required* status check, remove the `paths` filter from `pull_request`; otherwise PRs that don't touch those files never get the check.

## Limits

- The policy encodes common engineering readings of licence compatibility, not legal advice. Have it reviewed once the project licence is chosen.
- The environment-based SBOM reflects the CI platform (Linux). Packages restricted to other platforms are listed as warnings.
- Containers and models come from the manual supplement. Once container images are built, add `syft <image> -o cyclonedx-json` and merge its output the same way.
- Pin the GitHub Actions to commit SHAs and keep `CYCLONEDX_BOM_VERSION` pinned; update both deliberately.
- The `cyclonedx-py` options (`--pyproject`, `--mc-type`, `--sv`, `--of`, `--output-reproducible`, `-o`) follow the cyclonedx-bom 7.x documentation but were not run against a real project while this was written. If the first CI run reports an option error, adjust the `CDX=(...)` line in `regenerate_sbom.sh`.
- When a package declares several licences (licence field plus classifiers), they are treated as alternatives (`OR`). Inconsistent upstream metadata, such as `GPL-3.0` in one field and an `MIT` classifier, can therefore pass. Check the report for such components.
- Dev dependencies are taken from the `dev` group (`--only-dev`). If you use other dependency groups, change the second `uv sync` to `--all-groups` or `--group <name>`.
- Auto-commit on `main` fails on protected branches unless the Actions bot may push; then use the artifact and a normal pull request.
