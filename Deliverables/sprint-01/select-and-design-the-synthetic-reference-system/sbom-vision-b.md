#### SBOM: Vision B (copyleft)

Project: `migration-assistant` **0.1.0** (planning version), licence `AGPL-3.0-or-later`, SBOM version 1, generated 2026-10-24, lifecycle phase *design*. Machine-readable: `sbom-vision-b.cdx.json` (CycloneDX 1.6).

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
| 11 | repowise | 0.58.0 | library | repowise-dev | `AGPL-3.0-or-later OR LicenseRef-repowise-commercial` | `pkg:pypi/repowise@0.58.0` | required | S | Second extractor: workspaces and cross-repo contracts. Disable telemetry (opt-out). Version observed on PyPI earlier in the survey |
| 12 | neo4j (Python driver) | unpinned (resolve at first lockfile) | library | Neo4j Inc. | `Apache-2.0` | `pkg:pypi/neo4j` | required | P | Loader and MCP queries |
| 13 | PyDriller | unpinned (resolve at first lockfile) | library | Davide Spadini and contributors | `Apache-2.0` | `pkg:pypi/pydriller` | required | S | Git history mining (commits, changed files, issue keys) |
| 14 | ollama | 0.40.9 | container | Ollama Inc. | `MIT` | `pkg:github/ollama/ollama@v0.40.9` | required | S | Local LLM runtime. Sources disagree on latest (0.40.5 / 0.40.9 / 0.40.10); pinned 0.40.9. Cloud features must be disabled (offline configuration) |
| 15 | LibreChat | 0.8.8 | container | LibreChat (Danny Avila and contributors) | `MIT` | `pkg:github/LibreChat-AI/LibreChat@v0.8.8` | required | V | Chat UI (release 1 Oct 2026). Verify compose services at lock time |
| 16 | FerretDB | 2.x (unpinned (resolve at first lockfile)) | container | FerretDB Inc. | `Apache-2.0` | `pkg:github/FerretDB/FerretDB` | required | P | Replaces MongoDB (SSPL) as LibreChat's document store |
| 17 | DocumentDB PostgreSQL extension | unpinned (resolve at first lockfile) | library | Microsoft | `MIT` | `pkg:github/microsoft/documentdb` | required | P | Backend required by FerretDB 2.x; licence to verify |
| 18 | PostgreSQL | 17 (minor unpinned (resolve at first lockfile)) | container | PostgreSQL Global Development Group | `PostgreSQL` | `pkg:docker/library/postgres@17` | required | P | Backend for FerretDB (both visions); in Vision A also graph + vector store |
| 19 | Neo4j Community Edition | calendar version unpinned (resolve at first lockfile) | container | Neo4j Inc. | `GPL-3.0-only` | `pkg:docker/library/neo4j` | required | P | Graph store and vector index; run unmodified as a separate server |
| 20 | code-maat | unpinned (resolve at first lockfile) | application | Adam Tornhill | `GPL-3.0-only` | `pkg:github/adamtornhill/code-maat` | optional | V | Co-change coupling, run as a separate JVM process; optional input |
| 21 | gpt-oss-20b | revision unpinned (resolve at first lockfile) | machine-learning-model | OpenAI | `Apache-2.0` | `pkg:huggingface/openai/gpt-oss-20b` | required | V | Chat model; Apache-2.0 plus the gpt-oss usage policy |
| 22 | Qwen3-Embedding-0.6B | revision unpinned (resolve at first lockfile) | machine-learning-model | Qwen team, Alibaba Cloud | `Apache-2.0` | `pkg:huggingface/Qwen/Qwen3-Embedding-0.6B` | required | P | Embedding model; check licence on the model card (Qwen licences differ per checkpoint) |
| 23 | pytest | unpinned (resolve at first lockfile) | library | pytest-dev | `MIT` | `pkg:pypi/pytest` | optional | P | Dev-only: tests (DoD) |
| 24 | cyclonedx-bom (cyclonedx-py) | unpinned (resolve at first lockfile) | application | OWASP CycloneDX | `Apache-2.0` | `pkg:pypi/cyclonedx-bom` | optional | P | Dev-only: generates the build SBOM from the lockfile |
| 25 | syft | unpinned (resolve at first lockfile) | application | Anchore | `Apache-2.0` | `pkg:github/anchore/syft` | optional | P | Dev-only: SBOM for container images |
| 26 | pip-licenses | unpinned (resolve at first lockfile) | application | raimon49 | `MIT` | `pkg:pypi/pip-licenses` | optional | P | Dev-only: licence gate in CI |
| 27 | MongoDB Community | - | container | MongoDB Inc. | `SSPL-1.0` | `pkg:docker/library/mongo` | excluded | S | Default LibreChat store; excluded (non-OSI), replaced by FerretDB |
| 28 | Meilisearch | - | container | Meili SAS | `MIT` | `pkg:docker/getmeili/meilisearch` | excluded | P | Optional LibreChat search; disabled |
| 29 | Redis | - | container | Redis Ltd. | `LicenseRef-Redis-tri-licence` | `pkg:docker/library/redis` | excluded | P | Optional LibreChat cache; disabled (if needed, use Valkey, BSD-3-Clause) |

External services (not distributed, listed for completeness):

- **Jira** (Atlassian): Jira REST API (Cloud or Data Center). External proprietary data source; not distributed; read-only service account.
- **Confluence** (Atlassian): Confluence REST API (Cloud v2 or Server/DC). External proprietary data source; not distributed; read-only service account.

Not in this SBOM until a spike adopts them (watch list): SCIP indexers (scip-java, scip-python, scip-typescript), CLDK codeanalyzer-java, Joern 4.0.x, tree-sitter (direct use), jQAssistant (Vision B, Java only).
