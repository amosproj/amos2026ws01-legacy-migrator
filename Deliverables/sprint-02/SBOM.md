#### SBOM: Vision A (permissive)

Project: `migration-assistant` **0.1.0** (planning version), licence `Apache-2.0`, SBOM version 1, generated 2026-10-24, lifecycle phase *design*. Machine-readable: `sbom-vision-a.cdx.json` (CycloneDX 1.6).

| # | Component | Version | Type | Supplier | Licence (SPDX) | Package URL (purl) | Scope | Ev. | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | python | 3.12 | container | Python Software Foundation | `PSF-2.0` | `pkg:docker/library/python@3.12-slim` | required | P | Base image for pipeline and MCP server; code-review-graph needs Python >= 3.10 |
| 2 | git | unpinned (resolve at first lockfile) | application | Git project | `GPL-2.0-only` | `pkg:deb/debian/git` | required | P | Host/base-image tool for git worktree checkouts; invoked as a separate process, not linked or modified |
| 3 | code-review-graph | 2.3.9 | library | Tirth (tirth8205) | `MIT` | `pkg:pypi/code-review-graph@2.3.9` | required | V | Primary structural extractor (PyPI release 18 Sep 2026) |
| 4 | sqlglot | 30.22.0 | library | Toby Mao and contributors | `MIT` | `pkg:pypi/sqlglot@30.22.0` | required | S | SQL read/write extraction (release 9 Oct 2026) |
| 5 | atlassian-python-api | 5.0.5 | library | atlassian-api community (not Atlassian) | `Apache-2.0` | `pkg:pypi/atlassian-python-api@5.0.5` | required | S | Jira and Confluence connectors (Cloud and Server/DC); licence V, version from docs (S) |
| 6 | markdown-it-py | unpinned (resolve at first lockfile) | library | Executable Books | `MIT` | `pkg:pypi/markdown-it-py` | required | P | Markdown parsing (headings, links, code spans) |
| 7 | markdownify | unpinned (resolve at first lockfile) | library | Matthew Tretter and contributors | `MIT` | `pkg:pypi/markdownify` | required | P | Confluence storage format (XHTML) to markdown |
| 8 | mcp | unpinned (resolve at first lockfile) | library | Model Context Protocol project | `MIT` | `pkg:pypi/mcp` | required | P | MCP tool server SDK |
| 9 | pydantic | unpinned (resolve at first lockfile) | library | Pydantic Services Inc. and contributors | `MIT` | `pkg:pypi/pydantic` | required | P | Canonical fact schema and validation |
| 10 | ollama (Python client) | unpinned (resolve at first lockfile) | library | Ollama Inc. | `MIT` | `pkg:pypi/ollama` | required | P | Chat and embedding calls to the local model runtime |
| 11 | asyncpg | unpinned (resolve at first lockfile) | library | MagicStack Inc. | `Apache-2.0` | `pkg:pypi/asyncpg` | required | P | PostgreSQL driver; chosen instead of psycopg (LGPL-3.0) to keep Vision A permissive. AGE is queried via SQL cypher() calls, not the psycopg-based AGE driver |
| 12 | ollama | 0.40.9 | container | Ollama Inc. | `MIT` | `pkg:github/ollama/ollama@v0.40.9` | required | S | Local LLM runtime. Sources disagree on latest (0.40.5 / 0.40.9 / 0.40.10); pinned 0.40.9. Cloud features must be disabled (offline configuration) |
| 13 | LibreChat | 0.8.8 | container | LibreChat (Danny Avila and contributors) | `MIT` | `pkg:github/LibreChat-AI/LibreChat@v0.8.8` | required | V | Chat UI (release 1 Oct 2026). Verify compose services at lock time |
| 14 | FerretDB | 2.x (unpinned (resolve at first lockfile)) | container | FerretDB Inc. | `Apache-2.0` | `pkg:github/FerretDB/FerretDB` | required | P | Replaces MongoDB (SSPL) as LibreChat's document store |
| 15 | DocumentDB PostgreSQL extension | unpinned (resolve at first lockfile) | library | Microsoft | `MIT` | `pkg:github/microsoft/documentdb` | required | P | Backend required by FerretDB 2.x; licence to verify |
| 16 | PostgreSQL | 17 (minor unpinned (resolve at first lockfile)) | container | PostgreSQL Global Development Group | `PostgreSQL` | `pkg:docker/library/postgres@17` | required | P | Backend for FerretDB (both visions); in Vision A also graph + vector store |
| 17 | Apache AGE | 1.7.0 (PG17) | library | Apache Software Foundation | `Apache-2.0` | `pkg:github/apache/age@PG17%2Fv1.7.0-rc0` | required | V | Graph extension (openCypher) for PostgreSQL 17 |
| 18 | pgvector | unpinned (resolve at first lockfile) | library | Andrew Kane and contributors | `PostgreSQL` | `pkg:github/pgvector/pgvector` | required | P | Vector index in PostgreSQL |
| 19 | gpt-oss-20b | revision unpinned (resolve at first lockfile) | machine-learning-model | OpenAI | `Apache-2.0` | `pkg:huggingface/openai/gpt-oss-20b` | required | V | Chat model; Apache-2.0 plus the gpt-oss usage policy |
| 20 | Qwen3-Embedding-0.6B | revision unpinned (resolve at first lockfile) | machine-learning-model | Qwen team, Alibaba Cloud | `Apache-2.0` | `pkg:huggingface/Qwen/Qwen3-Embedding-0.6B` | required | P | Embedding model; check licence on the model card (Qwen licences differ per checkpoint) |
| 21 | pytest | unpinned (resolve at first lockfile) | library | pytest-dev | `MIT` | `pkg:pypi/pytest` | optional | P | Dev-only: tests (DoD) |
| 22 | cyclonedx-bom (cyclonedx-py) | unpinned (resolve at first lockfile) | application | OWASP CycloneDX | `Apache-2.0` | `pkg:pypi/cyclonedx-bom` | optional | P | Dev-only: generates the build SBOM from the lockfile |
| 23 | syft | unpinned (resolve at first lockfile) | application | Anchore | `Apache-2.0` | `pkg:github/anchore/syft` | optional | P | Dev-only: SBOM for container images |
| 24 | pip-licenses | unpinned (resolve at first lockfile) | application | raimon49 | `MIT` | `pkg:pypi/pip-licenses` | optional | P | Dev-only: licence gate in CI |
| 25 | MongoDB Community | - | container | MongoDB Inc. | `SSPL-1.0` | `pkg:docker/library/mongo` | excluded | S | Default LibreChat store; excluded (non-OSI), replaced by FerretDB |
| 26 | Meilisearch | - | container | Meili SAS | `MIT` | `pkg:docker/getmeili/meilisearch` | excluded | P | Optional LibreChat search; disabled |
| 27 | Redis | - | container | Redis Ltd. | `LicenseRef-Redis-tri-licence` | `pkg:docker/library/redis` | excluded | P | Optional LibreChat cache; disabled (if needed, use Valkey, BSD-3-Clause) |

External services (not distributed, listed for completeness):

- **Jira** (Atlassian): Jira REST API (Cloud or Data Center). External proprietary data source; not distributed; read-only service account.
- **Confluence** (Atlassian): Confluence REST API (Cloud v2 or Server/DC). External proprietary data source; not distributed; read-only service account.

Not in this SBOM until a spike adopts them (watch list): SCIP indexers (scip-java, scip-python, scip-typescript), CLDK codeanalyzer-java, Joern 4.0.x, tree-sitter (direct use), jQAssistant (Vision B, Java only).
