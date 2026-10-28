#!/usr/bin/env python3
"""Generate arc42 views (Context, Building Block L1, Deployment) from ONE view model
in three formats: Mermaid (+ Markdown tables), LikeC4, Structurizr DSL.

Usage: python generate.py [model.json] [outdir]
Deterministic: same model -> byte-identical output (sorted, no timestamps).
"""
import json
import sys
from pathlib import Path

STATUS_STYLE = {  # status -> (fill, stroke, label)
    "legacy": ("#d9d9d9", "#666666", "legacy"),
    "in-development": ("#ffd966", "#b38f00", "in development"),
    "target": ("#9fc5e8", "#1f5fa8", "target"),
    "decommissioned": ("#ffffff", "#999999", "decommissioned"),
}
GROUP_TITLE = {"legacy": "Legacy", "target": "Target", "data": "Data & messaging"}


def load(path):
    m = json.loads(Path(path).read_text())
    m["containers"].sort(key=lambda c: c["id"])
    m["actors"].sort(key=lambda a: a["id"])
    m["relationships"].sort(key=lambda r: (r["from"], r["to"]))
    return m


def esc(s):
    return s.replace('"', "'")


# ---------------------------------------------------------------- Mermaid + tables
def mermaid_context(m):
    s = m["system"]
    out = ["flowchart LR"]
    for a in m["actors"]:
        out.append(f'    {a["id"]}(["{esc(a["name"])}"])')
    out.append(f'    {s["id"]}["{esc(s["name"])}<br/><i>legacy + target landscape</i>"]')
    for e in m.get("external_systems", []):
        out.append(f'    {e["id"]}["{esc(e["name"])}"]:::external')
    ids = {c["id"] for c in m["containers"]}
    seen = set()
    for r in m["relationships"]:  # collapse container-level edges to system boundary
        f = s["id"] if r["from"] in ids else r["from"]
        t = s["id"] if r["to"] in ids else r["to"]
        if f != t and (f, t) not in seen:
            seen.add((f, t))
            out.append(f'    {f} -->|"{esc(r["label"])}"| {t}')
    out.append("    classDef external fill:#eeeeee,stroke:#999999,stroke-dasharray:4")
    return "\n".join(out)


def mermaid_classdefs():
    lines = []
    for st, (fill, stroke, _) in STATUS_STYLE.items():
        cls = st.replace("-", "_")
        dash = ",stroke-dasharray:5,color:#999999" if st == "decommissioned" else ""
        lines.append(f"    classDef {cls} fill:{fill},stroke:{stroke}{dash}")
    return lines


def node(c):
    label = f'{esc(c["name"])}<br/><i>{esc(c["tech"])}</i><br/>«{STATUS_STYLE[c["status"]][2]}»'
    shape = {"database": ('[("', '")]'), "queue": ('[["', '"]]')}.get(c.get("kind"), ('["', '"]'))
    return f'{c["id"]}{shape[0]}{label}{shape[1]}'


def mermaid_building_block(m):
    out = ["flowchart LR"]
    for a in m["actors"]:
        out.append(f'    {a["id"]}(["{esc(a["name"])}"])')
    for g in ("legacy", "target", "data"):
        out.append(f'    subgraph {g}_grp["{GROUP_TITLE[g]}"]')
        for c in m["containers"]:
            if c["group"] == g:
                out.append(f"        {node(c)}:::{c['status'].replace('-', '_')}")
        out.append("    end")
    for r in m["relationships"]:
        arrow = "-.->" if r.get("coupling") else "-->"
        out.append(f'    {r["from"]} {arrow}|"{esc(r["label"])}"| {r["to"]}')
    out += mermaid_classdefs()
    return "\n".join(out)


def mermaid_deployment(m):
    by_id = {c["id"]: c for c in m["containers"]}
    out = ["flowchart TB"]

    def walk(n, depth):
        pad = "    " * depth
        out.append(f'{pad}subgraph {n["id"]}["{esc(n["name"])}<br/><i>{esc(n["tech"])}</i>"]')
        for cid in sorted(n.get("instances", [])):
            c = by_id[cid]
            out.append(f"{pad}    {node(c)}:::{c['status'].replace('-', '_')}")
        for ch in n.get("children", []):
            walk(ch, depth + 1)
        out.append(f"{pad}end")

    for n in m["deployment"]["nodes"]:
        walk(n, 1)
    deployed = {i for n in _all_nodes(m) for i in n.get("instances", [])}
    for r in m["relationships"]:
        if r["from"] in deployed and r["to"] in deployed:
            arrow = "-.->" if r.get("coupling") else "-->"
            out.append(f'    {r["from"]} {arrow}|"{esc(r["tech"])}"| {r["to"]}')
    out += mermaid_classdefs()
    return "\n".join(out)


def _all_nodes(m):
    stack, res = list(m["deployment"]["nodes"]), []
    while stack:
        n = stack.pop()
        res.append(n)
        stack.extend(n.get("children", []))
    return res


def tables(m):
    names = {c["id"]: c["name"] for c in m["containers"]}
    names.update({a["id"]: a["name"] for a in m["actors"]})
    bb = ["| Building block | Technology | Status | Source |", "|---|---|---|---|"]
    for c in m["containers"]:
        bb.append(f'| {c["name"]} | {c["tech"]} | {STATUS_STYLE[c["status"]][2]} | `{c.get("source", "-")}` |')
    cp = ["| From | To | Interaction | Coupling |", "|---|---|---|---|"]
    for r in m["relationships"]:
        cp.append(f'| {names[r["from"]]} | {names[r["to"]]} | {r["label"]} ({r["tech"]}) | {r.get("coupling", "-")} |')
    return "\n".join(bb), "\n".join(cp)


def write_mermaid(m, out):
    d = out / "mermaid"
    d.mkdir(parents=True, exist_ok=True)
    bb_table, cp_table = tables(m)
    legend = "Legend: grey = legacy · amber = in development · blue = target · dashed = decommissioned · dotted arrow = coupling (shared data / messaging)"
    (d / "03_context.md").write_text(
        f"# 3. Context and Scope\n\n```mermaid\n{mermaid_context(m)}\n```\n\n"
        "| Partner | Interface |\n|---|---|\n"
        + "\n".join(f"| {a['name']} | {a['description']} |" for a in m["actors"]) + "\n")
    (d / "05_building_block.md").write_text(
        f"# 5. Building Block View (Level 1)\n\n{legend}\n\n```mermaid\n{mermaid_building_block(m)}\n```\n\n"
        f"{bb_table}\n\n## Coupling\n\n{cp_table}\n")
    (d / "07_deployment.md").write_text(
        f"# 7. Deployment View — {m['deployment']['environment']}\n\n{legend}\n\n```mermaid\n{mermaid_deployment(m)}\n```\n")


# ---------------------------------------------------------------- LikeC4
LIKEC4_COLOR = {"legacy": "gray", "in-development": "amber", "target": "primary", "decommissioned": "muted"}


def write_likec4(m, out):
    d = out / "likec4"
    d.mkdir(parents=True, exist_ok=True)
    s = m["system"]
    L = ["specification {",
         "  element actor { style { shape person } }",
         "  element system",
         "  element container",
         "  element database { style { shape storage } }",
         "  element queue { style { shape queue } }",
         "  deploymentNode environment",
         "  deploymentNode cluster",
         "  deploymentNode k8sNamespace"]
    for st in STATUS_STYLE:
        L.append(f"  tag {st.replace('-', '_')}")
    L += ["}", "", "model {"]
    for a in m["actors"]:
        L.append(f"  {a['id']} = actor '{a['name']}' {{ description '{a['description']}' }}")
    L.append(f"  {s['id']} = system '{s['name']}' {{")
    L.append(f"    description '{s['description']}'")
    for c in m["containers"]:
        kind = c.get("kind", "container")
        L.append(f"    {c['id']} = {kind} '{c['name']}' {{")
        L.append(f"      #{c['status'].replace('-', '_')}")
        L.append(f"      technology '{c['tech']}'")
        L.append("    }")
    L.append("  }")
    for r in m["relationships"]:
        f = r["from"] if r["from"] in {a["id"] for a in m["actors"]} else f"{s['id']}.{r['from']}"
        t = r["to"] if r["to"] in {a["id"] for a in m["actors"]} else f"{s['id']}.{r['to']}"
        L.append(f"  {f} -> {t} '{r['label']}' {{ technology '{r['tech']}' }}")
    L += ["}", "", "deployment {", "  environment prod {"]

    def walk(n, depth):
        pad = "  " * depth
        kind = "cluster" if n.get("children") else "k8sNamespace"
        L.append(f"{pad}{kind} {n['id']} '{n['name']}' {{")
        for cid in sorted(n.get("instances", [])):
            L.append(f"{pad}  instanceOf {s['id']}.{cid}")
        for ch in n.get("children", []):
            walk(ch, depth + 1)
        L.append(f"{pad}}}")

    for n in m["deployment"]["nodes"]:
        walk(n, 2)
    L += ["  }", "}", "", "views {"]
    styles = [f"    style element.tag = #{st.replace('-', '_')} {{ color {col} }}" for st, col in LIKEC4_COLOR.items()]
    L += ["  view context {", "    title '3. Context and Scope'", f"    include {s['id']}, *", "  }",
          f"  view building_block of {s['id']} {{", "    title '5. Building Block View (Level 1)'", "    include *"] + styles + ["  }",
          "  deployment view deployment {", "    title '7. Deployment View'", "    include prod.**", "  }", "}"]
    (d / "model.c4").write_text("\n".join(L) + "\n")


# ---------------------------------------------------------------- Structurizr DSL
def write_structurizr(m, out):
    d = out / "structurizr"
    d.mkdir(parents=True, exist_ok=True)
    s = m["system"]
    actors = {a["id"] for a in m["actors"]}
    L = ["workspace \"" + s["name"] + "\" \"Generated from the knowledge-graph view model\" {", "  !identifiers hierarchical", "  model {"]
    for a in m["actors"]:
        L.append(f'    {a["id"]} = person "{a["name"]}" "{a["description"]}"')
    L.append(f'    {s["id"]} = softwareSystem "{s["name"]}" "{s["description"]}" {{')
    for c in m["containers"]:
        extra = {"database": ",Database", "queue": ",Queue"}.get(c.get("kind"), "")
        L.append(f'      {c["id"]} = container "{c["name"]}" "" "{c["tech"]}" "{c["status"]}{extra}"')
    L.append("    }")
    for r in m["relationships"]:
        f = r["from"] if r["from"] in actors else f"{s['id']}.{r['from']}"
        t = r["to"] if r["to"] in actors else f"{s['id']}.{r['to']}"
        tag = f' "{r["coupling"]}"' if r.get("coupling") else ""
        L.append(f'    {f} -> {t} "{r["label"]}" "{r["tech"]}"{tag}')
    L.append(f'    prod = deploymentEnvironment "{m["deployment"]["environment"]}" {{')

    def walk(n, depth):
        pad = "  " * depth
        L.append(f'{pad}deploymentNode "{n["name"]}" "" "{n["tech"]}" {{')
        for cid in sorted(n.get("instances", [])):
            L.append(f"{pad}  containerInstance {s['id']}.{cid}")
        for ch in n.get("children", []):
            walk(ch, depth + 1)
        L.append(f"{pad}}}")

    for n in m["deployment"]["nodes"]:
        walk(n, 3)
    L += ["    }", "  }", "  views {",
          f'    systemContext {s["id"]} "context" "3. Context and Scope" {{', "      include *", "      autoLayout lr", "    }",
          f'    container {s["id"]} "building_block" "5. Building Block View (Level 1)" {{', "      include *", "      autoLayout lr", "    }",
          f'    deployment {s["id"]} prod "deployment" "7. Deployment View" {{', "      include *", "      autoLayout tb", "    }",
          "    styles {",
          '      element "Person" { shape Person }',
          '      element "Database" { shape Cylinder }',
          '      element "Queue" { shape Pipe }']
    for st, (fill, stroke, _) in STATUS_STYLE.items():
        border = "dashed" if st == "decommissioned" else "solid"
        L.append(f'      element "{st}" {{ background {fill} stroke {stroke} color #000000 border {border} }}')
    L += ['      relationship "shared-data" { style dotted color #c2410c }',
          '      relationship "messaging" { style dashed color #c2410c }',
          "    }", "  }", "}"]
    (d / "workspace.dsl").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    model = load(sys.argv[1] if len(sys.argv) > 1 else "model/views.json")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    write_mermaid(model, out)
    write_likec4(model, out)
    write_structurizr(model, out)
    print(f"generated into {out}/ (mermaid, likec4, structurizr)")
