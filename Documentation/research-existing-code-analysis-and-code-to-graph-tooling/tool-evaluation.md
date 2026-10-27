# Research: Existing code-analysis and code-to-graph tooling

*Issue #5 · Draft · desk research, assessment date 27 Oct 2026 · **no tool was installed, run or tested***

*Related documents: [main report](./tool-evaluation.md) · [security and license assessment](./security-assessment.md) · [experiment plan](./experiment-plan.md)*

This is the main report. It contains the candidate inventory, the criteria, the comparison matrix, the compact security and license summaries and the preliminary recommendation. Detailed vulnerability and license evidence is in the [security assessment](./security-assessment.md). The detailed experiment procedures are in the [experiment plan](./experiment-plan.md).

## 1. Purpose, scope and acceptance-criteria coverage

This document compares tools for AST extraction, dependency analysis and code-to-graph generation. It ends in a preliminary build / adopt / adapt recommendation and a justified shortlist. Security is one criterion (C11) among fourteen and is kept proportionate to the main comparison.

**Tool research is not tool testing.** Everything in §5, §6 and §9 comes from documentation, registries and advisory pages (validation level L0). No tool was installed, run or tested. The experiment in the [experiment plan](./experiment-plan.md) is a plan only.

| Acceptance criterion (Issue #5) | Where addressed |
|---|---|
| AC1 Identify tools for AST extraction, dependency analysis and code-to-graph generation | §3 inventory (24 tools), §5 profiles, §6.1 matrix |
| AC2 Treat Project Sketch tools as candidates, not predetermined solutions | §3 (all Project Sketch tools included, none presumed); §9 |
| AC3 Define common evaluation criteria | §4 (C1–C14); §6.1–§6.4; C11 detail in [security-assessment.md](./security-assessment.md#c11-full-assessment) |
| AC4 Document strengths, limitations and applicability of shortlisted tools | §5 profiles; §6.1 "Role / effort" column; §9; C11 detail in [security-assessment.md](./security-assessment.md#c11-full-assessment) |
| AC5 Consider both legacy and target code | C5 and C14 in §4; §6.3; §7; §8; tests T5 and T6 in [experiment-plan.md](./experiment-plan.md#tests-same-in-both-phases) |
| AC6 Include the industry partner's additional references | §3 (reference list included, every entry researched) |
| AC7 Preliminary build / adopt / adapt recommendation or justified shortlist | §9 |
| Additional criterion: SBOM | Design SBOM watch list in §3; supply-chain dimension (S5) in [security-assessment.md](./security-assessment.md#c11-full-assessment) |

The Definition of Done is added after week 5 and is not part of this document.

**Evidence labels**
- **[V]**: verified on an official page (URLs in §12). Every [V] fact was read through a summarising fetch tool, so small errors are possible.
- **[V-claim]**: a statement made by the project itself (benchmarks, "no telemetry", release cadence). The statement was read; its truth was not tested.
- **[P]**: stated by the industry partner (reference list or emails), not independently verified.
- **[A]**: assumption by the authors.
- **[U]**: untested capability.

"Not stated" means the checked page does not say. It does not mean "no".

## 2. Requirements the tools must serve

- Analyse legacy and target code with the same mechanism: classes/modules, calls, data access and control flow (FR-01, FR-02) [V].
- Coupling through shared tables, messaging routes and direct calls (FR-05, FR-08) [V].
- Tool survey and build / adopt / adapt recommendation in weeks 1–2; Project Sketch tools are candidates only [V].
- **Use existing AST parsers; do not build a new parser** [P]. "Build" here can mean our own normalisation, loader and evidence layer, not a parser.
- Every answer cites source evidence (file, commit or document); say "I don't know" when the data does not support an answer [P].
- Ingestion is deterministic, with no LLM. LLM comprehension is a separate stage [P, recommendation].
- Local-first demonstration with `docker compose up` [P, recommendation].
- **Building and running the example stages.** The industry partner's email states: "Building and running the stages is now possible and the developers probably should try it, as proposed at the kickoff." [P] This is partner-provided guidance, not a project requirement.
- **Design contract (separate branch).** It proposes adapting code-review-graph (D4) and proposes that analysed repositories are not built or executed (D10). Both are design proposals, not finalised project-wide requirements, and D10 differs from the partner guidance above. **This document does not rely on D4 or D10.** Whether D10 stays, changes or is dropped is an open question (§11).
- The language of the final reference system is not confirmed (Issue #4). Language fit is judged here only against the two reference systems described in the [experiment plan](./experiment-plan.md#reference-systems).

## 3. Candidate inventory (24 unique tools)

| Origin | Tools |
|---|---|
| Project Sketch | TangleGuard, Sourcegraph Cody, Driver, bloop, Joern, CodeQL, Tree-sitter extractors, ANTLR |
| Team shortlist (all also in the industry partner reference list) | code-maat, CodeMR, repowise, Understand-Anything, AiDex, cocoindex-code, code-review-graph |
| Industry partner reference list only | CodeCharta, tokei, Sonargraph, CodeScene, sqlgpt-parser |
| Design SBOM watch list only | SCIP indexers, CLDK codeanalyzer-java, jQAssistant, SQLGlot |

Categories are the authors' classification [A]. **TangleGuard:** official URL **unverified** (a guessed GitHub URL returned 404, a web search found nothing, tangleguard.com showed unrelated content). It is not evaluated beyond its Project Sketch description.

## 4. Evaluation criteria

| ID | Criterion | AC |
|---|---|---|
| C1 | Category and what it extracts | 1 |
| C2 | Output: graph model, storage, export formats | 1 |
| C3 | **Direct graph access and export** without the tool's own interface (top priority) | 1, 7 |
| C4 | Languages and fit with the reference systems | 5 |
| C5 | Same mechanism for legacy and target code | 5 |
| C6 | Coupling signals: tables, messaging, cross-repository contracts | 4 |
| C7 | License and commercial terms (separate from C11) | 3, 7 |
| C8 | Local/offline operation, telemetry, code leaving the machine, footprint on the host | 3 |
| C9 | Maturity and maintenance | 3 |
| C10 | Integration effort and fit with the rule to use existing AST parsers; whether the tool needs the analysed project to be built | 7 |
| C11 | Open-source security and vulnerability risk (§6.2 summary; full assessment in [security-assessment.md](./security-assessment.md#c11-full-assessment); separate from C7) | 3, 4, 7 |
| C12 | **Evidence traceability**: file, line range and a way to link to a commit or tag for each fact; unsupported facts reported as unknown | 3, 4 |
| C13 | **Package, class and method extraction** as separate, queryable entities with parent/child relations; deployment information represented or handled elsewhere | 1, 4 |
| C14 | **Compatibility with legacy and target repositories**: one configuration across repositories and stages; identical schema for comparing stage snapshots | 5 |

## 5. Tool profiles

### 5.1 Code-graph tools

**code-review-graph** (MIT, copyright 2026) [V]
- Tree-sitter structural map; 20+ languages including SQL and Terraform; custom languages via `languages.toml`.
- Storage: one SQLite file (`.code-review-graph/graph.db`, WAL mode), with a documented schema: base tables `nodes` and `edges` plus a `metadata` table. Exports to JSON, GraphML and Neo4j Cypher through `visualize`. 30 MCP tools.
- Node kinds documented: File, Class, Function, Test, Type, Endpoint, Scheduler, ConfigProperty, Event. Edge kinds include CALLS, IMPORTS_FROM, INHERITS, IMPLEMENTS, CONTAINS, TESTED_BY, REFERENCES, DEPENDS_ON and INJECTS.
- **Messaging and web edges are Spring-specific enrichment** [V]: `CONSUMES` (`@KafkaListener`/`@KafkaHandler` method to `kafka:<topic>`), `PRODUCES` (Kafka producer to `kafka:<topic>`), `PUBLISHES`, `HANDLES`, `Endpoint` and `Event` nodes (Spring request mappings, WebFlux routes, Spring application events). No SQL-table edge and no general HTTP-call edge is stated. Whether any of these are populated for Quarkus or other non-Spring code: **[U]**.
- Direct read-only SQL on `graph.db` is plausible [A]. The documentation does not explicitly endorse it. **[U]**
- "No telemetry, cloud embeddings opt-in" is the project's statement [V-claim].
- The `install` command edits editor configuration and appends a git pre-commit hook; it also writes `.claude/skills/` [V].
- v2.3.9 published 18 Sep 2026; Python 3.10+; at least 34 releases listed between 26 Feb and 10 Jun 2026, plus v2.3.9.
- Stated limitations: conservative impact analysis with false positives; flow detection strongest for Python and PHP; recall of 1.0 described as "circular"; co-change mode returned nothing in its own evaluation. The ~63x token-reduction figure is the author's benchmark against a whole-corpus baseline that the author calls an upper bound [V-claim].

**repowise** (AGPL-3.0; commercial licensing offered) [V]
- AST call graph for 28 languages, import graph, heritage edges, SQL/dbt lineage, git co-change [V-claim]. Cross-repository HTTP/gRPC/topic/OpenAPI contract matching with confidence levels [V-claim].
- CLI, dashboard, MCP (10 default tools).
- Storage: `.repowise/wiki.db`, described in the user guide as holding "pages, symbols, graph, git data, health scores" [V]. The storage engine is not stated (SQLite is plausible [A]). Direct read access to the graph: **[U]**.
- Export: the CLI reference documents `repowise export` with formats markdown, html, json and **structurizr** (one DSL file) [V]. No raw-graph export format is stated. Whether the json export contains graph edges: **[U]**. Output of any export: **[U]**.
- The CLI reference also documents `packages export` (declared packages and import sites as CycloneDX 1.6 JSON; "not an SBOM" per the page) [V]. Relevant to C13 and the SBOM criterion; **[U]**.
- Graph and health features need no LLM; LLM optional; opt-out telemetry (the opt-out mechanism was not verified); dashboard needs Node 20+.
- `init` writes to `~/.claude/settings.json` and the Claude Desktop config and can install a git post-commit hook. `--no-editor-setup` writes only `.repowise/` and also skips the post-commit hook [V].
- v0.59.0 published 25 Oct 2026; Python 3.11+; earliest visible release 28 Mar 2026.
- Suggested as a starting point in the industry partner reference list [P].

**Understand-Anything** (MIT) [V]: Tree-sitter extraction plus LLM agents; output `.ua/knowledge-graph.json`; graph building needs an LLM (local Ollama possible); languages and telemetry not stated. LLM at ingestion conflicts with deterministic ingestion [P/A].
**AiDex** (MIT) [V]: Tree-sitter, 14 languages, SQLite index of identifiers, methods, classes, types; MCP; call/dependency edges not stated. Probably a symbol index [A].
**cocoindex-code** (Apache-2.0) [V]: AST-based semantic and structural search, ~37 languages, LMDB, local or cloud embeddings, opt-out telemetry; graph not stated. Search layer [A].

### 5.2 Analysis infrastructure

- **Joern** (Apache-2.0) [V]: code property graphs, Scala query shell; frontends for C/C++, Java, JavaScript, Python, Kotlin and binaries; JDK 21; export formats not stated; latest release v4.0.665 on 23 Oct 2026.
- **CodeQL** [V]: queries repository MIT; CLI licensed separately; the page says analysing closed-source code needs a commercial license.
- **Tree-sitter** (MIT) [V]: parser library; call-graph extraction not stated.
- **ANTLR** (BSD-3) [V]: parser generator, 10 target languages. The Project Sketch cautions that its ANTLR-based concept outline was LLM-generated.
- **SCIP indexers** (Apache-2.0) [V]: index protocol; indexers for Java/Scala/Kotlin, TypeScript/JavaScript, Python, C/C++, C#, Rust, Ruby, PHP, Dart.
- **CLDK codeanalyzer-java** (Apache-2.0) [V]: Java only; symbol table and call graph; Neo4j emit; invokes the project's Maven/Gradle wrapper to compile, so it needs a project build. That is outside the static-only scope of EXP-1 and conflicts with D10 as proposed [A]; 7 stars.
- **jQAssistant** (GPL-3.0) [V]: page gives little detail.
- **TangleGuard:** unverified.

### 5.3 SQL parsing

- **SQLGlot** (MIT) [V]: 30+ dialects; SQL to AST; no runtime dependencies declared on PyPI; v30.25.0 published 26 Oct 2026.
- **sqlgpt-parser** (Apache-2.0) [V]: MySQL, OceanBase and ODPS only; 36 stars; no releases.

### 5.4 Metrics, history, visualisation

- **code-maat** (GPL-3.0) [V]: version-control mining incl. change coupling.
- **CodeCharta** (BSD-3) [V]: visualisation incl. import dependency view; Code Maat and tokei importers.
- **tokei** (MIT / Apache-2.0) [V]: line statistics, 150+ languages.
- **CodeScene** (commercial) [V]: free for open-source projects, trial offered.
- **CodeMR** [V]: Java, C#, Scala, Kotlin, C++; no license or pricing on the page.
- **Sonargraph** (commercial) [V]: from EUR 120/month for Java.

### 5.5 Commercial AI assistants

- **Sourcegraph Cody** [V]: public repository archived 1 Aug 2025 as a read-only snapshot.
- **bloop** [V]: archived 2 Jan 2025.
- **Driver** [V]: commercial SaaS context compiler (MCP, REST); licensing and pricing not stated.

## 6. Comparison matrix

### 6.1 Main comparison (C1–C10)

| Tool | Category | Extracts (C1) | Output / direct access (C2–C3) | Languages (C4) | Legacy + target (C5) | Coupling (C6) | License (C7) | Local / telemetry / footprint (C8) | Maturity (C9) | Role / effort (C10) |
|---|---|---|---|---|---|---|---|---|---|---|
| code-review-graph | Code graph | Structure, calls, impact [V] | SQLite with documented schema; JSON/GraphML/Cypher exports; MCP. Direct SQL plausible [A], untested [U] | 20+ incl. SQL, Terraform [V] | Where language supported [A] | Spring and Spring-Kafka enrichment edges documented [V]; no SQL-table or HTTP-call edge kinds stated; coverage of non-Spring code untested [U] | MIT [V] | Local; "no telemetry" [V-claim]; `install` edits editor configs and git hooks [V] | v2.3.9 18 Sep 2026; at least 34 releases 26 Feb–10 Jun 2026 [V] | Leading candidate for **adapt**, pending experiment; effort [U] |
| repowise | Code graph | Calls, imports, heritage, SQL lineage, co-change [V-claim] | `.repowise/wiki.db` holds a graph per user guide [V]; export formats markdown/html/json/structurizr documented [V]; no raw-graph export stated; outputs untested [U] | 28 AST languages [V-claim] | Where supported [A] | Cross-repository HTTP/gRPC/topic/OpenAPI contracts [V-claim]; untested [U] | AGPL-3.0; commercial option; PyPI says "or later" [V] | Local; opt-out telemetry [V]; `init` edits user and editor configs and can install a git hook; `--no-editor-setup` avoids both [V] | v0.59.0 25 Oct 2026 [V] | **Comparator**; license open (Issue #30) |
| Understand-Anything | Code graph | Imports, defs, calls + LLM summaries [V] | JSON file [V] | Not stated | [A] | Not stated | MIT [V] | LLM to build; telemetry not stated [V] | 88.4k stars [V] | Not preferred for ingestion: LLM at ingestion |
| AiDex | Symbol index | Identifiers, methods, classes, types [V] | SQLite; MCP [V] | 14 [V] | [A] | Not stated | MIT [V] | Local [V] | 46 stars [V] | Not preferred: no stated graph [A] |
| cocoindex-code | Semantic search | AST search [V] | LMDB; CLI/MCP [V] | ~37 [V] | [A] | Not stated | Apache-2.0 [V] | Local or cloud; opt-out telemetry [V] | 3.0k stars [V] | Search layer only [A] |
| Joern | Infrastructure | Code property graph [V] | Scala shell; export not stated [V] | C/C++, Java, JS, Python, Kotlin, binaries [V] | Where supported [A] | Not stated | Apache-2.0 [V] | Local; JDK 21 [V] | v4.0.665 23 Oct 2026; 3.6k stars [V] | **Fallback** [A] |
| CodeQL | Infrastructure | Query analysis [V] | Export not stated | 9 language folders in queries repository [V] | Commercial license needed for closed source [V] | Not stated | Repo MIT; CLI separate [V] | Not stated | n/a | License risk [A] |
| Tree-sitter | Parser library | Syntax trees [V] | Library API [V] | Via grammars [V] | [A] | No | MIT [V] | Local [V] | Crate 0.27.1 8 Oct 2026; 27.3k stars [V] | **Parser baseline** [A] |
| ANTLR | Parser generator | Parse trees [V] | Library API [V] | 10 targets [V] | [A] | No | BSD-3 [V] | Local [V] | 19.0k stars [V] | Parser option; grammars would have to be written or sourced [A] |
| SCIP indexers | Index protocol | Definitions/references [V] | SCIP index [V] | ~10 families [V] | Where supported [A] | Not stated | Apache-2.0 [V] | Not stated | 846 stars [V] | Possible precision layer [A] |
| CLDK codeanalyzer-java | Analyzer | Symbol table, call graph [V] | analysis.json, Neo4j emit [V] | Java only [V] | Java only | Not stated | Apache-2.0 [V] | Needs project build [V] | 7 stars [V] | Needs a build; outside EXP-1 static-only scope [A] |
| jQAssistant | Analyzer | Not stated | Not stated | Not stated | Unknown | Not stated | GPL-3.0 [V] | Not stated | 299 stars [V] | Insufficient evidence |
| TangleGuard | Unverified | — | — | — | — | — | — | — | — | Not evaluated |
| SQLGlot | SQL parser | SQL AST [V] | Python API [V] | 30+ dialects [V] | SQL [A] | Table-level [A][U] | MIT [V] | Local; no runtime deps [V] | v30.25.0 26 Oct 2026; 9.7k stars [V] | **Complement** [A] |
| sqlgpt-parser | SQL parser | SQL AST [V] | Python API [V] | 3 dialects [V] | Narrow | No | Apache-2.0 [V] | Local [V] | 36 stars, no releases [V] | Weak fit [A] |
| code-maat | History | Change coupling [V] | Tool output only [A] | VCS-based | [A] | Co-change | GPL-3.0 [V] | Local [V] | 2.6k stars [V] | Supporting only |
| CodeCharta | Visualisation | Metrics, import deps [V] | Visual / CSV [V] | 19 parsers [V] | [A] | Imports | BSD-3 [V] | Local; no telemetry [V-claim] | 559 stars [V] | Supporting only |
| tokei | Metrics | Line counts [V] | JSON/YAML/CBOR [V] | 150+ [V] | [A] | No | MIT / Apache-2.0 [V] | Local [V] | 15.0k stars [V] | Supporting only |
| CodeScene | Commercial | Hotspots, health [V] | No API on page [V] | 25+ [V] | [A] | Not stated | Commercial [V] | Cloud or on-prem [V] | n/a | Not deeper |
| CodeMR | Commercial | Metrics, coupling [V] | Reports [V] | 5 [V] | Limited | Class coupling | Not stated [V] | IDE-integrated [V] | n/a | License unclear |
| Sonargraph | Commercial | Not detailed | Not stated | 6 [V] | Limited | Not stated | Commercial [V] | Not stated | n/a | Cost barrier |
| Sourcegraph Cody | Assistant | n/a | n/a | n/a | n/a | n/a | Apache-2.0 on archived snapshot [V] | n/a | Archived 1 Aug 2025 [V] | Not applicable |
| bloop | Assistant | Code search [V] | n/a | 10+ [V] | n/a | n/a | Apache-2.0 [V] | n/a | Archived 2 Jan 2025 [V] | Not applicable |
| Driver | Commercial SaaS | Call chains, dependency maps [V] | MCP/REST [V] | "all" [V] | [A] | Not stated | Not stated [V] | SaaS; not offline [V] | n/a | Not open source as far as shown |

### 6.2 Security and vulnerability risk summary (C11), 27 Oct 2026

Rating terms: **Concern found**, **Mitigated at declared floor**, **No issues found (limited evidence)**, **Positive practice documented**, **No published security policy found**, **Unknown**. None means "secure". This table is a compact summary. The six-dimension table (S1 advisories, S2 dependency risk, S3 security policy, S4 maintenance, S5 supply chain, S6 operational), the method, the limits and the advisory evidence are in the [security assessment](./security-assessment.md#c11-full-assessment). No overall score is given, because none is defined.

| Tool and version | Key finding |
|---|---|
| **code-review-graph 2.3.9** | **Potential dependency-resolution risk.** Declared ranges permit versions with known advisories (mcp: 5 High; anyio: 1 Critical, 1 High; fastmcp: 1 Moderate). Fixed in current releases; actual resolution and exposure unverified. Advisories on the tool itself: no issues found (limited evidence). Supply chain and operational risk: Unknown. |
| **repowise 0.59.0** | **Mitigated at declared floor** for all checked Critical/High (litellm, GitPython, cryptography, mcp). Range-level exposure to Moderate advisories (litellm, jinja2). 53 core direct dependencies, most unchecked, so **Unknown** overall. Security policy published, but says fixes go only to the "0.54.x" line while latest is 0.59.0. Advisories on the tool itself: no issues found (limited evidence). |
| **Joern v4.0.665** | No issues found on the tool itself (limited evidence). No published security policy found. Dependencies Unknown. |
| **Tree-sitter (crate 0.27.1)** | No issues found on the tool itself (limited evidence); NVD/GHSA hits concern another product. No published security policy found. Dependencies Unknown (runtime stated dependency-free). |
| **SQLGlot 30.25.0** | No issues found on the tool itself (limited evidence). No runtime dependencies declared on PyPI. No published security policy found. |
| code-maat, CodeCharta, tokei | No published repository advisories. No published security policy found. Other dimensions Unknown. |

Commercial and closed tools are not assessable from public sources. Tools not listed were not assessed for C11.

### 6.3 Criteria C12–C14 (documentation status only)

No tool was tested, so every cell states what the documentation shows. "Unknown" means not assessed in this pass.

| Tool | C12 Evidence traceability | C13 Package / class / method extraction | C14 Legacy + target repository compatibility |
|---|---|---|---|
| code-review-graph | Schema documented [V]. Whether each fact carries file, line range and a commit link: **[U]** | Tree-sitter structure extraction; File, Class, Function and Type nodes and CONTAINS edges documented [V]. Packages as a separate entity: **[U]** | One configuration per repository [A]. Multi-repository stage comparison: **[U]** |
| repowise | Wiki/graph with claimed source links [V-claim]. Per-fact file and line: **[U]** | Calls, imports and heritage edges [V-claim]. Packages as entities: **[U]**. `packages export` documented [V], untested [U] | Claims multi-repository workspaces and contract matching [V-claim]. Stage comparison: **[U]** |
| Joern | Code property graph carries source positions [A]; not verified | Java and JavaScript frontends [V]. Package model: **[U]** | Per-repository import [A] |
| Tree-sitter | Byte ranges and positions per node [A]; library only | Syntax nodes only; semantic model must be built by us [A] | Language-dependent [A] |
| SQLGlot | SQL AST positions: **[U]** | Not applicable (SQL) | SQL dialect coverage only [V] |
| SCIP indexers | Occurrence ranges in the protocol [A]; not verified | Definitions and references [V] | Per-language indexers [V] |
| Others | Unknown | Unknown | Unknown |

### 6.4 License summary (C7, separate from C11)

| License group | Tools |
|---|---|
| MIT / Apache-2.0 / BSD-3 | code-review-graph, Understand-Anything, AiDex, cocoindex-code, Joern, Tree-sitter, ANTLR, SCIP, CLDK, SQLGlot, sqlgpt-parser, CodeCharta, tokei |
| Copyleft | repowise (AGPL-3.0; commercial licensing offered), code-maat (GPL-3.0), jQAssistant (GPL-3.0) |
| Commercial / restricted | CodeQL CLI, CodeScene, Sonargraph, Driver |
| Not stated | CodeMR |

repowise: the README and the `LICENSE` file say AGPL-3.0, the PyPI metadata says "AGPL-3.0-or-later", and the README offers commercial licensing. License detail, input for Issue #30 and the licenses of the reference systems are in the [security and license assessment](./security-assessment.md#license-detail). This is not legal advice.

## 7. Validation Strategy

### 7.1 Tool research vs tool testing, and what each level supports

| Level | What it is | Status | What it can support |
|---|---|---|---|
| L0 | Documentation research: official pages, schemas, registries, advisories | Done (this document) | The Issue #5 **preliminary build / adopt / adapt recommendation or justified shortlist** (AC7), together with its stated uncertainty |
| L1 | Preliminary experiment on the public IBM repository ([EXP-1](./experiment-plan.md), Phase A) | Proposed, not run, needs approval | Confirm or revise the shortlist; eliminate weak candidates; refine the test method |
| L2 | Project-specific validation on the industry partner's staged repositories (EXP-1, Phase B) | Blocked: access pending | Project-specific validation before the team commits to implementation |

The preliminary recommendation in §9 rests on L0 evidence and is valid on that basis. L1 and L2 are validation steps. If their results contradict it, the shortlist is revised.

The two reference systems behind L1 and L2 (a public IBM sample and the industry partner's private staged example) are described in the [experiment plan](./experiment-plan.md#reference-systems).

### 7.2 Validation rules (summary)

Preliminary results are labelled "preliminary, public stand-in"; project-specific validation needs the partner's staged system and separate approval; private content and derived outputs stay out of the public repository; tools never receive credentials; EXP-1 is static analysis only; every result records repository, tag or directory, tool version, date and command. The full rules are in the [experiment plan](./experiment-plan.md#validation-rules).

## 8. Legacy and target code (AC5)

- Tree-sitter-based tools apply the same mechanism to any repository whose language they support [A].
- The comparison unit is a stage pair. In the staged system it is `step-05` → `step-06`. In the public repository it is the directory subsets described in the [experiment plan](./experiment-plan.md#reference-systems).
- Messaging routes, shared tables and deployment configuration are documented as Spring-specific schema entries for code-review-graph [V] and as contract matching and SQL lineage for repowise [V-claim]. None of this has been tested on either reference system.
- AST and code facts are distinguished from documents and deployment files, which may need other ingestion methods. Each tool is recorded as "AST only" or "AST plus other" in the tests.
- repowise declares `sqlglot>=26,<28` for version 0.59.0, while the design SBOM pins SQLGlot 30.22.0 [V]. The SBOM also lists repowise 0.58.0; whether that version has the same range is **[U]**. Installing both in one environment may fail [A].

## 9. Preliminary recommendation

This recommendation is a **justified shortlist based on documented capabilities (L0)**. It does not rely on the D4 or D10 design proposals. It is preliminary and no tool has been tested.

| Role | Tool | Stance | Documented basis |
|---|---|---|---|
| Leading candidate | code-review-graph | **Adapt** (leading candidate, to be confirmed by EXP-1) | MIT [V]; documented SQLite schema and JSON/GraphML/Cypher export [V]; Tree-sitter parsing, so no parser is built [V]; small direct dependency set; Spring and Spring-Kafka enrichment edges documented [V], but no SQL-table or HTTP-call edges stated and non-Spring coverage untested [U]; footprint of `install` must be controlled [V]; dependency ranges permit older versions with advisories, so pin and lock [A] |
| Comparator | repowise | **Evaluate in parallel** | Broader documented edge types and cross-repository contract matching [V-claim], which suits a multi-repository staged system; graph stored in `wiki.db` and Structurizr/JSON/markdown/HTML exports documented [V], with no raw-graph export stated and outputs untested [U]; AGPL (Issue #30), telemetry, 53 core dependencies and the SQLGlot range conflict need clearance [V] |
| Fallback | Joern | Keep as option | Documented frontends and query shell [V]; export, fit and effort untested [U] |
| Parser baseline | Tree-sitter | Build option if adapting fails | Parser only; we would write the normalisation, evidence and loader layers ourselves [V][A] |
| SQL | SQLGlot | Candidate for table-level coupling | SQL AST, no runtime dependencies [V]; lineage not documented [V] |
| Supporting | code-maat, CodeCharta, tokei | Complementary | [V] |
| Not recommended now | Cody, bloop (archived [V]); Driver, Sonargraph, CodeScene (commercial [V]); CLDK (needs a build [V]); Understand-Anything (LLM at ingestion [V]); AiDex, cocoindex-code (no stated graph [V]); jQAssistant (insufficient evidence) | See §5 |

**Conclusion.** The preliminary stance is adapt: reuse an existing Tree-sitter-based analyser and write our own normalisation, evidence tagging and graph loading, as the partner's rule requires [P]. Build means only the layers around the parser. Adopt is not recommended without a graph-access test, and repowise remains the alternative. A lack of published advisories is not treated as proof of security.

**What would change this.** A failed EXP-1 Phase A or B for the leading candidate; a license ruling against the AGPL option; or the discovery that required language coverage or coupling extraction (including Quarkus messaging and SQL tables) is missing.

## 10. Validation experiment EXP-1 (summary; plan only, nothing executed)

The full procedures, safety conditions, tests, provisional thresholds and decision rule are in the [experiment plan](./experiment-plan.md).

**Goal.** Decide which of code-review-graph 2.3.9 and repowise 0.59.0, if either, can extract packages, classes, dependencies and evidence for legacy and target code, with direct access to the resulting graph. All thresholds below are **provisional [A]** and need team review. Nothing in this section has been run.

**Priorities, in order:** (1) direct graph access and export; (2) AST and dependency extraction; (3) applicability to legacy and target code; (4) coupling extraction.

**Phases (each step needs explicit approval)**
- **Phase A (L1):** the public IBM repository, with a pinned snapshot recorded at the start. Before/after pairs are formed from directory subsets (see [Reference systems](./experiment-plan.md#reference-systems)). Ground truth is derived by hand from directory listings and a seeded sample of 25 files, reviewed by a second person.
- **Phase B (L2):** the industry partner's staged system once access is granted. Index `step-05` and `step-06` per repository from manual checkouts of each tag. Ground truth from the diff between the tags, the partner's step and question documents, and a second reviewer.
- **Optional controlled test:** a small synthetic fixture (about 10–15 Java files per side) with known classes, calls, imports, a shared SQL table, a Kafka produce/consume pair and an HTTP route. It is written in a scratch directory and is used only if a known-answer check is needed.

**Outcomes.** Each tool is rated suitable, partially suitable or not suitable against provisional thresholds that need team review. License (C7) and security (C11) remain separate gates. Phase A can eliminate a candidate or revise the shortlist; Phase B provides project-specific validation. The Issue #5 recommendation in §9 does not wait for either. See the [decision rule](./experiment-plan.md#decision-rule).

## 11. Open questions and untested items

| # | Open question | Detail in |
|---|---|---|
| 1 | Hands-on test of direct graph access for code-review-graph and repowise; needs approval to install. | [experiment plan](./experiment-plan.md#tests-same-in-both-phases) |
| 2 | Access to the staged repositories; their languages, layout and build systems. | [experiment plan](./experiment-plan.md#reference-systems) |
| 3 | Whether the stage numbering of the public repository corresponds to the staged system's. | [experiment plan](./experiment-plan.md#reference-systems) |
| 4 | Whether commit history or a manual checkout can provide the stage pair in each repository. | [experiment plan](./experiment-plan.md#phases-each-step-needs-explicit-approval) |
| 5 | TangleGuard's official source. | §3 |
| 6 | Whether an AGPL tool may be used (Issue #30). | [security assessment](./security-assessment.md#license-detail) |
| 7 | Full lockfile-level dependency scan of the chosen tool; transitive dependencies. | [security assessment](./security-assessment.md#method-and-limits) |
| 8 | repowise and SQLGlot version-range conflict (0.59.0 verified; 0.58.0 untested). | §8; [security assessment, Appendix A.2](./security-assessment.md#a2-repowise-0590) |
| 9 | Alignment of criteria with Issue #6. | §4 |
| 10 | Whether derived data from private repositories may be committed to the public repository (assumed no). | [experiment plan](./experiment-plan.md#validation-rules) |
| 11 | Correction of the "step-07" reference in the first-increment proposal draft. | [experiment plan](./experiment-plan.md#reference-systems) |
| 12 | Whether D10 (no builds or execution of analysed repositories) stays, changes or is dropped, given the partner's guidance that building and running the stages is possible and encouraged. | §2; [experiment plan](./experiment-plan.md#safety-conditions) |
| 13 | Whether code-review-graph's Spring-specific messaging edges work on Quarkus code, and whether either tool finds SQL-table coupling. | §5.1, §6.1; [experiment plan](./experiment-plan.md#tests-same-in-both-phases) |
| 14 | Which mechanism disables repowise telemetry. | §5.1; [experiment plan](./experiment-plan.md#safety-conditions) |

## 12. Sources (accessed 27 Oct 2026)

Sources for security advisories, dependency checks and security policies are listed in the [security assessment](./security-assessment.md#sources-accessed-27-oct-2026).

**Reference systems**
- https://github.com/IBM/application-modernization-javaee-quarkus (public)
- Industry partner's private staged example: location shared privately by the partner; access pending; not accessed; not linked
- Industry partner emails and reference list (private; not linked)
- Team arc42 rendering research, branch `research-arc42-view-rendering-options`

**code-review-graph**
- https://github.com/tirth8205/code-review-graph
- https://github.com/tirth8205/code-review-graph/blob/main/docs/schema.md (schema; link verified)
- https://github.com/tirth8205/code-review-graph/tree/main/docs (commands, usage and index pages)
- https://raw.githubusercontent.com/tirth8205/code-review-graph/main/LICENSE
- https://pypi.org/project/code-review-graph/
- https://pypi.org/pypi/code-review-graph/json

**repowise**
- https://github.com/repowise-dev/repowise
- https://github.com/repowise-dev/repowise/blob/main/README.md
- https://github.com/repowise-dev/repowise/blob/main/docs/start/USER_GUIDE.md (link verified)
- https://github.com/repowise-dev/repowise/blob/main/docs/reference/CLI_REFERENCE.md (link verified; the page is long and its telemetry section was not visible)
- https://github.com/repowise-dev/repowise/blob/main/LICENSE (link verified; plain GNU AGPL v3 text)
- https://pypi.org/project/repowise/
- https://pypi.org/pypi/repowise/json

**Joern**
- https://github.com/joernio/joern
- https://api.github.com/repos/joernio/joern/releases/latest

**Tree-sitter**
- https://github.com/tree-sitter/tree-sitter
- https://crates.io/api/v1/crates/tree-sitter

**SQLGlot**
- https://github.com/tobymao/sqlglot
- https://pypi.org/pypi/sqlglot/json

**Other candidates**
- https://github.com/Egonex-AI/Understand-Anything
- https://github.com/CSCSoftware/AiDex
- https://github.com/cocoindex-io/cocoindex-code
- https://github.com/github/codeql
- https://github.com/antlr/antlr4
- https://github.com/sourcegraph/scip
- https://github.com/codellm-devkit/codeanalyzer-java
- https://github.com/jqassistant/jqassistant
- https://github.com/eosphoros-ai/sqlgpt-parser
- https://github.com/adamtornhill/code-maat and /security
- https://github.com/MaibornWolff/codecharta and /security
- https://github.com/XAMPPRocky/tokei and /security
- https://codescene.com/product/how-it-works
- https://www.codemr.co.uk/features/
- https://www.hello2morrow.com/products/sonargraph/single_licenses
- https://github.com/sourcegraph/cody-public-snapshot
- https://github.com/bloopai/bloop
- https://driver.ai

**TangleGuard:** official URL unverified; none listed.

**Project documents:** Project Sketch (PDF), `Documentation/preliminary-functional-requirements.md`, kickoff document, industry partner reference list and emails, design contract and SBOM on the reference-system branch.
