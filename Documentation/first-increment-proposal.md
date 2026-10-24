# Sunset Tracker — First Increment Proposal

**AMOS 2026/27 · iteratec**  
**Status:** Draft for team and industry-partner discussion · **Date:** 20 October 2026

## 1. Purpose

Sunset Tracker aims to make the progress of replacing a legacy system understandable and traceable. It does not migrate source code automatically. The prototype should connect evidence from legacy code (**L**), target code (**T**), domain knowledge (**D**) and process/coupling information (**P**) to answer meaningful migration questions and support architecture views.

This document proposes a **candidate first increment**, not a confirmed MVP or an implementation decision.

## 2. Proposed first increment

**Scenario:** Select one migration snapshot from the partner's derived reference application, answer a small set of questions about its state, and show a simplified Building Block View derived from the same underlying information.

| Capability | Expected outcome | Why start here? | Existing requirements |
|---|---|---|---|
| **Q3 — What is implemented in the target?** | Identify target components and the business areas they support, distinguishing implemented code from plans. | Establishes what has actually been built before claiming migration progress. | FR-02, FR-03, FR-04, FR-07 |
| **Q4 — What is switched off or unreachable in legacy?** | Identify legacy components no longer reachable via known routes; distinguish *unreachable*, *still present*, and *removed*. | Prevents a false assumption that replaced components have already been decommissioned. | FR-01, FR-05, FR-06 |
| **Q5 — What coupling remains?** | Identify selected routes, events, calls or data dependencies across legacy and target, with evidence. | Remaining coupling explains why a seemingly migrated capability may still depend on legacy. | FR-01, FR-02, FR-05, FR-08 |
| **Simplified Building Block View** | Display major legacy/target components and confirmed relationships from the same evidence model. | Makes the answers easier to inspect and tests whether textual and visual outputs stay consistent. | FR-11, FR-13 (supported by FR-04/05) |

**Why not start with Q1 (overall migration percentage)?** A defensible overall measure requires an agreed unit of progress, weighting and completion rules. Q3–Q5 help establish the facts needed for that later decision; they do not by themselves produce a valid percentage.

## 3. Illustrative reference scenario

Wolfgang's `QUESTIONS.md` describes, at `step-07`, a catalog service alongside a remaining monolith, with proxy routing, a Kafka price-update event and duplicated product data. This provides a possible scenario for Q3–Q5.

**Important:** The original IBM README describes ten modernization steps, but Wolfgang notes that these do not map cleanly to its commit history. We must validate the stage identifiers and supporting evidence against his **derived repository** before adopting `step-07` as the test snapshot. His example answers are manually derived references, not tool-generated outputs.

## 4. Candidate acceptance criteria

1. **Stage-specific:** The demonstrator uses an identified and documented reference snapshot.
2. **Q3:** It distinguishes target functionality evident in code from functionality that is only planned or documented.
3. **Q4:** It does not equate route inaccessibility with physical removal or full decommissioning.
4. **Q5:** It identifies a small, agreed set of remaining cross-system relationships and their types.
5. **Evidence:** Important statements link to inspectable evidence (for example, file, route, configuration, table or commit).
6. **Uncertainty:** Missing or contradictory evidence is reported as uncertain rather than asserted as fact.
7. **Shared model:** The simplified Building Block View represents the same components and relationships used in the answers; changes to that data can be reflected through regeneration.

These are **proposed assessment criteria**. Required coverage, extraction automation, output format and quality thresholds remain to be agreed.

## 5. Dependencies and feasibility questions

- **Reference material:** Obtain and inspect the partner's derived variant; establish a trustworthy stage-to-evidence mapping.
- **Data availability:** Determine which facts can be extracted from code/configuration and which domain/process facts must be supplied as structured input.
- **Tooling:** Developers assess applicable open-source analysis tools, including repowise and code-review-graph, without assuming either is selected.
- **Scope control:** Decide how many components and dependencies are sufficient for an end-to-end demonstration.
- **Architecture view:** Confirm whether a simplified generated Building Block View is an acceptable first step toward the arc42 views described in the Project Sketch.

## 6. Decisions requested from the team and Wolfgang

1. Are Q3, Q4 and Q5 the right first questions, or would a different subset create more value?
2. Which snapshot(s) of the derived reference project should define the first demonstration?
3. What evidence is sufficient to describe a feature as implemented, unreachable or decommissioned?
4. Is a simplified, generated Building Block View appropriate for the first increment?
5. Which parts of the domain/process model may initially be entered manually, and which should be extracted automatically?

## 7. Relationship to ongoing work

This proposal **complements**, rather than replaces, the existing `Documentation/preliminary-functional-requirements.md` (FR-01–FR-13). It can inform the ongoing GitHub issues: **#3** success criteria, **#4** reference system, **#5** tooling research, **#6** technical decisions and **#7** arc42 rendering. No new implementation commitment is implied.

**Review status:** For discussion with both Product Owners, developers and the industry partner. Any accepted scope and criteria should be recorded in the existing backlog after review.
