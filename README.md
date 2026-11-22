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

The repository has one committed SBOM artifact: SPDX 3.0.1 JSON in
[`sbom.spdx.json`](sbom.spdx.json). Syft catalogs the project and its locked
runtime dependencies; the deterministic post-processor adds lockfile dependency
edges, registry-backed creator and license evidence, and SHA-512 distribution
artifact records. The generated SPDX file is also copied to
`Deliverables/sprint-06/sbom.spdx.json`. Third-party license texts and notices
are rendered to the frontend Legal Notices page from repository data.

```bash
scripts/sbom/regenerate_sbom.sh                 # regenerate using local tools
scripts/sbom/regenerate_sbom.sh --check          # compare against committed output
scripts/sbom/regenerate_sbom.sh --docker         # regenerate in Linux/amd64, matching CI
scripts/sbom/regenerate_sbom.sh --docker --check # verify in Linux/amd64, matching CI
scripts/sbom/regenerate_sbom.sh --refresh-registry-snapshot
```

The refresh command records version-specific registry responses and verifies
PyPI artifact bytes against `uv.lock` before snapshotting their SHA-512 hashes.
Review and commit `scripts/sbom/registry-license-snapshot.json` with the SBOM and
Legal Notices. The pull-request workflow regenerates from committed snapshots,
checks BSI TR-03183-2 v2.1.0 content requirements with SPDX's conformance checker,
and enforces the project's allowed-license policy. It does not query registries.

Use `--docker` on macOS or Windows to match GitHub Actions' Linux/amd64 package
metadata. The `--check` option verifies the SBOM, its sprint deliverable copy,
and the UI Legal Notices against regenerated output.

### Manually inventoried components

Use [`scripts/sbom/manual-components.json`](scripts/sbom/manual-components.json)
for shipped components that Syft cannot discover from the project and lockfiles.
Do not list planned or mock-only components. Each manual component must have a
stable version, PURL, SPDX license expression, evidence URL, creator contact,
distribution filename, and SHA-512 hash. For a container, pin the image by
digest and use its artifact digest as the evidence. The manifest starts empty;
the container-image workflow builds and publishes images but does not create a
second SBOM artifact.

After editing the manifest or adding license texts, regenerate in Docker mode
and commit the manifest, registry snapshot (if refreshed), SBOM, and Legal
Notices together. The container image workflow remains responsible for image
builds and provenance attestations.
