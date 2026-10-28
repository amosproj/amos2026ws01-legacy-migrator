#!/usr/bin/env python3
"""SBOM and licence-compliance helper (stdlib only, Python >= 3.11).

Sub-commands
  inspect-dists  run with the *target environment's* interpreter; records licence
                 metadata and licence/notice files of every installed distribution
  merge          merge the environment SBOM with the manual supplement, add
                 deterministic serial number/timestamp, cross-check with uv.lock
  check          licence gate: project LICENSE detection, dependency licence
                 compatibility, licence-file presence, approved exceptions
  render-md      render the SBOM as a Markdown table for the planning document

Engineering aid, not legal advice. The policy lives in licence-policy.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

LICENCE_FILE_RE = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors|copyright)([.\-_][^/]*)?$", re.I)
PROP_GROUP = "migration-assistant:group"
RANK = {"allow": 0, "allow-aggregate": 0, "report": 0, "review": 1, "deny": 2}


# --------------------------------------------------------------------------- io
def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        if default is not None:
            return default
        sys.exit(f"missing file: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def dump_json(obj, path):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def norm_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------- inspect-dists
def cmd_inspect_dists(args):
    from importlib import metadata

    out = {}
    for dist in metadata.distributions():
        md = dist.metadata
        name = md.get("Name")
        if not name:
            continue
        files = [str(f) for f in (dist.files or [])]
        lic_files = sorted({f for f in files if LICENCE_FILE_RE.search(f) and ".dist-info/" in f or "/licenses/" in f})
        texts = {}
        for rel in lic_files[:20]:
            try:
                p = dist.locate_file(rel)
                data = Path(p).read_text(encoding="utf-8", errors="replace")
                texts[rel.split("/")[-1] if "/licenses/" not in rel else rel.split("/licenses/")[-1]] = data[:200_000]
            except OSError:
                pass
        out[norm_name(name)] = {
            "name": name,
            "version": md.get("Version"),
            "license_expression": md.get("License-Expression"),
            "license": (md.get("License") or "").strip()[:500] or None,
            "classifiers": sorted(c for c in (md.get_all("Classifier") or []) if c.startswith("License ::")),
            "license_file_headers": md.get_all("License-File") or [],
            "licence_files": texts,
        }
    dump_json(dict(sorted(out.items())), args.out)


# ------------------------------------------------------------------------ merge
def _key(c):
    return (c.get("purl") or c.get("name", "")).lower()


def cmd_merge(args):
    runtime = load_json(args.runtime)
    dev = load_json(args.dev)
    supplement = load_json(args.supplement, default={"components": [], "services": []})

    lock_bytes = Path(args.lock).read_bytes()
    supp_bytes = Path(args.supplement).read_bytes() if Path(args.supplement).exists() else b""
    digest = hashlib.sha256(lock_bytes + b"\0" + supp_bytes).hexdigest()
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0") or 0)
    ts = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def finalise(bom, label):
        bom["serialNumber"] = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'sbom/{label}/{digest}')}"
        bom["version"] = 1
        md = bom.setdefault("metadata", {})
        md["timestamp"] = ts
        md["lifecycles"] = [{"phase": "build"}]
        props = [p for p in md.get("properties", []) if not p.get("name", "").startswith("sbom:")]
        props += [{"name": "sbom:source", "value": "uv.lock"},
                  {"name": "sbom:uv-lock-sha256", "value": hashlib.sha256(lock_bytes).hexdigest()},
                  {"name": "sbom:scope", "value": label}]
        md["properties"] = props
        return bom

    # runtime + supplement
    comps = {_key(c): c for c in runtime.get("components", [])}
    for c in supplement.get("components", []):
        comps.setdefault(_key(c), c)
    runtime["components"] = sorted(comps.values(), key=lambda c: (c.get("type", ""), c.get("name", "").lower()))
    services = {}
    for s in runtime.get("services", []) + supplement.get("services", []):
        name = s.get("name")
        if name:
            services[name] = s

    if services:
        runtime["services"] = [services[k] for k in sorted(services)]
    rootref = runtime.get("metadata", {}).get("component", {}).get("bom-ref")
    if rootref:
        deps = {d["ref"]: d for d in runtime.get("dependencies", [])}
        root = deps.setdefault(rootref, {"ref": rootref})
        root.setdefault("dependsOn", [])

        for c in supplement.get("components", []):
            ref = c.get("bom-ref")
            if c.get("scope") != "excluded" and ref and ref not in root["dependsOn"]:
                root["dependsOn"].append(ref)

        root["dependsOn"].sort()
        runtime["dependencies"] = [deps[k] for k in sorted(deps)]
    dump_json(finalise(runtime, "runtime"), args.out)

    for c in dev.get("components", []):
        c["scope"] = "optional"
        c.setdefault("properties", []).append({"name": PROP_GROUP, "value": "dev"})
    dump_json(finalise(dev, "dev"), args.dev_out)

    # cross-check: packages in uv.lock export vs. installed environment
    locked = set()
    for line in Path(args.lock_export).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            locked.add(norm_name(re.split(r"[=<>!~;\s\[]", line, maxsplit=1)[0]))
    installed = {norm_name(c["name"]) for c in runtime["components"] if (c.get("purl") or "").startswith("pkg:pypi/")}
    missing = sorted(locked - installed)
    if missing:
        print("WARNING: packages in uv.lock but not installed on this platform "
              f"(platform markers?) and therefore not in the SBOM: {', '.join(missing)}")


# ---------------------------------------------------------------- licence logic
class Policy:
    def __init__(self, data):
        self.d = data
        self.id_to_cat = {}
        for cat, ids in data["categories"].items():
            for i in ids:
                self.id_to_cat[i.lower()] = cat
        self.patterns = [(re.compile(p, re.I), cat) for p, cat in data["name_patterns"]]
        self.with_patterns = [(re.compile(p, re.I), cat) for p, cat in data["with_exception_patterns"]]

    def category(self, token: str) -> str:
        t = token.strip().strip("()").strip()
        if not t:
            return "unknown"
        t = re.sub(r"\+$", "-or-later", t)
        if t.lower() in self.id_to_cat:
            return self.id_to_cat[t.lower()]
        for rx, cat in self.patterns:
            if rx.search(t):
                return cat
        return "unknown"

    def decide(self, cat, project_family, context):
        if context == "report":
            return "report", "dev-only dependency, not distributed"
        if context == "aggregate":
            dec = self.d["aggregate_matrix"].get(cat, "review")
            return dec, self.d["notes"].get(f"aggregate:{cat}", "separate program / data, not linked")
        row = self.d["linked_matrix"][project_family]
        dec = row.get(cat, "review")
        return dec, self.d["notes"].get(f"{project_family}:{cat}", self.d["notes"].get(cat, ""))


def tokenize(expr):
    return re.findall(r"\(|\)|\bAND\b|\bOR\b|\bWITH\b|[^\s()]+", expr)


def eval_expr(expr, policy, family, context):
    """Returns (decision, category-summary, note) for an SPDX-like expression."""
    toks = tokenize(expr)
    if not any(t in ("AND", "OR", "WITH") for t in toks):
        cat = policy.category(expr)
        d, n = policy.decide(cat, family, context)
        return d, cat, n
    pos = 0

    def parse_or():
        nonlocal pos
        left = parse_and()
        while pos < len(toks) and toks[pos] == "OR":
            pos += 1
            right = parse_and()
            left = left if RANK[left[0]] <= RANK[right[0]] else right
        return left

    def parse_and():
        nonlocal pos
        left = parse_atom()
        while pos < len(toks) and toks[pos] == "AND":
            pos += 1
            right = parse_atom()
            left = left if RANK[left[0]] >= RANK[right[0]] else right
        return left

    def parse_atom():
        nonlocal pos
        if pos < len(toks) and toks[pos] == "(":
            pos += 1
            r = parse_or()
            if pos < len(toks) and toks[pos] == ")":
                pos += 1
            return r
        tok = toks[pos] if pos < len(toks) else ""
        pos += 1
        cat = policy.category(tok)
        if pos < len(toks) and toks[pos] == "WITH":
            pos += 1
            exc = toks[pos] if pos < len(toks) else ""
            pos += 1
            for rx, wcat in policy.with_patterns:
                if rx.search(exc):
                    cat = wcat if cat.startswith(("gpl", "lgpl")) or wcat == "apache" else cat
                    break
        d, n = policy.decide(cat, family, context)
        return d, cat, n

    return parse_or()


def component_licence_strings(comp, dists):
    out = []
    for item in comp.get("licenses", []) or []:
        if "expression" in item:
            out.append(item["expression"])
        elif "license" in item:
            lic = item["license"]
            out.append(lic.get("id") or lic.get("name") or "")
    out = [s for s in out if s and s.upper() != "UNKNOWN"]
    if out:
        return out, "sbom"
    d = dists.get(norm_name(comp.get("name", "")))
    if d:
        if d.get("license_expression"):
            return [d["license_expression"]], "metadata"
        cls = [c.split("::")[-1].strip() for c in d.get("classifiers", [])]
        cls = [c for c in cls if c not in ("OSI Approved",)]
        if cls:
            return cls, "classifier"
        if d.get("license") and len(d["license"]) < 120:
            return [d["license"]], "metadata"
    return [], "none"


def evaluate_component(comp, dists, policy, family, context):
    strings, source = component_licence_strings(comp, dists)
    if not strings:
        return {"decision": "deny" if context != "report" else "report", "category": "unknown",
                "licence": "(none found)", "note": "no licence metadata", "source": source}
    # several entries for one component = alternatives declared by the package -> OR
    expr = " OR ".join(f"({s})" if " " in s else s for s in strings)
    d, cat, note = eval_expr(expr, policy, family, context)
    return {"decision": d, "category": cat, "licence": " | ".join(strings), "note": note, "source": source}


def context_of(comp):
    if comp.get("scope") == "excluded":
        return "skip"
    group = next((p["value"] for p in comp.get("properties", []) if p.get("name") == PROP_GROUP), None)
    if group == "dev":
        return "report"
    if group in ("service", "runtime", "model") or comp.get("type") in ("container", "machine-learning-model", "data"):
        return "aggregate"
    return "linked"


# ------------------------------------------------------- project licence detection
# Each entry: (SPDX, patterns that must match, "head" = only search the first 600 characters).
# GNU texts mention each other (GPL-3.0 section 13 names the AGPL; the GPL appendix names
# the LGPL), so the GNU family is identified by the document title at the top of the file.
FINGERPRINTS = [
    ("AGPL-3.0", [r"gnu affero general public license version 3,? 19 november 2007"], True),
    ("LGPL-3.0", [r"gnu lesser general public license version 3,? 29 june 2007"], True),
    ("LGPL-2.1", [r"gnu lesser general public license version 2\.1"], True),
    ("GPL-3.0", [r"gnu general public license version 3,? 29 june 2007"], True),
    ("GPL-2.0", [r"gnu general public license version 2,? june 1991"], True),
    ("MPL-2.0", [r"mozilla public license,? version 2\.0"], True),
    ("Apache-2.0", [r"apache license,? version 2\.0"], True),
    ("MIT", [r"permission is hereby granted, free of charge"], False),
    ("BSD-3-Clause", [r"redistribution and use in source and binary forms", r"neither the name"], False),
    ("BSD-2-Clause", [r"redistribution and use in source and binary forms"], False),
    ("ISC", [r"permission to use, copy, modify, and(/or)? distribute this software for any purpose"], False),
    ("Unlicense", [r"this is free and unencumbered software released into the public domain"], False),
]
PROJECT_LICENCE_FILES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md", "COPYING", "COPYING.md"]


def detect_project_licence(root: Path):
    info = {"file": None, "file_spdx": None, "pyproject_spdx": None, "problems": []}
    for name in PROJECT_LICENCE_FILES:
        p = root / name
        if p.is_file():
            info["file"] = name
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            text = re.sub(r"[#*_=`>]+", " ", text)          # strip markdown decoration
            text = re.sub(r"\s+", " ", text).strip()
            head = text[:600]
            for spdx, pats, head_only in FINGERPRINTS:
                hay = head if head_only else text
                if all(re.search(x, hay) for x in pats):
                    info["file_spdx"] = spdx
                    break
            if not info["file_spdx"]:
                info["problems"].append(f"{name} exists but its licence could not be identified")
            break
    if not info["file"] and (root / "LICENSES").is_dir():
        info["file"] = "LICENSES/ (REUSE)"
    pp = root / "pyproject.toml"
    if pp.is_file():
        try:
            import tomllib
            proj = tomllib.loads(pp.read_text(encoding="utf-8")).get("project", {})
            lic = proj.get("license")
            if isinstance(lic, str):
                info["pyproject_spdx"] = lic
            elif isinstance(lic, dict) and lic.get("text"):
                info["pyproject_spdx"] = lic["text"].strip()
            for c in proj.get("classifiers", []):
                if c.startswith("License ::") and not info["pyproject_spdx"]:
                    info["pyproject_spdx"] = c.split("::")[-1].strip()
        except Exception as exc:  # noqa: BLE001
            info["problems"].append(f"pyproject.toml could not be parsed: {exc}")
    return info


def family_of(spdx, policy):
    if not spdx:
        return None
    s = re.sub(r"\+$", "-or-later", spdx.strip())
    fam = policy.d["project_families"]
    if s in fam:
        return fam[s]
    for key, val in fam.items():          # tolerate "GPL-3.0" vs "GPL-3.0-only"
        if key.lower().startswith(s.lower()) or s.lower().startswith(key.lower()):
            return val
    cat = policy.category(s)
    return {"permissive": "permissive", "apache": "permissive", "weak": "weak", "lgpl21": "lgpl",
            "lgpl3": "lgpl", "gpl2only": "gpl2only", "gpl2plus": "gpl2plus", "gpl3": "gpl3",
            "agpl3": "agpl3"}.get(cat)


def same_licence(a, b):
    def n(x):
        x = re.sub(r"(-only|-or-later|\+)$", "", x.strip(), flags=re.I).lower()
        return {"mit license": "mit", "apache software license": "apache-2.0"}.get(x, x)
    return n(a) == n(b) or n(a).startswith(n(b)) or n(b).startswith(n(a))


# ------------------------------------------------------------------- exceptions
def active_exceptions(path):
    data = load_json(path, default={"exceptions": []})
    today = dt.date.today().isoformat()
    out, problems = {}, []
    for e in data.get("exceptions", []):
        missing = [k for k in ("component", "justification", "approved_by", "expires") if not e.get(k)]
        if missing:
            problems.append(f"exception for {e.get('component')} ignored: missing {', '.join(missing)}")
            continue
        if e["expires"] < today:
            problems.append(f"exception for {e['component']} expired on {e['expires']}")
            continue
        out[norm_name(e["component"])] = e
    return out, problems


# ------------------------------------------------------------------------ check
def cmd_check(args):
    policy = Policy(load_json(args.policy))
    sbom = load_json(args.sbom)
    dev_sbom = load_json(args.dev_sbom, default={"components": []})
    dists = load_json(args.dists, default={})
    dev_dists = load_json(args.dev_dists, default={})
    exceptions, exc_problems = active_exceptions(args.exceptions)
    root = Path(args.project_root)

    lines, errors, warnings = [], [], list(exc_problems)
    lines.append("## Licence compliance report\n")

    # ---- project licence
    info = detect_project_licence(root)
    declared = info["file_spdx"] or info["pyproject_spdx"]
    if info["file_spdx"] and info["pyproject_spdx"] and not same_licence(info["file_spdx"], info["pyproject_spdx"]):
        errors.append(f"LICENSE file ({info['file_spdx']}) and pyproject.toml ({info['pyproject_spdx']}) disagree")
    if info["pyproject_spdx"] and not info["file"]:
        errors.append(f"pyproject.toml declares {info['pyproject_spdx']} but there is no LICENSE file in the repository")
    errors += info["problems"]
    override = os.environ.get("PROJECT_LICENSE", "").strip()
    require = os.environ.get("SBOM_REQUIRE_PROJECT_LICENSE", "false").lower() == "true"

    if declared:
        candidates = [declared]
        mode = "enforce"
        if override and not same_licence(override, declared):
            warnings.append(f"PROJECT_LICENSE={override} ignored: repository declares {declared}")
    elif override:
        candidates = [override]
        mode = "enforce (PROJECT_LICENSE override, no LICENSE file yet)"
        warnings.append("No LICENSE file yet; using PROJECT_LICENSE override")
    else:
        candidates = policy.d["candidate_project_licences"]
        mode = "undecided"
        msg = "No project LICENSE file: running in 'undecided' mode against all candidate licences"
        (errors if require else warnings).append(msg + (" (release builds require a LICENSE)" if require else ""))

    lines.append(f"- Project licence file: `{info['file'] or 'none'}` → `{info['file_spdx'] or '-'}`")
    lines.append(f"- pyproject.toml licence: `{info['pyproject_spdx'] or '-'}`")
    lines.append(f"- Mode: **{mode}**; evaluated against: {', '.join(f'`{c}`' for c in candidates)}\n")

    fams = {}
    for c in candidates:
        f = family_of(c, policy)
        if not f:
            errors.append(f"project licence '{c}' is not covered by licence-policy.json (project_families)")
        else:
            fams[c] = f

    # ---- components
    comps = [(c, "runtime") for c in sbom.get("components", [])] + [(c, "dev") for c in dev_sbom.get("components", [])]
    results = []  # (comp, ctx, {cand: result})
    for comp, origin in comps:
        ctx = "report" if origin == "dev" else context_of(comp)
        if ctx == "skip":
            continue
        dd = dev_dists if origin == "dev" else dists
        per = {cand: evaluate_component(comp, dd, policy, fam, ctx) for cand, fam in fams.items()}
        results.append((comp, ctx, per, dd))

    # ---- licence files of python distributions (attribution)
    missing_files = []
    for comp, ctx, per, dd in results:
        if ctx in ("linked", "report") and (comp.get("purl") or "").startswith("pkg:pypi/"):
            d = dd.get(norm_name(comp["name"]))
            if d is not None and not d.get("licence_files"):
                missing_files.append(comp["name"])
    if missing_files:
        warnings.append("No licence text shipped in the installed package (attribution must be sourced manually): "
                        + ", ".join(sorted(set(missing_files))))

    # ---- decisions
    def apply_exception(comp, res):
        e = exceptions.get(norm_name(comp.get("name", "")))
        if e and res["decision"] in ("review", "deny") and (e.get("version", "*") in ("*", comp.get("version"))):
            return dict(res, decision="allow", note=f"exception: {e['justification']} (approved by {e['approved_by']}, until {e['expires']})")
        return res

    blocking_all = []
    per_candidate_fail = {c: [] for c in fams}
    table = ["| Component | Version | Context | Licence | " + " | ".join(f"`{c}`" for c in fams) + " |",
             "|---|---|---|---|" + "---|" * len(fams)]
    for comp, ctx, per, _ in sorted(results, key=lambda r: (r[1], r[0].get("name", "").lower())):
        cells, bad = [], 0
        for cand in fams:
            r = apply_exception(comp, per[cand])
            per[cand] = r
            icon = {"allow": "✅", "allow-aggregate": "✅ᵃ", "report": "ℹ️", "review": "⚠️ review", "deny": "❌ deny"}[r["decision"]]
            cells.append(icon)
            if r["decision"] in ("review", "deny"):
                per_candidate_fail[cand].append(f"{comp.get('name')} ({r['licence']}: {r['decision']})")
                bad += 1
        if fams and bad == len(fams):
            blocking_all.append(comp.get("name"))
        any_r = next(iter(per.values())) if per else {"licence": "?"}
        table.append(f"| {comp.get('name')} | {comp.get('version', '-')} | {ctx} | `{any_r['licence']}` | " + " | ".join(cells) + " |")
        if any_r.get("category") == "unknown" and ctx != "report":
            errors.append(f"{comp.get('name')}: licence unknown or not recognised ({any_r['licence']})")

    lines.append("### Compatibility summary\n")
    lines.append("| Candidate project licence | Blocking dependencies |")
    lines.append("|---|---|")
    for cand, fails in per_candidate_fail.items():
        lines.append(f"| `{cand}` | {len(fails)}: {'; '.join(fails) if fails else 'none'} |")
    lines.append("")

    if mode.startswith("enforce"):
        for cand, fails in per_candidate_fail.items():
            for f in fails:
                errors.append(f"[{cand}] {f}")
    else:
        for name in blocking_all:
            errors.append(f"{name} is incompatible with every candidate licence")
        ok = [c for c, f in per_candidate_fail.items() if not f]
        lines.append(f"Candidate licences compatible with the current dependencies: "
                     f"{', '.join(f'`{c}`' for c in ok) if ok else '**none**'}\n")

    lines.append("### Components\n")
    lines.append("Legend: ✅ allowed · ✅ᵃ allowed as separate program (aggregate) · ℹ️ dev-only, report only · "
                 "⚠️ needs an approved exception · ❌ not allowed\n")
    lines += table
    lines.append("")
    if warnings:
        lines.append("### Warnings\n")
        lines += [f"- {w}" for w in warnings]
        lines.append("")
    if errors:
        lines.append("### Errors (gate failed)\n")
        lines += [f"- {e}" for e in errors]
        lines.append("")
    else:
        lines.append("**Licence gate passed.**\n")
    lines.append("_Automated engineering check, not legal advice._\n")
    Path(args.report_out).write_text("\n".join(lines), encoding="utf-8")

    # ---- third-party notices (runtime only)
    notice = ["# Third-party licences and notices\n",
              "Generated from the installed runtime dependencies (uv.lock) and the SBOM supplement. "
              "Do not edit by hand; run `scripts/sbom/regenerate_sbom.sh`.\n"]
    for comp in sorted(sbom.get("components", []), key=lambda c: c.get("name", "").lower()):
        if comp.get("scope") == "excluded":
            continue
        strings, _ = component_licence_strings(comp, dists)
        notice.append(f"\n## {comp.get('name')} {comp.get('version', '')}\n")
        notice.append(f"- Licence: `{' | '.join(strings) or 'unknown'}`")
        if comp.get("purl"):
            notice.append(f"- Package URL: `{comp['purl']}`")
        d = dists.get(norm_name(comp.get("name", "")))
        if d and d.get("licence_files"):
            for fname, text in sorted(d["licence_files"].items()):
                notice.append(f"\n<details><summary>{fname}</summary>\n\n```text\n{text.strip()}\n```\n</details>")
        elif (comp.get("purl") or "").startswith("pkg:pypi/"):
            notice.append("- Licence text: not shipped in the package; see the project repository.")
        else:
            notice.append("- Not a Python package (container, model or tool); licence text is provided by the upstream distribution.")
    Path(args.notices_out).write_text("\n".join(notice) + "\n", encoding="utf-8")

    print("\n".join(lines))
    return 1 if errors else 0


# -------------------------------------------------------------------- render-md
def cmd_render_md(args):
    sbom = load_json(args.sbom)
    md = sbom.get("metadata", {})
    root = md.get("component", {})
    out = [
        "Software Bill of Materials",
        f"Project: {root.get('name', '?')} {root.get('version', '')}",
        f"Generated: {md.get('timestamp', '?')}",
        f"From: uv.lock CycloneDX {sbom.get('specVersion')}",
        f"Serial: {sbom.get('serialNumber')}",
        "",
        "Type | Component | Version | Licence (SPDX) | Notes",
        "--- | --- | --- | --- | ---",
    ]

    for i, c in enumerate(
        sorted(
            sbom.get("components", []),
            key=lambda c: (c.get("scope", "required") != "required", c.get("name", "").lower()),
        ),
        1,
    ):
        lic = []
        for item in c.get("licenses", []):
            lic.append(
                item.get("expression")
                or item.get("license", {}).get("id")
                or item.get("license", {}).get("name")
            )

        notes = []
        if c.get("scope") and c.get("scope") != "required":
            notes.append(f"scope: {c['scope']}")
        if c.get("purl"):
            notes.append(c["purl"])

        out.append(
            f"{i} | {c.get('type', '-')} | {c.get('name', '-')} | "
            f"{c.get('version', '-')} | {', '.join(x for x in lic if x) or '-'} | "
            f"{'; '.join(notes) or '-'}"
        )
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------- compare
def cmd_compare(args):
    """Exit 0 if two generated files are equivalent (CycloneDX: ignoring metadata.timestamp)."""
    a, b = Path(args.a), Path(args.b)
    if not a.exists() or not b.exists():
        return 1
    if a.suffix == ".json":
        ja, jb = (json.loads(x.read_text(encoding="utf-8")) for x in (a, b))
        for j in (ja, jb):
            j.get("metadata", {}).pop("timestamp", None)
        return 0 if ja == jb else 1
    return 0 if a.read_bytes() == b.read_bytes() else 1


# ------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("inspect-dists"); p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_inspect_dists)

    p = sp.add_parser("merge")
    for a in ("--runtime", "--dev", "--supplement", "--lock", "--lock-export", "--out", "--dev-out"):
        p.add_argument(a, required=True)
    p.set_defaults(fn=cmd_merge)

    p = sp.add_parser("check")
    for a in ("--sbom", "--policy", "--project-root", "--report-out", "--notices-out"):
        p.add_argument(a, required=True)
    for a in ("--dev-sbom", "--dists", "--dev-dists", "--exceptions"):
        p.add_argument(a, default="/nonexistent")
    p.set_defaults(fn=cmd_check)

    p = sp.add_parser("render-md"); p.add_argument("--sbom", required=True); p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_render_md)

    p = sp.add_parser("compare"); p.add_argument("a"); p.add_argument("b")
    p.set_defaults(fn=cmd_compare)

    args = ap.parse_args()
    rc = args.fn(args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
