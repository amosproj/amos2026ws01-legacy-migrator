# EXP-1: proposed comparison experiment (plan only)

*Issue #5 · Draft · **plan only: nothing in this document has been executed, installed, cloned or run** · all thresholds are provisional*

*Related documents: [main report](./tool-evaluation.md) · [security and license assessment](./security-assessment.md) · [experiment plan](./experiment-plan.md)*

This document holds the detailed experiment procedures. The research, the candidate comparison and the preliminary recommendation are in the [main report](./tool-evaluation.md). The reference systems are described in [Reference systems](#reference-systems) below. Validation levels L0, L1 and L2 are defined in [§7.1](./tool-evaluation.md#71-tool-research-vs-tool-testing-and-what-each-level-supports). Security and license gates are in the [security assessment](./security-assessment.md).

**Evidence labels**
- **[V]**: verified on an official page (URLs in the Sources section below and §12 of the main report). Every [V] fact was read through a summarising fetch tool, so small errors are possible.
- **[V-claim]**: a statement made by the project itself (benchmarks, "no telemetry", release cadence). The statement was read; its truth was not tested.
- **[P]**: stated by the industry partner (reference list or emails), not independently verified.
- **[A]**: assumption by the authors.
- **[U]**: untested capability.

"Not stated" means the checked page does not say. It does not mean "no".

## Goal and priorities

**Goal.** Decide which of code-review-graph 2.3.9 and repowise 0.59.0, if either, can extract packages, classes, dependencies and evidence for legacy and target code, with direct access to the resulting graph. All thresholds in this document are **provisional [A]** and need team review. Nothing in this document has been run.

**Priorities, in order:** (1) direct graph access and export; (2) AST and dependency extraction; (3) applicability to legacy and target code; (4) coupling extraction.

## Reference systems

Two reference systems are used. They are representative examples, not necessarily an actual legacy-to-target migration history, and they are **not identical**. The public IBM sample is used for preliminary tests (Phase A, L1). The industry partner's private staged example is the priority for project-specific validation (Phase B, L2). The levels are defined in [§7.1 of the main report](./tool-evaluation.md#71-tool-research-vs-tool-testing-and-what-each-level-supports).

### Public IBM sample (Phase A)

Repository: `IBM/application-modernization-javaee-quarkus` [V, with the summariser caveat]. It is also the reference system in the team's arc42 rendering research.

- Description: "Application Modernization Sample: From Java EE (2010) to Cloud-Native (2021)". The README calls the legacy application a Java EE 6 application from 2008.
- Apache-2.0 license. 322 commits on the default branch at the time of reading. The page indicates the repository is **archived (read-only)**; the archive date is not recorded here because it has not been independently verified.
- Languages and build tools: **not stated on the page [U]**.
- Technologies named: Db2 (legacy monolith), Postgres (catalog service), Kafka (events), Quarkus, Open Liberty, WebSphere, OpenShift.
- Ten modernization steps in the README. Step 5 is the Open Liberty monolith. Step 6 is the strangled Quarkus catalog service plus the remaining monolith, with Kafka messaging.
- Structure: the steps are **directories in one snapshot**, not tags or separate repositories. Examples are `monolith-websphere-855`, `monolith-open-liberty`, `monolith-quarkus-synch`, `service-catalog-quarkus-synch`, `service-catalog-quarkus-reactive`, `proxy`, three frontends (Dojo, single-spa/Vue), `db2`, and deployment scripts.

Why it is useful for the preliminary tests:
1. It contains a Java EE monolith, a strangled catalog service, Kafka and two databases. The same patterns are in the staged system [P].
2. It is public and Apache-2.0, so no confidentiality limits apply and results can be shared in the team repository.
3. It covers Java in several frameworks, JavaScript/Vue frontends, Db2 SQL and YAML/shell scripts. That tests language coverage (C4) and the split between AST and non-AST ingestion.
4. It is archived, so the snapshot is stable during an experiment.

Testing limits:
- A before/after pair has to be formed from directory subsets, not from a git diff. Ground truth must be built by hand. Whether the commit history supports historical checkouts is **[U]**.
- The arc42 trial's view model is hand-written, so it provides no extraction ground truth.
- Because the example uses Quarkus, Spring-specific enrichment in some tools ([§5.1 of the main report](./tool-evaluation.md#51-code-graph-tools)) may not apply [A].

### Industry partner's staged example (Phase B)

The industry partner's private staged example consists of one umbrella repository and eight component repositories, with stages tagged `step-00` to `step-10`. Its location was shared privately with the team. **Access is pending and the contents have not been inspected.** All statements below come from the partner's emails and are [P].

- It is derived from the IBM application, with added explanations, and is split into separate repositories as migrated components are developed.
- Supporting documents: stage descriptions, derivation notes, a corrected question set (the earlier version is superseded), license notices, and fix scripts. The fix scripts address unpinned container images and a proprietary Db2 driver, which matters for builds, probably not for static analysis [A].
- Source code is described as unchanged and Apache-2.0; the partner's additions are also Apache-2.0. The license notices have not been read.
- **Minimum acceptance step: `step-05` → `step-06`, the extraction of the catalog service.** The system must explain what is newly covered (documents, classes, packages, deployments). `step-05` deliberately contains no catalog service, even though the original source history already had one.
- Building and running the stages is now possible, and the partner states developers probably should try it (quoted in [§2 of the main report](./tool-evaluation.md#2-requirements-the-tools-must-serve)).
- Demo acceptance criteria: every answer cites file, commit or document; existing AST parsers are used; the system answers "I don't know" when data is missing; the acceptance run is documented. Six named questions are rated by the partner as correct, partly correct or wrong. Stretch goals (arc42 views, further steps, scheduled runs) are not required.

### The two reference systems are not identical

| Aspect | Public IBM sample | Industry partner's staged example |
|---|---|---|
| Access | Public | Private, pending |
| Structure | One snapshot, steps as directories [V] | Nine repositories, stages as tags [P] |
| Stage definition | README steps 1–10 [V] | `step-00`–`step-10`; `step-05` has no catalog service although the original history did [P] |
| Added material | None | Explanations, fix scripts, acceptance questions [P] |
| Contents verified | Page only | Not inspected |

- The stage numbering of the two systems may not correspond (IBM steps run 1–10, the partner's 00–10). A pair such as "Open Liberty monolith alone" versus "monolith plus `service-catalog-quarkus-synch` and `proxy`" is a plausible analogue of the acceptance pair. This is an assumption [A], not a verified mapping.
- The first-increment proposal draft placed the catalog extraction at "step-07". The partner's email says `step-05` → `step-06`. The email is treated as authoritative, and the proposal should be corrected.

## Phases (each step needs explicit approval)
- **Phase A (L1):** the public IBM repository, with a pinned snapshot recorded at the start. Before/after pairs are formed from directory subsets (see [Reference systems](#reference-systems)). Ground truth is derived by hand from directory listings and a seeded sample of 25 files, reviewed by a second person.
- **Phase B (L2):** the industry partner's staged system once access is granted. Index `step-05` and `step-06` per repository from manual checkouts of each tag. Ground truth from the diff between the tags, the partner's step and question documents, and a second reviewer.
- **Optional controlled test:** a small synthetic fixture (about 10–15 Java files per side) with known classes, calls, imports, a shared SQL table, a Kafka produce/consume pair and an HTTP route. It is written in a scratch directory and is used only if a known-answer check is needed.

## Safety conditions
- Disposable clones; WSL2 or a container; one virtualenv per tool (their dependency ranges may conflict).
- Never run `code-review-graph install`. Use `build`, `status` and `visualize` only.
- For repowise, use `init --no-editor-setup` (writes only `.repowise/` and skips the post-commit hook [V]). Disable telemetry through the project's documented opt-out; the mechanism has not been verified.
- No LLM keys, no cloud embeddings, network blocked during analysis.
- EXP-1 is static analysis: analysed code is not built or run, because static analysis needs no build [A]. Building and running the stages is allowed by the partner but is a separate activity needing its own approval. The partner's helper and fix scripts are not part of EXP-1.
- Credentials for private access are never given to the tools and are revoked afterwards.
- Index directories and outputs from private repositories stay local and uncommitted.
- Record `pip freeze`, OS, dates and all commands.

## Tests (same in both phases)

| ID | Test | Method |
|---|---|---|
| T1 | **Direct graph access and export** | code-review-graph: read-only queries on `graph.db`, plus JSON, GraphML and Cypher exports. repowise: inspect `.repowise/wiki.db`, run `export` in each documented format, check whether any export contains graph edges. Retrieve nodes and edges (name, kind, file, line) by script. |
| T2 | **Package, class and method extraction** | Index the stages or subsets separately; compare against ground truth. |
| T3 | **Dependency, import and call extraction** | Compare with hand-checked samples (and the fixture, if used). |
| T4 | **Evidence traceability** | For 25 sampled facts, check file, line range and a linkable commit or tag; check how unsupported facts are reported. |
| T5 | **Legacy and target applicability** | Same configuration on both sides; compare recall per side and the schema. |
| T6 | **Stage-pair difference** | Compare the graphs of the two snapshots; does the catalog addition appear as new? |
| T7 | **Coupling extraction** | Kafka routes, shared database tables, direct HTTP calls, with file and line. Note whether Spring-specific edges fire on non-Spring (Quarkus) code. |
| T8 | **Determinism and operations** | Two identical builds compared; incremental update; offline run; no writes outside project directories; telemetry confirmed off. |

## Expected outputs

Results tables per tool, repository and snapshot; logs; query and export outputs (kept locally for private data); ground-truth files; the sample list and seed; pinned versions; a replayable command log.

## Provisional pass/fail criteria [A]

| Test | Pass | Partial | Fail |
|---|---|---|---|
| T1 | Facts retrievable by script with file and line; identical across two runs | Only via UI or MCP | Not retrievable |
| T2 | Class and package precision and recall ≥ 0.90 | Within 0.10 below | Below |
| T3 | Import recall ≥ 0.85; call precision and recall ≥ 0.80 | 0.65–0.84 imports; 0.60–0.79 calls | Below |
| T4 | ≥ 90% of sampled facts have file and line, and a commit or tag can be linked | 70–89% | Below 70%, or unsupported facts presented as known |
| T5 | Same schema; recall on both sides within 10 points | Documented difference | Unexplained gap |
| T6 | The catalog addition is visible as new | Needs manual steps | Not visible |
| T7 | At least two of three link types found with evidence | One of three | None |
| T8 | Identical builds; offline; no unexpected writes; telemetry off | Minor | Unexpected writes or network use |

## Decision rule

Suitable: passes T1 and T8, meets the thresholds on T2–T6, and reaches at least partial on T7. Partially suitable: misses at most two of T2–T7. Not suitable: anything worse. License (C7) and security (C11) remain separate gates. If neither tool is at least partially suitable, the fallback is a Tree-sitter-based loader or a Joern trial. Phase A results can eliminate a candidate or revise the shortlist, and Phase B results provide project-specific validation. The Issue #5 recommendation does not wait for either.

## Validation rules

1. Preliminary results from the public repository are labelled "preliminary, public stand-in".
2. Project-specific validation uses the staged system once access is granted and is approved separately.
3. No private content, and no output containing private source, goes into the public repository without permission.
4. Tools never receive credentials.
5. EXP-1 is static analysis only. Building or running the stages, which the partner now permits, is a separate activity that needs its own approval and is not part of EXP-1.
6. Every result states repository, tag or directory, tool version, date and command.

## Open items owned by this document

These are items 1, 2, 3, 4, 10, 11, 12, 13 and 14 of the [open questions in the main report](./tool-evaluation.md#11-open-questions-and-untested-items): the hands-on tests, access to the staged repositories, the correspondence of stage numbering, the stage pair in each repository, the rule for derived data, the correction of the "step-07" reference, the status of D10, the Quarkus and SQL-table coupling questions, and the repowise telemetry opt-out.

## Sources

Full source list: [§12 of the main report](./tool-evaluation.md#12-sources-accessed-27-oct-2026). Sources the tests rely on most:

- https://github.com/IBM/application-modernization-javaee-quarkus (public)
- https://github.com/tirth8205/code-review-graph/blob/main/docs/schema.md (schema; link verified)
- https://github.com/repowise-dev/repowise/blob/main/docs/start/USER_GUIDE.md (link verified)
- https://github.com/repowise-dev/repowise/blob/main/docs/reference/CLI_REFERENCE.md (link verified; the page is long and its telemetry section was not visible)
- Industry partner's private staged example and emails: not linked; access pending; not accessed
