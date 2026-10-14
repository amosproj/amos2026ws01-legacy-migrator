# Preliminary Functional Requirements

**AI-Assisted Legacy Migration Knowledge Base**
*AMOS · Winter Semester 2026/27 · iteratec*

> [!NOTE]
> This document presents requirements derived from the Industry Partner's initial Project Sketch. They are subject to review with the project team and iteratec; no priorities or implementation commitments are implied.

| Project information | Details |
| :--- | :--- |
| **Project** | AMOS-27 Legacy Migrator |
| **Industry Partner** | iteratec |
| **Document version** | 0.1 |
| **Status** | Preliminary draft |
| **Source** | *AMOS-27 Project 1 — iteratec — Know Legacy Detail Information*, Project Sketch, sections 1–7, as summarized in *AMOS Legacy Migrator — Requirements and Project Document Summary*, 14 October 2026 |

**Contents:** [Purpose](#1-purpose) · [Functional requirements](#2-functional-requirements) · [Scope and constraints](#3-scope-and-constraints) · [Open questions](#4-open-questions) · [Proposed follow-up](#5-proposed-follow-up)

---

## 1. Purpose

This document identifies the functional capabilities described in iteratec's initial Project Sketch. Requirements are grouped by function and assigned reference IDs to support review and subsequent backlog refinement.

## 2. Functional requirements

### 2.1 Code analysis

| ID | Functional requirement |
| :--- | :--- |
| **FR-01** | Analyze the **legacy codebase** and capture structural elements and relationships, including classes or modules, calls, and data access. |
| **FR-02** | Analyze the **implemented target codebase** using the same AST/graph-based mechanism, representing code that actually exists rather than only planned functionality. |

---

### 2.2 Domain knowledge and traceability

| ID | Functional requirement |
| :--- | :--- |
| **FR-03** | Integrate **domain knowledge** in a structured model, including bounded contexts, ubiquitous language, business rules, and events. |
| **FR-04** | Link domain knowledge to relevant **legacy and target code elements** to identify which implementation supports a given bounded context. |

---

### 2.3 Migration process and system coupling

| ID | Functional requirement |
| :--- | :--- |
| **FR-05** | Integrate **process and coupling information**, including user stories or tickets, architecture decisions, deployment status, shared tables, messaging routes, and direct calls. |

---

### 2.4 Natural-language migration queries

| ID | Functional requirement |
| :--- | :--- |
| **FR-06** | Answer, in **natural language**, which parts of the legacy system have already been switched off or decommissioned. |
| **FR-07** | Explain, in **natural language**, what is being developed in the target system and which bounded contexts are implemented by existing target code. |
| **FR-08** | Explain which legacy and target components remain coupled through **shared tables, messaging routes, or direct calls**. |
| **FR-09** | Suggest plausible **next decommissioning candidates** using migration status and remaining dependencies as evidence; this is decision support, not automatic decommissioning. |

---

### 2.5 Generated architecture documentation

| ID | Functional requirement |
| :--- | :--- |
| **FR-10** | Generate an **arc42 Context View** showing external actors, neighboring systems, and interfaces. |
| **FR-11** | Generate an **arc42 Building Block View** showing remaining legacy components alongside target components; status coloring or labeling is a desirable enhancement. |
| **FR-12** | Generate an **arc42 Deployment View** showing infrastructure, execution locations, and runtime connections. |
| **FR-13** | Derive all three architecture views **from the shared knowledge graph** and support regeneration when its underlying data changes. |

---

## 3. Scope and constraints

The Project Sketch also establishes the following boundaries:


- Demonstrate the core migration questions using **at least one worked example domain**; the exact reference system and MVP coverage remain undecided.
- Use a **synthetic reference system**, without confidential client code or data.
- Develop a **fresh prototype**, rather than extending the Industry Partner's earlier internal implementation.
- Observed runtime behavior collected through logs or traces is outside the initial three-month prototype scope.
- Focus on **migration tracking and generated arc42 views**, rather than a general-purpose project assistant.
- Automatic code migration or automatic decommissioning is **not** a stated capability.
- Technology choices, architecture output formats, update frequency, and measurable quality thresholds remain open.

---

## 4. Open questions

The following issues require clarification before prioritization and acceptance criteria can be established.

| Topic | Question to resolve |
| :--- | :--- |
| **MVP scope** | Which requirements form the minimum end-to-end demonstration, and which can be deferred? |
| **Reference scenario** | Which synthetic legacy/target pair and migration history will be used? |
| **Acceptance criteria** | What observable behavior and example answers will demonstrate successful fulfillment of each selected requirement? |
| **Data sources** | Which process and coupling inputs will be mocked, provided as static data, or integrated directly? |
| **Interaction and outputs** | What query interface and architecture-view output formats are expected? |
| **Quality and refresh** | How will answer accuracy, traceability, and regeneration after data changes be evaluated? |

---

## 5. Proposed follow-up

The Product Owners should review the requirements with the team and iteratec, identify the intended MVP scope, and prepare backlog items with acceptance criteria. Developers should assess technical feasibility and dependencies before implementation estimates are agreed.

---

*Source: iteratec, AMOS-27 Project 1 — Know Legacy Detail Information, Project Sketch, sections 1–7. Requirement identifiers and formulations are an initial extraction, not quotations or an approved specification.*
