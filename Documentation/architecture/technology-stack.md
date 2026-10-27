# Summary of the Underlying Technology Stack

SunsetTracker is a locally reproducible prototype: every component below runs
on a single machine (Docker Compose or plain processes) and is licence-
compatible with MIT. The stack follows the SBOM Vision A (permissive) decision
record; versions marked *unpinned* are resolved at the first lockfile.

| Area | Technology | Role in the system | Status |
|---|---|---|---|
| Frontend | Vite + React + TypeScript | Web app with the AI chat interface (ChatUI) and the arc42 architecture views (ViewsUI); built and hosted separately from the backend (no single origin) | fixed |
| Backend | Python 3.12 + FastAPI + Pydantic | Application server: MCP tool facade, chat orchestration, ingestion pipeline, arc42 view generation; Pydantic validates the canonical fact schema | fixed (Python 3.12 per SBOM Vision A) |
| Chat interface | MCP SDK (`mcp`) | Tool protocol between the chat host and the backend tools (analyze, compare, history, views) | fixed |
| LLM access | OpenAI-compatible adapter | Provider-agnostic HTTP boundary; encapsulates the model call and makes local and cloud runtimes interchangeable | fixed (adapter), runtime open |
| LLM runtime | Ollama 0.40.9 (local) or a cloud provider via API key | Inference for chat answers and RAG; local runtime preferred for the offline demo, cloud possible later without code changes thanks to the adapter | local for MVP, cloud optional |
| Chat model | gpt-oss-20b (revision unpinned) | Open-weight chat model served by the local runtime | fixed (model), revision open |
| Embeddings | Qwen3-Embedding-0.6B (revision unpinned) | Optional local embeddings for retrieval-augmented answers | optional |
| Knowledge store | PostgreSQL 17 + Apache AGE 1.7.0 + pgvector | Graph store for code, domain and process facts (openCypher via `cypher()`) plus vector index for document chunks; single database for facts, jobs and manifests | fixed (Vision A) |
| Code sources | Git (local repositories / self-contained bundles) | Read-only input for the ingestion pipeline; migration steps are pinned by full commit SHA; no builds or execution of analyzed code | fixed |
| Code analysis | code-review-graph 2.3.9, SQLGlot 30.22.0, markdown-it-py | Deterministic extractors for code structure, SQL access and documentation; no LLM involved in ingestion | fixed |
| Chat persistence | LibreChat 0.8.8 + FerretDB 2.x + PostgreSQL 17 (DocumentDB) | Chat host UI and its document store; FerretDB replaces MongoDB (SSPL) to keep the stack permissively licensed | fixed |
| Testing | pytest | Unit, contract and integration tests with golden-file view tests | dev-only |
| Supply chain | cyclonedx-bom, Syft, pip-licenses | SBOM generation and licence gate in CI | dev-only |
| Orchestration | Docker Compose | Local deployment of all services; one-command reproducibility for development and demo day | fixed |
