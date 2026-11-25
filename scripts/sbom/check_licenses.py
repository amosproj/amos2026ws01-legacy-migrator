#!/usr/bin/env python3
"""Fail if any dependency license is blocked, unresolved, or not an SPDX expression."""
import json
import re
import sys
from pathlib import Path
from license_metadata import normalize_license

# Common permissive software licenses. Copyleft, source-available, and custom
# licenses must be reviewed and explicitly added only after approval.
ALLOWED = {
    "MIT", "MIT-0", "ISC", "BSD-2-Clause", "BSD-3-Clause", "0BSD",
    "Apache-2.0", "Zlib", "BSL-1.0", "Unlicense", "CC0-1.0",
    "AFL-3.0", "Artistic-2.0", "BlueOak-1.0.0", "PostgreSQL",
    "Python-2.0", "PSF-2.0", "EPL-2.0", "WTFPL", "UPL-1.0", "MIT-CMU",
}
ALIASES = {"MIT License":"MIT","Apache License 2.0":"Apache-2.0"}
TOKEN = re.compile(r"\(|\)|\bAND\b|\bOR\b|\bWITH\b|[A-Za-z0-9][A-Za-z0-9.+-]*")
def allowed_expr(expr):
    expr=ALIASES.get(expr.strip(),expr.strip())
    if expr in ("NOASSERTION","NONE",""): return None
    tokens=TOKEN.findall(expr)
    if "".join(tokens)!=re.sub(r"\s+","",expr): return False
    pos=0
    def atom():
        nonlocal pos
        if pos>=len(tokens): raise ValueError()
        t=tokens[pos]; pos+=1
        if t=="(":
            value=ors()
            if pos>=len(tokens) or tokens[pos]!=")": raise ValueError()
            pos+=1
            return value
        if t in ("AND","OR","WITH",")"): raise ValueError()
        return t in ALLOWED
    def ands():
        nonlocal pos
        value=atom()
        while pos<len(tokens) and tokens[pos]=="AND":
            pos+=1
            right=atom()  # Consume the right operand even when value is false.
            value=value and right
        return value
    def ors():
        nonlocal pos
        value=ands()
        while pos<len(tokens) and tokens[pos]=="OR":
            pos+=1; right=ands(); value=value or right
        return value
    try:
        result=ors()
        return result if pos==len(tokens) else False
    except ValueError: return False

def main(path):
    bom=json.loads(Path(path).read_text())
    blocked=[]; unresolved=[]
    if isinstance(bom.get("@graph"), list):
        graph=bom["@graph"]
        elements={item.get("spdxId"):item for item in graph if item.get("spdxId")}
        licenses={}
        for relationship in graph:
            if relationship.get("type") != "Relationship":
                continue
            if str(relationship.get("relationshipType", "")).rsplit("/",1)[-1] != "hasConcludedLicense":
                continue
            targets=relationship.get("to", [])
            if not isinstance(targets,list): targets=[targets]
            for target in targets:
                license_node=elements.get(target,{})
                expression=license_node.get("simplelicensing_licenseExpression")
                if expression:
                    licenses[relationship.get("from")]=expression
        packages=[
            {"name":item.get("name","?"),"versionInfo":item.get("software_packageVersion",""),"SPDXID":item.get("spdxId"),"licenseDeclared":licenses.get(item.get("spdxId"),"NOASSERTION")}
            for item in graph if item.get("type")=="software_Package"
        ]
    else:
        packages=bom.get("packages",[])
    for p in packages:
        raw_lic=p.get("licenseDeclared") or p.get("licenseConcluded") or "NOASSERTION"
        lic=normalize_license(raw_lic)
        if not lic: unresolved.append((p.get("name","?"),p.get("versionInfo",""),raw_lic)); continue
        if not allowed_expr(lic): blocked.append((p.get("name","?"),p.get("versionInfo",""),lic))
    for name,version,lic in blocked: print(f"BLOCKED: {name} {version}: {lic}")
    for name,version,lic in unresolved: print(f"UNRESOLVED: {name} {version}: {lic}")
    print(f"License gate: {len(blocked)} blocked, {len(unresolved)} unresolved")
    if blocked or unresolved:
        print("Only approved permissive SPDX license expressions pass; unknown or ambiguous licenses must be resolved before merging.")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
