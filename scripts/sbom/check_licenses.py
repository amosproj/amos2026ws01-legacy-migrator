#!/usr/bin/env python3
"""Fail if the SPDX SBOM contains a license outside the permissive allowlist."""
import json
import re
import sys
from pathlib import Path

# Common permissive software licenses. Copyleft, source-available, and custom
# licenses must be reviewed and explicitly added only after approval.
ALLOWED = {
    "MIT", "MIT-0", "ISC", "BSD-2-Clause", "BSD-3-Clause", "0BSD",
    "Apache-2.0", "Zlib", "BSL-1.0", "Unlicense", "CC0-1.0",
    "AFL-3.0", "Artistic-2.0", "BlueOak-1.0.0", "PostgreSQL",
    "Python-2.0", "PSF-2.0", "WTFPL", "UPL-1.0", "MIT-CMU",
}
ALIASES = {"MIT License":"MIT","BSD License":"BSD-3-Clause","BSD":"BSD-3-Clause","Apache License 2.0":"Apache-2.0"}
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
            pos+=1; value=value and atom()
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

bom=json.loads(Path(sys.argv[1]).read_text())
blocked=[]; unresolved=[]
for p in bom.get("packages",[]):
    lic=p.get("licenseDeclared") or p.get("licenseConcluded") or "NOASSERTION"
    if lic in ("NOASSERTION","NONE"): unresolved.append((p.get("name","?"),p.get("versionInfo",""),lic)); continue
    if not allowed_expr(lic): blocked.append((p.get("name","?"),p.get("versionInfo",""),lic))
for name,version,lic in blocked: print(f"BLOCKED: {name} {version}: {lic}")
for name,version,lic in unresolved: print(f"UNRESOLVED: {name} {version}: {lic}")
print(f"License gate: {len(blocked)} blocked, {len(unresolved)} unresolved")
if blocked:
    print("Only approved permissive SPDX license expressions pass. Review the package license and update the SBOM before merging.")
    sys.exit(1)
