# Explanation of the Diagrams and Architectural Choices

## Runtime Architecture (page 1)

The runtime architecture is organized in three tiers. The **presentation
tier** contains the two frontend features: the chat interface (ChatUI) and the
arc42 architecture views (ViewsUI). The **domain tier** holds the backend
logic: the MCP tool facade (McpFacade) exposes the backend capabilities as
tools, the chat orchestrator (ChatOrchestrator) combines retrieval with model
calls, the ingestion pipeline (IngestionPipeline) analyses pinned migration
steps, and the view generator (ViewGenerator) projects the knowledge graph
into arc42 views. The **persistence tier** contains the knowledge graph
(GraphStore) and the local Git depot (GitDepot) with the pinned repository
states.

Two boundaries are deliberate. First, the frontend and the backend are built
and hosted **separately** (no single origin), because the frontend offers more
than the chat interface — the arc42 views are a first-class feature. Second,
the **LLM server is external**: it may run locally (Ollama) or in the cloud
via an API key. The backend talks to it only through the provider-agnostic,
OpenAI-compatible LlmAdapter, which is a module of the backend — not a
separate runtime component. This keeps the model runtime exchangeable without
touching the orchestration logic.

## Objects at Runtime (page 2)

The second diagram shows one concrete instance per tier, following the lecture
template. The web client runs one `:WebApp` instance (Vite + React + TS,
containing ChatUI and ViewsUI). The application service column contains two
separate servers: the `:BackendServer` (Python + FastAPI, hosting McpFacade,
ChatOrchestrator, LlmAdapter, IngestionPipeline and ViewGenerator as modules)
and the `:LlmServer` (local, e.g. Ollama — or a cloud service). The
persistence service column contains the `:GraphStore` (PostgreSQL 17 with
Apache AGE) and the `:GitDepot` with the local repositories. The LLM server is
grouped under "application service" because it provides inference, but it
remains a separate server from the backend.

## Code Organization (page 3)

The code organization maps the same components onto three horizontal layers.
The **application layer** contains our own code in two separate repositories:
`frontend/` (ChatUI, ViewsUI) and `backend/` (api, chat, ingest, views,
adapters). The **framework layer** contains the libraries we use and
configure: React + Vite, FastAPI + Pydantic, the MCP SDK, the PostgreSQL/AGE
driver and the OpenAI-compatible client. The **platform layer** contains the
system software we only operate: Node.js, Python 3.12, the PostgreSQL server,
Git, the LLM runtime and Docker Compose. The LLM runtime sits in the platform
layer because we run or consume it, but never modify its code.

## Key choices and their rationale

| Choice | Rationale |
|---|---|
| Separate frontend and backend hosting | Industry partner requirement; the frontend is more than a chat shell (arc42 views). No single origin. |
| MCP as the chat-to-backend interface | A typed tool boundary keeps the model from inventing backend behavior; the chat host executes tool calls, the backend owns the logic. |
| OpenAI-compatible LLM adapter | Encapsulation and exchangeability: local Ollama for the offline demo, a cloud provider via API key later — no changes to orchestration code. |
| PostgreSQL 17 + Apache AGE as knowledge store | One permissively licensed database serves graph queries (openCypher), vector search (pgvector) and job/manifest storage; matches SBOM Vision A. |
| Deterministic ingestion without LLM | Facts (code structure, SQL access, docs) are extracted deterministically and validated with Pydantic; the LLM only explains, it does not invent facts. Evidence-based answers are the core requirement. |
| Pinned migration steps (full commit SHAs) | Every question about migration status is answered against a reproducible snapshot; Git bundles make the reference system shareable and offline-capable. |
| Local-first, MIT-compatible stack | Demo day must work offline (Ollama); every dependency is permissively licensed (FerretDB replaces MongoDB/SSPL). |
