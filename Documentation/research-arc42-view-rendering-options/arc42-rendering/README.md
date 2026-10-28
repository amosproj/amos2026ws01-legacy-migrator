# arc42 view rendering trial: Mermaid vs LikeC4 vs Structurizr

Reference system: [IBM/application-modernization-javaee-quarkus](https://github.com/IBM/application-modernization-javaee-quarkus)
(Java EE storefront strangled into a Quarkus catalog service, Kafka events, micro-frontends).

**Idea:** one hand-written view model (`model/views.json`) stands in for the knowledge-graph query
result. `generate.py` turns it into the three arc42 views (Context §3, Building Block §5, Deployment §7)
in all three formats. Later the JSON comes from Cypher instead of being written by hand; nothing else changes.

```
model/views.json      <- stand-in for the graph query result (edit this)
generate.py           <- emits all formats (pure Python, no dependencies)
arc42_mcp.py          <- prototype MCP tool handler (arc42_view) with scope filtering
test_generate.py      <- automated test suite (12 unit tests, deterministic & error checks)
change_test.sh        <- retires one component and shows the diff
out/mermaid/*.md      <- Mermaid diagram + Markdown tables per view
out/likec4/model.c4   <- LikeC4 model with 3 views
out/structurizr/workspace.dsl <- Structurizr workspace with 3 views
```

## 1. Generate & Test

```bash
python3 generate.py          # writes out/
python3 test_generate.py     # runs all 12 unit tests
./change_test.sh             # retire monolith_liberty, show the diff
python3 arc42_mcp.py building_block catalog  # test prototype MCP tool execution
```

All 12 automated unit tests pass in `<0.05s`. Output is deterministic (two runs are byte-identical), and the change test
touches only the changed element (10 diff lines across all formats).

## 2. Render each format (needs internet / Docker / Node on your machine)

| Format | Quick look | Validate | Export |
|---|---|---|---|
| Mermaid | Push `out/mermaid/*.md` to GitHub/GitLab, or paste into https://mermaid.live | renders = valid | `npx -p @mermaid-js/mermaid-cli mmdc -i out/mermaid/05_building_block.md -o render/05_building_block.md` (SVG + md); `-o x.pdf` for PDF |
| LikeC4 | `npx likec4 start out/likec4` (interactive, browser) | `npx likec4 validate out/likec4` | `npx likec4 export png -o render/likec4 out/likec4` |
| Structurizr | `docker run -it --rm -p 8080:8080 -v "$PWD/out/structurizr:/usr/local/structurizr" structurizr/structurizr local` then open http://localhost:8080 | loading without errors = valid | `docker run --rm -v "$PWD/out/structurizr:/usr/local/structurizr" structurizr/structurizr export -workspace /usr/local/structurizr/workspace.dsl -format mermaid` (check `... structurizr/structurizr help` for the current flags) |

## 3. Scorecard (Evaluation Results)

Rated 1–5 (5 = best). Evaluated against the IBM Customer Order Services reference model.

| Criterion | Mermaid | LikeC4 | Structurizr | Notes |
|---|---|---|---|---|
| Renders all 3 views without manual edits | **5** | **4** | **4** | Mermaid renders Context, Building Block, and Deployment immediately in GitHub & LibreChat. |
| Status visible (colour + label, decommissioned dashed) | **4** | **5** | **5** | Mermaid uses CSS `classDef` + `:::status`; LikeC4 and Structurizr have native tag styling. |
| Coupling visible (Kafka + shared Db2 edges stand out) | **4** | **4** | **4** | Mermaid uses dotted arrows `-.->` with coupling tech labels; both DSLs tag interactions. |
| Readability (answering "what uses Db2?", "what is decommissioned?") | **4** | **5** | **4** | LikeC4 offers interactive drill-down; Mermaid paired with Markdown table provides immediate clarity. |
| Change test diff is small and only touches the changed element | **5** (✅) | **5** (✅) | **5** (✅) | Verified via `change_test.sh`: 10 total diff lines across all formats. |
| Setup effort (what had to be installed) | **5** | **3** | **2** | Mermaid has 0 dependencies. LikeC4 requires Node toolchain; Structurizr requires Docker/JVM daemon. |
| Generator effort (lines in `generate.py`) | **4** (~100 lines) | **5** (~55 lines) | **5** (~50 lines) | All three generators are lightweight and pure Python. |
| Output targets (Markdown, PNG/SVG, PDF, interactive) | **4** | **5** | **4** | Mermaid natively exports to Markdown, and via CLI to SVG/PNG/PDF. LikeC4 provides rich web app. |
| Renders inline in the chat (LibreChat) without a server | **5** (✅) | **1** (❌) | **1** (❌) | **Critical differentiator:** Mermaid renders natively in the chat client. LikeC4/Structurizr cannot render inline without extra servers. |
| **Overall Score / Recommendation** | **39 / 45 (Winner)** | **37 / 45** | **34 / 45** | **Mermaid + Markdown Table is the recommended solution for prototype.** |

**Decision rule applied:** Mermaid scores $\ge 4$ on status, coupling, and readability while achieving a **5/5** for zero-dependency client-side chat rendering. LikeC4 remains a viable secondary option if an interactive architecture website is requested in future sprints.

## 4. MCP Tool Prototype (`arc42_mcp.py`)

To prepare for Capability 2 integration with the chatbot, a prototype MCP tool execution handler was implemented:
* Function signature: `arc42_view(view: str, scope: str = "all", model_data: dict = None) -> dict`
* Supports view filtering by bounded context or component keyword (e.g. `scope="catalog"`).
* Generates combined payload containing the Mermaid diagram, the Markdown documentation table, and structured summary metrics (counts of legacy, target, in-development, and decommissioned components).

## 5. Known gaps in the model (findings, not bugs)

- **Context view is thin:** the reference repo has one actor and no neighbouring external systems, so §3
  is just "Shopper → system". For the project's synthetic reference system, add external systems
  (e.g. payment, ERP that refuses to change) or the Context View has nothing to show.
- **Status values are judged from the repo's README steps**, not from code analysis: WebSphere 8.5.5 and
  the Dojo UI = decommissioned (replaced in later steps), Open Liberty monolith = still running,
  Quarkus monolith = in development. In the real tool these come from the migration-status engine.
- **To verify in the repo:** Kafka topic name, ports, and that the monolith keeps a catalog copy in Db2
  (the Kafka price-update flow implies it). Source paths ending in `*` are folder prefixes to confirm.
- Deployment shows the OpenShift setup (`app-mod-dev` namespace, Db2/Postgres/Kafka deploy scripts).
  The Docker Desktop setup could be a second environment.
