# Open Technical & Architectural Decisions

## 1. Purpose & Scope

This document catalogs and structures the open technical and architectural decisions for Sunset Tracker. Rather than adopting architectural choices from previous art on authority, all technology selections are treated strictly as candidate solutions to be evaluated against project-specific requirements.

### Architectural Context & Fixed Constraints
To bound the decision space, the following constraints have already been established with Wolfgang:
* **Core Objective:** Reconstruct and query the continuous state of a Strangler Fig software migration by cross-referencing four knowledge sources: (1) Legacy Code, (2) Target Code, (3) Domain Knowledge, and (4) Process & Runtime Coupling Data (tickets, shared tables, messaging routes).
* **Two-Stage Pipeline Pattern:** Deterministic structural ingestion (AST, call graphs, schemas, topology—cheap, reproducible, LLM-free) must be separated from probabilistic LLM comprehension (node summarization, semantic enrichment, Retrieval-Augmented Generation).
* **Decoupled Client-Server Topology:** Frontend and backend **must** be implemented and hosted as separate components (no single-origin monolithic coupling), enabling diverse visualization clients (chat, arc42 views, graph explorers) to consume backend APIs independently.
* **Reuse Over Custom Parsing:** Custom parsers shall not be written from scratch where mature open-source static analysis or parsing tools exist.
* **Non-Invasive Analysis:** The reference system is strictly read-only analysis input and must not be modified or migrated by the team.

### Decisions which have already been made
* **Reference System:** Wolfgangs adjusted version of the IBM Application Modernization Sample
* **MVP Strategy:** Vertical Slice - Analyze a single sub-domain/module of the reference application end-to-end (*Source → Parser → Graph → Backend → Chat UI*) to answer one concrete migration question

## 3. Evaluation Framework

To ensure evidence-based decision-making, candidate technologies are evaluated against six weighted dimensions:

1. **Functional Fit & Expressiveness:** Ability to model or extract the required artifacts (legacy/target code structures, bounded contexts, runtime database/messaging coupling, and migration states).
2. **Reuse & Integration Effort (Time-to-Slice):** Maturity of open-source ecosystems, out-of-the-box language support, and low engineering overhead.
3. **Determinism & Accuracy:** Separation of deterministic structural ground truth from probabilistic LLM inference.
4. **Queryability & Cross-Referencing:** Support for multi-hop structural traversal (e.g., transitive dependency analysis for decommissioning) alongside semantic similarity search.
5. **Operational Simplicity & Cost:** Ease of local/containerized deployment (`docker compose`), zero reliance on heavy proprietary hardware, and adherence to student project budget/token limits.
6. **Architectural Extensibility:** Compliance with the decoupled frontend/backend mandate and ability to scale from the initial vertical slice to all four knowledge sources and arc42 views.

---

## 2. Detailed Open Decisions & Evaluation Criteria

### OD-01: Code Analysis, AST & Dependency Extraction Tooling
* **Status:** Open - research is part of current sprint
* **Context & Problem Statement:**
  Both legacy code and target code must be deterministically parsed into structural entities and relationships. Wolfgang explicitly advised against writing custom parsers from scratch if existing tools suffice.
* **Evaluation Criteria:**
  * **Semantic & Type Resolution Depth:** Ability to resolve cross-file method calls, interface implementations, and framework-specific annotations without manual AST walking.
  * **Shared Pipeline Compatibility:** Ability to process both legacy and target codebases through a unified extraction pipeline.
  * **Determinism & Execution Speed:** Re-runnable in seconds/minutes inside CI or local environments without LLM invocation.
  * **Graph Export Ergonomics:** Ease of transforming extracted AST/CPG structures into the target graph database schema.

---

### OD-02: arc42 View Generation & Rendering Pipeline
* **Status:** Open - research is part of current sprint
* **Context & Problem Statement:**
  Sunset Tracker must be able to dynamically generate three **arc42** views from the knowledge graph reflecting the combined state of legacy and target systems:
  1. **Context View** (external actors, neighboring systems, interfaces)
  2. **Building Block View** (legacy modules + target services side by side, color-coded/labeled by migration status: *legacy / in development / decommissioned*)
  3. **Deployment View** (runtime topology, shared databases, messaging routes)
* **Evaluation Criteria:**
  * **Live Graph Fidelity:** Views must be derived directly from current graph state (not hand-drawn) and update automatically as the underlying system state changes.
  * **Visual Semantics:** Ability to visually distinguish migration states and highlight runtime coupling bottlenecks.
  * **Interactive Navigation:** Alignment with Wolfgang's vision of navigating through architecture views and domain objects in the decoupled frontend.

---

### OD-03: Knowledge Representation & Database Technology
* **Status:** Open
* **Context & Problem Statement:**
  Sunset Tracker requires persistent, versioned storage capable of representing rich structural topologies (code graphs, domain models, runtime coupling) alongside vector embeddings for LLM comprehension and semantic retrieval. While prior art used Neo4j or Vector Databases, neither is pre-mandated.
* **Evaluation Criteria:**
  * **Hybrid Retrieval Support (Graph + Vector):** Ability to execute vector similarity search over LLM-generated node summaries and immediately traverse k-hop structural neighborhoods in a single query or transaction.
  * **Query Language Expressiveness:** Support for variable-length path queries, subgraph extraction (for arc42 views), and aggregation queries.
  * **LLM Text-to-Query Reliability:** Quality of LLM zero/few-shot query generation.
  * **Containerization & Licensing:** Free/open-source availability and one-command local startup via Docker Compose.

---

### OD-04: Unified Graph Schema & Cross-Source Ontology
* **Status:** Open
* **Context & Problem Statement:**
  Parallel sub-teams will ingest data into a shared model. Without a strict, unified ontology, AI-assisted coding across teams will cause schema drift, preventing cross-source queries.
* **Candidates & Alternatives:**
  * **Granularity Level:**
    * *Option A (Full AST Graph):* Persist every statement/expression node in the database.
    * *Option B (Architectural & Symbol Graph):* Persist `System`, `Service/Deployable`, `Package/Module`, `Class/Interface`, `Method/Function`, `Field`, `DatabaseTable`, `MessageTopic`, `BoundedContext`, `BusinessRule`, and `WorkItem/Ticket` nodes.
  * **Coupling Aggregation:**
    * *Candidate Pattern:* Reuse and formalize the 2025 internal precedent's derived `CLASS_USES_CLASS` (and `SERVICE_COUPLED_TO_SERVICE`) weighted edges aggregated from low-level `CALLS`, `READS_TABLE`, and `PUBLISHES_TO` edges.
  * **Temporal & Migration State Modeling:**
    * Explicit state properties (`status: LEGACY | IN_DEV | MIGRATED | DECOMMISSIONED`) vs. computed state derived from graph topology (e.g., whether a `BoundedContext` has active `IMPLEMENTS` edges from target code vs. legacy code).
* **Evaluation Criteria:**
  * **Cross-Source Traceability:** Can a single traversal link `WorkItem (Jira)` $\rightarrow$ `BoundedContext (Domain)` $\rightarrow$ `LegacyClass` & `TargetClass` $\rightarrow$ `SharedDatabaseTable (Coupling)`?
  * **arc42 View Derivability:** Does the schema explicitly capture external actors/interfaces (Context View), component hierarchies and statuses (Building Block View), and runtime containers/channels (Deployment View)?
  * **Idempotency & Versioning:** Can deterministic re-ingestion update structural edges without overwriting or orphaning comprehension-stage summaries if code hashes are unchanged?

---

### OD-05: LLM Provider, Models & Comprehension/RAG Architecture
* **Status:** Open - pending response from Dirk Riehle
* **Context & Problem Statement:**
  LLMs are used in two distinct places: (1) Offline/Batch Comprehension (generating natural-language summaries of code nodes/subgraphs and linking unstructured domain concepts) and (2) answering natural-language migration questions via RAG/GraphRAG.
* **Evaluation Criteria:**
  * **Token Budget & Rate Limits:** Feasibility of running batch comprehension over thousands of AST/graph nodes within available API quotas.
  * **Structured Output & Tool-Calling Reliability:** Accuracy in generating valid JSON schemas, entity links, and graph queries.
  * **Hallucination Mitigation:** Ability to cite concrete graph nodes (file paths, class names, table names, ticket IDs) as evidence for every migration-status claim.
  * **Provider Agnosticism:** Abstraction via LiteLLM, LangChain/LangGraph, or LlamaIndex so models can be swapped seamlessly.

---

### OD-06: Chat UI vs. MCP Server
* **Status:** Open - candidate is implied by architecture diagram
* **Context & Problem Statement:**
  The system needs to be capable of natural-language querying over the combined knowledge base. While a standalone web chat interface is the baseline for demonstrations and visual views, the 2025 internal precedent demonstrated an MCP server deployed locally per developer against a shared central graph database (*"share nothing but knowledge"*), enabling developers to query migration state directly inside AI IDEs.
* **Candidate:**
  * **Dual Interface over Shared Backend Core:** Implement core retrieval and graph-query logic in the backend service, exposing it both via REST to the decoupled Web Frontend *and* via a lightweight MCP server adapter.
* **Evaluation Criteria:**
  * **Alignment with Decoupled Frontend Requirement:** Must not compromise the rich web UI required for arc42 and visual graph navigation.
  * **Architectural Reuse:** Can MCP tools and the internal Web Chat agent invoke the exact same backend query functions/tools without code duplication?
  * **Demonstration Value:** Utility for live stakeholder demos vs. developer workflow integration.

---

### OD-07: External System Integration Depth (Jira, GitLab, Confluence, DB/Messaging)
* **Status:** Open
* **Context & Problem Statement:**
  Process & Coupling Data captures user stories, ADRs, deployment status, shared database tables, and messaging routes. Wolfgang confirmed that live integrations with Jira, GitLab, or Confluence are not required and may be mocked so the team focuses on combining and reasoning over knowledge rather than building API connectors.
* **Candidates & Alternatives:**
  * **Option A (Curated Static Fixtures / Mocked MCP Server):** Represent Jira tickets, Confluence/wiki pages, and Event Storming outputs as structured JSON/YAML/Markdown datasets (or behind a mocked MCP server interface) versioned alongside the reference repository.
  * **Option B (Repository-Derived Artifacts + Mocked Process Data):** Extract runtime coupling (shared DB schemas, Docker Compose/Kubernetes configs, messaging topics, REST clients) deterministically from the reference Git repositories, while mocking only the issue tracker and wiki artifacts.
* **Evaluation Criteria:**
  * **Signal-to-Effort Ratio:** Maximizing realistic cross-referencing data (e.g., tickets referencing unimplemented or partially migrated bounded contexts) with minimal infrastructure maintenance.
  * **Reproducibility:** Ensuring any evaluator can clone and run the prototype without external SaaS credentials.
  * **Interface Realism:** Designing ingestion adapters so a mocked MCP/JSON source could be replaced by a live API client without altering the graph schema.

---

### OD-09: Domain Knowledge & Unstructured Data Ingestion
* **Status:** Open
* **Context & Problem Statement:**
  Systematic linking of Domain Knowledge (Bounded Contexts, ubiquitous language, business rules, and domain events) to both legacy code and target code.
* **Candidates & Alternatives:**
  * **Input Representation:** Structured/semi-structured domain descriptors (JSON/YAML/Markdown exports simulating Miro Event Storming boards, Context Maps, and ADRs)
  * **Code-to-Domain Linking Mechanism:**
    * *Deterministic Heuristics:* Package/namespace naming conventions, explicit annotations, or glossary keyword matching.
    * *LLM-Assisted Semantic Mapping:* Using embeddings and LLM classification during the comprehension stage to map `Class`/`Method` summaries to `BoundedContext` and `BusinessRule` nodes, scored by confidence.
    * *Hybrid (Human-in-the-Loop / Curated Seed + Automated Propagation):* Seed anchor mappings and propagate across call/dependency edges (`CLASS_USES_CLASS`).
* **Evaluation Criteria:**
  * **Bi-Directional Mapping Accuracy:** Precision and recall when answering *"Which classes implement Bounded Context X in the legacy system vs. the target system?"*
  * **Parser Reuse:** Adherence to Wolfgang's guidance to reuse existing document/wiki parsers rather than writing custom format parsers.