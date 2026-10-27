# EXP-1: proposed comparison experiment (plan only)

*Issue #5 · Draft · **plan only: nothing in this document has been executed, installed, cloned or run** · all thresholds are provisional*

*Related documents: [main report](./tool-evaluation.md) · [security and licence assessment](./security-assessment.md) · [experiment plan](./experiment-plan.md)*

This document holds the detailed experiment procedures. The research, the candidate comparison and the preliminary recommendation are in the [main report](./tool-evaluation.md). The reference systems are described in [§7 of the main report](./tool-evaluation.md#7-reference-systems-and-validation-strategy). Validation levels L0, L1 and L2 are defined in [§7.1](./tool-evaluation.md#71-tool-research-vs-tool-testing-and-what-each-level-supports). Security and licence gates are in the [security assessment](./security-assessment.md).

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

## Phases (each step needs explicit approval)
- **Phase A (L1):** the public IBM repository, with a pinned snapshot recorded at the start. Before/after pairs are formed from directory subsets ([§7.4 of the main report](./tool-evaluation.md#74-the-two-reference-systems-are-not-identical)). Ground truth is derived by hand from directory listings and a seeded sample of 25 files, reviewed by a second person.
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

Suitable: passes T1 and T8, meets the thresholds on T2–T6, and reaches at least partial on T7. Partially suitable: misses at most two of T2–T7. Not suitable: anything worse. Licence (C7) and security (C11) remain separate gates. If neither tool is at least partially suitable, the fallback is a Tree-sitter-based loader or a Joern trial. Phase A results can eliminate a candidate or revise the shortlist, and Phase B results provide project-specific validation. The Issue #5 recommendation does not wait for either.

## Validation rules

1. Preliminary results from the public repository are labelled "preliminary, public stand-in".
2. Project-specific validation uses the staged system once access is granted and is approved separately.
3. No private content, and no output containing private source, goes into the public repository without permission.
4. Tools never receive credentials.
5. EXP-1 is static analysis only. Building or running the stages, which the partner now permits, is a separate activity that needs its own approval and is not part of EXP-1.
6. Every result states repository, tag or directory, tool version, date and command.

## Open items owned by this document

These are items 1, 4, 10, 12, 13 and 14 of the [open questions in the main report](./tool-evaluation.md#11-open-questions-and-untested-items): the hands-on tests, the stage pair in each repository, the rule for derived data, the status of D10, the Quarkus and SQL-table coupling questions, and the repowise telemetry opt-out.

## Sources

Full source list: [§12 of the main report](./tool-evaluation.md#12-sources-accessed-27-oct-2026). Sources the tests rely on most:

- https://github.com/IBM/application-modernization-javaee-quarkus (public)
- https://github.com/tirth8205/code-review-graph/blob/main/docs/schema.md (schema; link verified)
- https://github.com/repowise-dev/repowise/blob/main/docs/start/USER_GUIDE.md (link verified)
- https://github.com/repowise-dev/repowise/blob/main/docs/reference/CLI_REFERENCE.md (link verified; the page is long and its telemetry section was not visible)
- Industry partner's private staged example and emails: not linked; access pending; not accessed
