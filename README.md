# Sunset Tracker Team WS 2026/27

SunsetTracker is a prototype that helps software teams migrate legacy systems:
a knowledge base of legacy code, target code, domain knowledge and system
dependencies, queryable in natural language and visualized as arc42 views.

## Prototype (query API + frontend)

Vertical slice from tickets #24, #25, #27, #28: ask a migration question in the
browser and receive a streamed LLM answer.

- Backend (FastAPI): see [backend/README.md](backend/README.md)
- Frontend (React): see [frontend/README.md](frontend/README.md)
- One-command start: `./backend/run.sh` (Linux) or `.\backend\run.ps1` (Windows)
- Docker images: see [Documentation/containers.md](Documentation/containers.md)
  (`docker compose up` from the repo root)

## Ingestion Pipeline

Ingestion pipeline (including the reference loader): see the [setup guide](backend/code-ingestion-pipeline/README.md).

## SBOM and legal notices

The committed SPDX SBOM and frontend Legal Notices are generated from
`backend/uv.lock`, `frontend/package-lock.json` and `scripts/sbom/manual-components.json`:

```bash
scripts/sbom/regenerate_sbom.sh                 # regenerate on the current OS
scripts/sbom/regenerate_sbom.sh --check          # verify generated files
scripts/sbom/regenerate_sbom.sh --docker         # regenerate in Linux/amd64, matching CI
scripts/sbom/regenerate_sbom.sh --docker --check # verify in Linux/amd64, matching CI
scripts/sbom/regenerate_sbom.sh --refresh-registry-snapshot # refresh missing npm/PyPI license metadata, then regenerate
```

Important for Windows and macOS developers!: the SBOM generator uses Linux/amd64
to match the GitHub Actions runner. Use the `--docker` option to avoid platform-specific
differences in package metadata. The `--check` option verifies that the generated
SBOM and Legal Notices match the committed files. The CI job runs the same check
on pull requests to `develop`.
Use the Docker mode on macOS or Windows so platform-specific package license
metadata matches the Linux GitHub Actions runner. The CI job checks the SBOM,
notices, and dependency license policy on pull requests to `develop`.

### Manually inventoried components

Some materials do not appear in the npm or Python lockfiles. Add those to
[`scripts/sbom/manual-components.json`](scripts/sbom/manual-components.json); the
SBOM generator validates the entries, adds them to `sbom.spdx.json`, and includes
their license and evidence in the Legal Notices when a license is known. The
manifest starts empty. Do not add planned or mock-only components as if they
were shipped.

Each entry requires `name`, `version`, `kind`, `scope`, `purl`, `license`, and
`evidenceUrl`. Use an SPDX license identifier/expression, or `NOASSERTION` (not recommended)
when it has not been established. A `licenseTextFile` can point to a reviewed text
under `LICENSES/`. The generator validates evidence URLs and rejects duplicate
PURLs or entries already found by Syft.

Use `kind` values `container-image`, `tool`, `external-service`, `model`, or
`other`; use `scope` values `runtime`, `build`, `development`, `test`, or
`external-service`. Pin containers with an immutable `imageRef` ending in
`@sha256:<digest>` and identify them with a versioned Docker PURL.

Example template for a container that is actually part of the release:

```json
{
  "name": "graphifyy",
  "SPDXID": "SPDXRef-Package-python-graphifyy-9a8fceeada756581",
  "versionInfo": "0.9.100",
  "supplier": "NOASSERTION",
  "downloadLocation": "NOASSERTION",
  "filesAnalyzed": false,
  "sourceInfo": "acquired package info from installed python package manifest file: /backend/uv.lock",
  "licenseConcluded": "NOASSERTION",
  "licenseDeclared": "Apache-2.0",
  "copyrightText": "NOASSERTION",
  "externalRefs": [
    {
      "referenceCategory": "PACKAGE-MANAGER",
      "referenceType": "purl",
      "referenceLocator": "pkg:pypi/graphifyy@0.9.100"
    }
  ],
  "licenseInfoInFiles": [
    "Apache-2.0"
  ]
}
```

The current job does not discover or scan image references in Compose or
Kubernetes manifests. A manual container entry records that image as a
component; it does not inventory the packages inside the image. To inventory
those too, scan the pinned image with Syft and merge that image SBOM as a
separate generator step. Syft supports scanning container images and emitting
SPDX JSON. [Syft scanning documentation](https://github.com/anchore/syft/wiki/supported-sources).

After editing the manifest or adding license texts, regenerate with
`scripts/sbom/regenerate_sbom.sh --docker` and commit the manifest, SBOM, and
Legal Notices together.
GitHub Actions checks use the committed registry snapshot and do not query live
registries. When a dependency is missing license metadata, run the refresh
command, review the generated snapshot records (including source URL and response
hash), then commit the snapshot together with the regenerated SBOM and notices.
The completeness check reports unresolved suppliers and artifact hashes for
review; it fails on missing component identity, PURLs, relationships, author, or
timestamp. Checksums are mapped from `package-lock.json` integrity values and
`uv.lock` artifact hashes when available.
