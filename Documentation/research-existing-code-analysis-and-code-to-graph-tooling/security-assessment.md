# Security and license assessment (C11 and C7)

*Issue #5 · Draft · desk research, assessment date 27 Oct 2026 · **no scanner was run and no tool was installed, run or tested***

*Related documents: [main report](./tool-evaluation.md) · [security and license assessment](./security-assessment.md) · [experiment plan](./experiment-plan.md)*

This document holds the detailed vulnerability and license evidence behind the compact summaries in the [main report](./tool-evaluation.md#62-security-and-vulnerability-risk-summary-c11-27-oct-2026) and [license summary](./tool-evaluation.md#64-license-summary-c7-separate-from-c11). The preliminary recommendation is in [§9 of the main report](./tool-evaluation.md#9-preliminary-recommendation). License compliance (C7) and security risk (C11) are separate criteria. Security and license results are gates in the [experiment plan](./experiment-plan.md#decision-rule); they are not part of its technical score.

**Evidence labels**
- **[V]**: verified on an official page (URLs in the Sources section below and §12 of the main report). Every [V] fact was read through a summarising fetch tool, so small errors are possible.
- **[V-claim]**: a statement made by the project itself (benchmarks, "no telemetry", release cadence). The statement was read; its truth was not tested.
- **[P]**: stated by the industry partner (reference list or emails), not independently verified.
- **[A]**: assumption by the authors.
- **[U]**: untested capability.

"Not stated" means the checked page does not say. It does not mean "no".

## Method and limits

**Method.** Pin the version; query the sources in the Sources section below by package and repository; check advisories against declared dependency ranges; record dates; treat absence as Unknown; keep license (C7) and vulnerability (C11) separate; no scanner was run.

**Source roles.** GitHub Security Advisories and the GitHub Advisory Database, NVD and package registries are primary. **deps.dev (Google Open Source Insights)** is a supplementary source used for per-version advisory keys. Its limits: it republishes OSV-style identifiers (GHSA, PYSEC), its coverage and update delay are not documented on the pages checked, and "no advisory keys" means none known to deps.dev, not none exist. OSV.dev was not queried directly. Findings from deps.dev were cross-checked against GitHub advisory pages wherever an advisory was opened.

**Limits of this assessment.**
- Only direct dependencies at their lowest declared version and at current releases were checked for code-review-graph and repowise. Transitive dependencies and constraints were not.
- Most of repowise's 53 core dependencies, including 27 tree-sitter grammar packages, remain **Unknown**.
- Whether a tool uses an affected code path is unverified.
- Advisories exist only if someone files them; both tools assessed are under nine months old.
- Name searches in the advisory database are keyword matches; results were filtered to the exact package.
- PYSEC identifiers from deps.dev were not opened.

## C11 full assessment

Rating terms: **Concern found**, **Mitigated at declared floor**, **No issues found (limited evidence)**, **Positive practice documented**, **No published security policy found**, **Unknown**. None means "secure". Detail is in Appendix A.

Rating dimensions: S1 advisories on the tool itself, S2 dependency risk, S3 security policy, S4 maintenance, S5 supply chain, S6 operational risk (documentation review).

| Tool and version | S1 Advisories on the tool itself | S2 Dependency risk | S3 Security policy | S4 Maintenance | S5 Supply chain | S6 Operational (documentation review) |
|---|---|---|---|---|---|---|
| **code-review-graph 2.3.9** | No issues found (limited evidence) | **Potential dependency-resolution risk.** Declared ranges permit versions with known advisories (mcp: 5 High; anyio: 1 Critical, 1 High; fastmcp: 1 Moderate). Fixed in current releases; actual resolution and exposure unverified. | Policy published: supports 2.3.x; private reporting; 48 h acknowledgement and 7-day critical-fix targets (project's claims) | At least 34 releases 26 Feb–10 Jun 2026, plus 2.3.9 on 18 Sep; one maintainer listed on PyPI | Unknown | Unknown (MCP server with 30 tools; `install` edits editor configs and git hooks) |
| **repowise 0.59.0** | No issues found (limited evidence) | **Mitigated at declared floor** for all checked Critical/High (litellm, GitPython, cryptography, mcp). Range-level exposure to Moderate advisories (litellm, jinja2). 53 core direct dependencies, most unchecked → **Unknown** overall. | Policy published, but says fixes go only to the "0.54.x" line while latest is 0.59.0 | First visible release 28 Mar 2026; frequent releases | PyPI publish attestation linked; contents not verified | Unknown (opt-out telemetry; optional cloud LLM providers; dashboard and MCP server; `init` edits user configs and can install a git hook) |
| **Joern v4.0.665** | No issues found (limited evidence) | Unknown | No published security policy found | Daily releases [V-claim]; 283 open issues | Unknown | Unknown (JDK 21; query shell runs arbitrary queries by design [A]) |
| **Tree-sitter (crate 0.27.1)** | No issues found (limited evidence); NVD/GHSA hits concern another product | Unknown (runtime stated dependency-free) | No published security policy found | Active; 0.22.0 yanked in 2024 | Unknown | Parses untrusted source; no network use stated |
| **SQLGlot 30.25.0** | No issues found (limited evidence) | No runtime dependencies declared on PyPI | No published security policy found | Released one day before assessment | Unknown | Pure library; optional native extras |
| code-maat, CodeCharta, tokei | No published repository advisories | Unknown | No published security policy found | Unknown | Unknown | Unknown |

Commercial and closed tools are not assessable from public sources. Tools not listed were not assessed for C11.

## License detail

License notes are input for Issue #30 and are not legal advice. The grouped summary is in [§6.4 of the main report](./tool-evaluation.md#64-license-summary-c7-separate-from-c11); the per-tool license is in the C7 column of the [comparison matrix](./tool-evaluation.md#61-main-comparison-c1c10).

- **repowise:** the README and the `LICENSE` file say AGPL-3.0 (the file is the plain GNU AGPL v3 text); the PyPI metadata says "AGPL-3.0-or-later"; the README offers commercial licensing. The design SBOM's "OR" expression is not confirmed by these pages. Whether an AGPL tool may be used is Issue #30.
- **CodeQL:** the queries repository is MIT; the CLI is licensed separately; the page says analysing closed-source code needs a commercial license [V].
- **CodeScene:** commercial; free for open-source projects, trial offered [V]. **Sonargraph and Driver:** commercial [V]. **CodeMR:** no license or pricing on the page [V].
- **Sourcegraph Cody:** the public repository is an archived read-only snapshot, Apache-2.0 [V].
- **Reference systems:** the public IBM repository is Apache-2.0 [V]. The industry partner states that the IBM source is unchanged and Apache-2.0 and that its own additions are also Apache-2.0 [P]. The partner's license notices have not been read.

## Appendix A: Dependency advisory checks (C11 / S2)

Latest releases at assessment (PyPI): fastmcp 4.1.4, mcp 2.3.0, anyio 4.15.1, litellm 1.106.4, GitPython 3.2.1, jinja2 3.1.6. Advisory ranges were read from each GitHub advisory page.

### A.1 code-review-graph 2.3.9

| Dependency (declared) | Advisory | Severity | Affected | Fixed | Result |
|---|---|---|---|---|---|
| fastmcp (`>=3.2.4,<4`) | GHSA-vv7q-7jx5-f767 (CVE-2026-32871) | Critical | <3.2.0 | 3.2.0 | Fixed below floor |
| | GHSA-rww4-4w9c-7733 (CVE-2026-27124) | High | <3.2.0 | 3.2.0 | Fixed below floor |
| | GHSA-5h2m-4q8j-pqpj (CVE-2025-69196) | High | <2.14.2 | 2.14.2 | Fixed below floor |
| | GHSA-rcfx-77hg-w2wv (no CVE) | High | <2.14.0 | 2.14.0 | Fixed below floor |
| | GHSA-c2jp-c369-7pvx (no CVE) | High | <2.13.0 | 2.13.0 | Fixed below floor |
| | GHSA-7xgj-8392-5q4r | Moderate | >=3.0.0,<3.4.10; >=4.0.0,<4.1.2 | 3.4.10; 4.1.2 | **Range permits affected 3.x**; cap `<4` keeps 4.x out |
| mcp (`>=1.0.0,<3`) | GHSA-3qhf-m339-9g5v (CVE-2025-53366) | High | <1.9.4 | 1.9.4 | **Range permits affected** |
| | GHSA-j975-95f5-7wqh (CVE-2025-53365) | High | <1.10.0 | 1.10.0 | **Range permits affected** |
| | GHSA-9h52-p55h-vw2f (CVE-2025-66416) | High | <1.23.0 | 1.23.0 | **Range permits affected** |
| | GHSA-jpw9-pfvf-9f58 (CVE-2026-52869) | High | <=1.27.1 | 1.27.2 | **Range permits affected** |
| | GHSA-vj7q-gjh5-988w (CVE-2026-59950) | High | <1.28.1 | 1.28.1 | **Range permits affected** |
| | GHSA-84m7-p3x7-pcfv (CVE-2026-59951) | Moderate | >=1.8.0,<1.30.0; >=2.0.0,<2.2.0 | 1.30.0; 2.2.0 | **Range permits affected** |
| anyio (`>=4.0,<5`) | GHSA-82r6-8w77-94w6 (CVE-2026-63374) | Critical | <4.14.2 | 4.14.2 | **Range permits affected** |
| | GHSA-3w57-8xmc-8v26 (CVE-2026-63349) | High | >=4.14.0,<4.14.2 | 4.14.2 | **Range permits affected** |
| | GHSA-5p39-cfhj-2xmp | Moderate | not opened | — | Listed only (deps.dev at 4.0.0) |
| pyyaml 6.0, networkx 3.2, watchdog 4.0.0 | none in deps.dev at floor | — | — | — | No known advisory keys |
| tree-sitter, tree-sitter-language-pack | — | — | — | — | Not checked |

Reading: the declared floors of mcp and anyio are loose. Current releases of both (mcp 2.3.0, anyio 4.15.1) show no advisory keys in deps.dev, so a fresh resolution would normally avoid these versions [A]. An older lockfile or manual pin could land in the affected ranges. This is a **potential dependency-resolution risk**, not a confirmed vulnerability in code-review-graph.

### A.2 repowise 0.59.0

| Dependency (declared) | Advisory | Severity | Affected | Fixed | Result |
|---|---|---|---|---|---|
| litellm (`>=1.90.7,<2`) | GHSA-6wvf-77m9-58rm (CVE-2026-37004) | Critical | <1.83.7 | 1.83.7 | Fixed below floor |
| | GHSA-4xpc-pv4p-pm3w (CVE-2026-49468) | Critical | <1.84.0 | 1.84.0 | Fixed below floor |
| | GHSA-r75f-5x8p-qvmc (CVE-2026-42208) | Critical | >=1.81.16,<1.83.7 | 1.83.7 | Fixed below floor |
| | GHSA-jjhc-v7c2-5hh6 (CVE-2026-35030) | Critical | <1.83.0 | 1.83.0 | Fixed below floor |
| | GHSA-5mg7-485q-xm76 (no CVE) | Critical (malware) | exactly 1.82.7–1.82.8 | none | Excluded by floor |
| | GHSA-7488-6r32-c95q (CVE-2026-59822) | High | <1.84.0 | 1.84.0 | Fixed below floor |
| | GHSA-wpfp-gwwc-vwq6 (CVE-2026-47102) | High | <1.83.10 | 1.83.10 | Fixed below floor |
| | GHSA-qrc4-49gv-mv9m (CVE-2026-47101) | High | <1.83.14 | 1.83.14 | Fixed below floor |
| | GHSA-wxxx-gvqv-xp7p (CVE-2026-40217) | High | >=1.81.8,<1.83.10 | 1.83.10 in metadata; the description says 1.83.11 | Fixed below floor either way |
| | GHSA-v4p8-mg3p-g94g (CVE-2026-42271) | High | >=1.74.2,<1.83.7 | 1.83.7 | Fixed below floor |
| | GHSA-xqmj-j6mv-4862 (CVE-2026-42203) | High | >=1.80.5,<1.83.7 | 1.83.7 | Fixed below floor |
| | GHSA-69x8-hrgq-fjj8 (no CVE) | High | <1.83.0 | 1.83.0 | Fixed below floor |
| | GHSA-53mr-6c8q-9789 (CVE-2026-35029) | High | <1.83.0 | 1.83.0 | Fixed below floor |
| | GHSA-3cv6-jpf6-8222 | Moderate | <1.88.6; >=1.89.0,<1.89.7; >=1.90.0,<1.90.7; >=1.91.0,<1.91.5; >=1.92.0,<1.92.2; >=1.93.0,<1.93.2; >=1.94.0,<1.94.3; >=1.95.0,<1.95.1; >=1.96.0,<1.96.2 | 1.88.6 … 1.96.2 | Floor is patched in its own line; **range permits 1.91.0–1.96.1 affected lines** |
| | deps.dev | — | no advisory keys at 1.90.7 or latest 1.106.4 | — | Consistent with the above |
| GitPython (`>=3.2.1,<4`) | GHSA-284h-m62q-gf8w (CVE-2026-78676) | Critical | <=3.1.58 | 3.1.59 | Fixed below floor |
| | GHSA-83vg-56qc-22m7 (CVE-2026-114145) | High | <=3.2.0 | 3.2.1 | Fixed at floor |
| | GHSA-g5vv-9gxw-82hx (CVE-2026-87819), GHSA-239g-whfq-7xj9 (CVE-2026-87817) | High | <=3.1.59 | 3.1.60 | Fixed below floor |
| | GHSA-8mcc-hrx5-hvxc (CVE-2026-78677), GHSA-7833-fr7j-v32q (CVE-2026-78675) | High | <=3.1.58 | 3.1.59 | Fixed below floor |
| | GHSA-wvpp-8hx9-p66j (CVE-2026-76220), GHSA-jm78-9fvv-mhgr (no CVE) | High | <=3.1.57 | 3.1.58 | Fixed below floor |
| | ~20 further Critical/High listed, not opened | — | — | — | deps.dev: no advisory keys for 3.2.1 |
| cryptography (`>=50.0.0,<51`) | GHSA-g6cj-pr64-35w5 (CVE-2026-69247) | High | >=44.0.0,<50.0.0 | 50.0.0 | Fixed at floor |
| | GHSA-jwv3-5hgf-82ww (CVE-2026-69249) | High | >=42.0.0,<49.0.0 | 49.0.0 | Fixed below floor |
| mcp (`>=1.30.0,<2`) | GHSA-84m7-p3x7-pcfv | Moderate | see A.1 | 1.30.0 | Fixed at floor; deps.dev none at 1.30.0 |
| jinja2 (`>=3.1,<4`) | GHSA-cpwx-vrp4-4pq7, GHSA-gmj6-6f8f-6699, GHSA-h5c8-rqwp-cp95, GHSA-h75v-3vvj-5mfj, GHSA-q2x7-8rv6-6q7h | all Moderate | up to <=3.1.5 | 3.1.3–3.1.6 | **Range permits affected 3.1.x**; latest 3.1.6 fixes all five; 5 PYSEC keys not opened |
| httpx 0.27.0, fastapi 0.115.0, uvicorn 0.32.0, sqlalchemy 2.0.0 | none in deps.dev at floor | — | — | — | No known advisory keys |
| Remaining ~40 direct dependencies (incl. 27 tree-sitter grammar packages, lancedb, pydantic, apscheduler, scipy, LLM SDKs) | — | — | — | — | **Unknown** (not checked) |

## Open items owned by this document

These are items 6, 7, 8 and 14 of the [open questions in the main report](./tool-evaluation.md#11-open-questions-and-untested-items): the AGPL decision (Issue #30), the lockfile-level and transitive dependency scan, the repowise and SQLGlot version-range conflict, and the repowise telemetry opt-out mechanism. Most of repowise's 53 core dependencies, all transitive dependencies and the PYSEC identifiers remain **Unknown** or unopened, as stated in Appendix A and in the limits above.

## Sources (accessed 27 Oct 2026)

Tool pages, documentation, LICENSE files, registry pages and reference systems are listed in [§12 of the main report](./tool-evaluation.md#12-sources-accessed-27-oct-2026). The sources below were used for the security and dependency checks.

**code-review-graph**
- https://github.com/tirth8205/code-review-graph/security
- https://raw.githubusercontent.com/tirth8205/code-review-graph/main/SECURITY.md
- https://api.deps.dev/v3/systems/pypi/packages/code-review-graph/versions/2.3.9
- https://github.com/advisories?query=code-review-graph
- https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=code-review-graph

**repowise**
- https://github.com/repowise-dev/repowise/security
- https://raw.githubusercontent.com/repowise-dev/repowise/main/.github/SECURITY.md
- https://api.deps.dev/v3/systems/pypi/packages/repowise/versions/0.59.0
- https://github.com/advisories?query=repowise
- https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=repowise

**Dependency advisories: lists**
- https://github.com/advisories?query=ecosystem%3Apip+litellm (pages 1 and 2)
- https://github.com/advisories?query=ecosystem%3Apip+fastmcp
- https://github.com/advisories?query=ecosystem%3Apip+gitpython (pages 1–3)
- https://github.com/advisories?query=ecosystem%3Apip+mcp
- https://github.com/advisories?query=ecosystem%3Apip+cryptography
- https://github.com/advisories?query=ecosystem%3Apip+anyio

**Dependency advisories: individual pages (https://github.com/advisories/<ID>)**
- fastmcp: GHSA-vv7q-7jx5-f767, GHSA-rww4-4w9c-7733, GHSA-5h2m-4q8j-pqpj, GHSA-rcfx-77hg-w2wv, GHSA-c2jp-c369-7pvx, GHSA-7xgj-8392-5q4r
- mcp: GHSA-3qhf-m339-9g5v, GHSA-j975-95f5-7wqh, GHSA-9h52-p55h-vw2f, GHSA-jpw9-pfvf-9f58, GHSA-vj7q-gjh5-988w, GHSA-84m7-p3x7-pcfv
- anyio: GHSA-82r6-8w77-94w6, GHSA-3w57-8xmc-8v26
- litellm: GHSA-6wvf-77m9-58rm, GHSA-4xpc-pv4p-pm3w, GHSA-r75f-5x8p-qvmc, GHSA-jjhc-v7c2-5hh6, GHSA-5mg7-485q-xm76, GHSA-7488-6r32-c95q, GHSA-wpfp-gwwc-vwq6, GHSA-qrc4-49gv-mv9m, GHSA-wxxx-gvqv-xp7p, GHSA-v4p8-mg3p-g94g, GHSA-xqmj-j6mv-4862, GHSA-69x8-hrgq-fjj8, GHSA-53mr-6c8q-9789, GHSA-3cv6-jpf6-8222
- GitPython: GHSA-284h-m62q-gf8w, GHSA-83vg-56qc-22m7, GHSA-g5vv-9gxw-82hx, GHSA-239g-whfq-7xj9, GHSA-8mcc-hrx5-hvxc, GHSA-7833-fr7j-v32q, GHSA-wvpp-8hx9-p66j, GHSA-jm78-9fvv-mhgr
- cryptography: GHSA-g6cj-pr64-35w5, GHSA-jwv3-5hgf-82ww
- jinja2: GHSA-cpwx-vrp4-4pq7, GHSA-gmj6-6f8f-6699, GHSA-h5c8-rqwp-cp95, GHSA-h75v-3vvj-5mfj, GHSA-q2x7-8rv6-6q7h

**Dependency version checks (supplementary, deps.dev): https://api.deps.dev/v3/systems/pypi/packages/<name>/versions/<version>**
- gitpython 3.2.1; litellm 1.90.7 and 1.106.4; cryptography 50.0.0; fastmcp 3.2.4 and 3.4.10; anyio 4.0.0 and 4.15.1; mcp 1.0.0, 1.30.0 and 2.3.0; pyyaml 6.0; networkx 3.2; watchdog 4.0.0; httpx 0.27.0; fastapi 0.115.0; uvicorn 0.32.0; jinja2 3.1.0; sqlalchemy 2.0.0
- Latest versions: https://pypi.org/pypi/gitpython/json, https://pypi.org/pypi/fastmcp/json, https://pypi.org/pypi/litellm/json, https://pypi.org/pypi/anyio/json, https://pypi.org/pypi/mcp/json, https://pypi.org/pypi/jinja2/json

**Joern**
- https://github.com/joernio/joern/security
- https://github.com/advisories?query=joern
- https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=joern

**Tree-sitter**
- https://github.com/tree-sitter/tree-sitter/security
- https://github.com/advisories?query=tree-sitter
- https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=tree-sitter

**SQLGlot**
- https://github.com/tobymao/sqlglot/security
- https://api.deps.dev/v3/systems/pypi/packages/sqlglot/versions/30.25.0
- https://github.com/advisories?query=sqlglot
- https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=sqlglot
