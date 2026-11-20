#!/usr/bin/env python3
"""Enrich Syft SPDX packages and generate notices from installed package metadata."""
import datetime as dt
import hashlib
import json, os, re, sys, tomllib, base64
from pathlib import Path
bom_path, py_meta_path, root, notices_path = map(Path, sys.argv[1:])
bom=json.loads(bom_path.read_text())
# Syft uses random document namespaces and wall-clock timestamps. Derive stable
# SPDX metadata from the locked dependency inputs for meaningful CI comparisons.
digest=hashlib.sha256((root/"backend/uv.lock").read_bytes()+(root/"frontend/package-lock.json").read_bytes()).hexdigest()
bom["documentNamespace"]="https://spdx.org/spdxdocs/SunsetTracker-"+digest
created=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
bom.setdefault("creationInfo",{})["created"]=created
creation_info=bom["creationInfo"]
# Syft identifies the generator as a Tool creator. Record the project that
# prepared this SBOM separately, without removing Syft's attribution.
creators=creation_info.setdefault("creators",[])
project_creator="Organization: AMOS Project"
if project_creator not in creators:
    creators.append(project_creator)
def key(s): return re.sub(r"[-_.]+","-",s or "").lower()
licenses={}
py=json.loads(py_meta_path.read_text())
for k,v in py.items():
    lic=v.get("license_expression") or v.get("license")
    if not lic:
        for c in v.get("classifiers",[]):
            if c.startswith("License :: OSI Approved :: "): lic=c.rsplit(" :: ",1)[-1]
    if lic: licenses[("pypi",k)]=(lic,v.get("licence_files",{}))
lock=json.loads((root/"frontend/package-lock.json").read_text())
for path,meta in lock.get("packages",{}).items():
    if not path.startswith("node_modules/"): continue
    name=meta.get("name") or path.rsplit("/",1)[-1]
    lic=meta.get("license"); pkg=Path(os.environ.get("SBOM_FRONTEND_NODE_MODULES", str(root/"frontend/node_modules")))/path.removeprefix("node_modules/")/"package.json"; texts={}
    if pkg.exists():
        try:
            md=json.loads(pkg.read_text()); lic=md.get("license",lic)
            for f in ("LICENSE","LICENCE","NOTICE","COPYING"):
                fp=pkg.parent/f
                if fp.is_file(): texts[fp.name]=fp.read_text(errors="replace")
        except (OSError,json.JSONDecodeError): pass
    if lic: licenses[("npm",key(name))]=(lic,texts)
def ecosystem(p):
    for ref in p.get("externalRefs",[]):
        val=ref.get("referenceLocator","")
        if ref.get("referenceType")=="purl":
            if val.startswith("pkg:pypi/"): return "pypi"
            if val.startswith("pkg:npm/"): return "npm"
    return None
snapshot_path=root/"scripts/sbom/registry-license-snapshot.json"
snapshot=json.loads(snapshot_path.read_text()) if snapshot_path.exists() else {"schemaVersion":1,"packages":{}}
registry_results={}
for package in bom.get("packages",[]):
    eco=ecosystem(package); k=key(package.get("name","")); version=package.get("versionInfo","")
    entry=snapshot.get("packages",{}).get(f"{eco}:{k}@{version}") if eco else None
    if entry and entry.get("license"):
        registry_results[(eco,k,version)]=(entry["license"],entry.get("source","registry snapshot"),entry.get("sourceUrl",""))

# Locked artifact hashes are stronger identifiers than a package name/version.
checksums={}
uv=tomllib.loads((root/"backend/uv.lock").read_text())
for item in uv.get("package",[]):
    name,version=item.get("name"),item.get("version")
    if not name or not version: continue
    vals=[]
    for artifact in ([item.get("sdist")] if item.get("sdist") else [])+item.get("wheels",[]):
        h=artifact.get("hash","")
        if h.startswith("sha256:"): vals.append(("SHA256",h.split(":",1)[1]))
    checksums[("pypi",key(name),version)]=sorted(set(vals))
for path,meta in lock.get("packages",{}).items():
    if path.startswith("node_modules/") and meta.get("integrity"):
        name=meta.get("name")
        if not name:
            name=path.rsplit("node_modules/",1)[-1]
            if "/node_modules/" in name: name=name.rsplit("/node_modules/",1)[-1]
        vals=[]
        for token in meta["integrity"].split():
            if "-" in token:
                alg,encoded=token.split("-",1); algorithm={"sha256":"SHA256","sha384":"SHA384","sha512":"SHA512"}.get(alg.lower())
                if algorithm:
                    try: vals.append((algorithm,base64.b64decode(encoded.split("?",1)[0]).hex()))
                    except (ValueError,base64.binascii.Error): pass
        checksums[("npm",key(name),meta.get("version",""))]=sorted(set(vals))

texts=[]
provenance={}
for p in bom.get("packages",[]):
    eco=ecosystem(p); normalized=key(p.get("name",""))
    # Keep stable package URLs, drop Syft's speculative CPE guesses.
    p["externalRefs"]=[r for r in p.get("externalRefs",[]) if r.get("referenceType")=="purl"]
    item=licenses.get((eco,normalized))
    source="installed package metadata"
    registry=registry_results.get((eco,normalized,p.get("versionInfo","")))
    if registry and not item:
        item=(registry[0],(item[1] if item else {}))
        source=registry[1]+" — "+registry[2]
    if not item and (normalized in ("sunsettracker", "sunsettracker-backend")):
        item=("MIT", {})
        source="repository LICENSE"
    if item:
        p["licenseDeclared"]=item[0]
        p["licenseConcluded"]="NOASSERTION"
        p["licenseInfoInFiles"]=[item[0]]
        provenance[(eco,normalized)]=source
        for fname,content in item[1].items(): texts.append((p.get("name",""),p.get("versionInfo",""),fname,content))
    if normalized in ("sunsettracker", "sunsettracker-backend"):
        p["supplier"]="Organization: AMOS Project"
        if not any(r.get("referenceType")=="purl" for r in p.get("externalRefs",[])):
            p.setdefault("externalRefs",[]).append({"referenceCategory":"PACKAGE-MANAGER","referenceType":"purl","referenceLocator":"pkg:generic/sunsettracker@"+p.get("versionInfo","0.1.0")})
    vals=checksums.get((eco,normalized,p.get("versionInfo","")),[])
    if vals: p["checksums"]=[{"algorithm":a,"checksumValue":v} for a,v in vals]
# Merge explicitly inventoried materials that cannot be discovered from lockfiles.
manual_file=root/"scripts/sbom/manual-components.json"
manual=json.loads(manual_file.read_text())
if manual.get("schemaVersion") != 1 or not isinstance(manual.get("components"), list):
    raise SystemExit("manual-components.json must have schemaVersion: 1 and a components array")
manual_evidence={}
seen_purls=set()
for c in manual["components"]:
    required=("name","version","kind","scope","purl","license","evidenceUrl")
    missing=[field for field in required if not isinstance(c.get(field),str) or not c[field].strip()]
    if missing: raise SystemExit("manual component missing required fields: "+", ".join(missing))
    if c["kind"] not in ("container-image","tool","external-service","model","other"):
        raise SystemExit("invalid kind for manual component "+c["name"])
    if c["scope"] not in ("runtime","build","development","test","external-service"):
        raise SystemExit("invalid scope for manual component "+c["name"])
    if not c["purl"].startswith("pkg:"):
        raise SystemExit("manual component purl must start with pkg: "+c["name"])
    if not c["evidenceUrl"].startswith(("https://","http://")):
        raise SystemExit("manual component evidenceUrl must be an http(s) URL: "+c["name"])
    if c["kind"]=="container-image" and not re.search(r"@sha256:[0-9a-f]{64}$",c.get("imageRef","")):
        raise SystemExit("container-image entries must pin imageRef by sha256 digest: "+c["name"])
    if c["purl"] in seen_purls: raise SystemExit("duplicate manual component purl: "+c["purl"])
    seen_purls.add(c["purl"])
    if any(r.get("referenceLocator")==c["purl"] for pkg in bom.get("packages",[]) for r in pkg.get("externalRefs",[])):
        raise SystemExit("manual component already appears in scanned SBOM: "+c["purl"])
    package_id="SPDXRef-Package-Manual-"+hashlib.sha256(c["purl"].encode()).hexdigest()[:16]
    lic=c["license"]
    source="Manual inventory (scripts/sbom/manual-components.json); scope="+c["scope"]+"; kind="+c["kind"]+"; evidence="+c["evidenceUrl"]+("; image="+c["imageRef"] if c.get("imageRef") else "")
    pkg={
        "name":c["name"],"SPDXID":package_id,"versionInfo":c["version"],
        "supplier":c.get("supplier","NOASSERTION"),
        "downloadLocation":c.get("downloadLocation","NOASSERTION"),
        "filesAnalyzed":False,"sourceInfo":source,
        "licenseConcluded":"NOASSERTION","licenseDeclared":lic,
        "copyrightText":"NOASSERTION",
        "externalRefs":[{"referenceCategory":"PACKAGE-MANAGER","referenceType":"purl","referenceLocator":c["purl"]}],
        "packageComment":"Inventory scope: "+c["scope"]+"; kind: "+c["kind"]+("; image: "+c["imageRef"] if c.get("imageRef") else "")+("; "+c["notes"] if c.get("notes") else "")
    }
    if c["kind"]=="container-image": pkg["primaryPackagePurpose"]="CONTAINER"
    bom.setdefault("packages",[]).append(pkg)
    bom.setdefault("relationships",[]).append({"spdxElementId":"SPDXRef-DOCUMENT","relationshipType":"DESCRIBES","relatedSpdxElement":package_id})
    manual_evidence[package_id]=source
    license_path=c.get("licenseTextFile")
    if license_path:
        text_path=(root/license_path).resolve()
        if root.resolve() not in text_path.parents or not text_path.is_file():
            raise SystemExit("licenseTextFile must reference a file inside the repository: "+license_path)
        texts_content=text_path.read_text(encoding="utf-8",errors="replace")
        texts.append((c["name"],c["version"],license_path,texts_content))

lines=["# Third-party legal notices","","Generated from sbom.spdx.json and package metadata. Review license terms before release.","","## Dependency licenses","","| Package | Version | License | Evidence |","|---|---:|---|---|"]
for p in sorted(bom.get("packages",[]),key=lambda x:(x.get("name","").lower(),x.get("versionInfo",""))):
    if p.get("name") in ("NOASSERTION",""): continue
    lic=p.get("licenseDeclared") or p.get("licenseConcluded") or "NOASSERTION"
    if lic in ("NOASSERTION", "NONE"): continue
    evidence=manual_evidence.get(p.get("SPDXID"),provenance.get((ecosystem(p),key(p.get("name",""))),"No registry/package license metadata found"))
    lines.append("| "+p.get("name","Unknown").replace("|","\\|")+" | "+p.get("versionInfo","Unknown")+" | "+lic+" | "+evidence+" |")
lines += ["","## Included license and notice texts",""]
fence=chr(96)*3
for name,version,filename,content in sorted(texts):
    lines += ["### "+name+" "+version+" — "+filename,"",fence+"text",content.rstrip(),fence,""]
bom_path.write_text(json.dumps(bom,indent=2,ensure_ascii=False)+"\n")
notices_path.write_text("\n".join(lines).rstrip()+"\n")
