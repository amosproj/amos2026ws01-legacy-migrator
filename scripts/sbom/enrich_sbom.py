#!/usr/bin/env python3
"""Enrich Syft SPDX packages and generate notices from installed package metadata."""
import concurrent.futures
import datetime as dt
import hashlib
import json, re, sys, subprocess, urllib.error, urllib.parse, urllib.request
from pathlib import Path
bom_path, py_meta_path, root, notices_path = map(Path, sys.argv[1:])
bom=json.loads(bom_path.read_text())
# Syft uses random document namespaces and wall-clock timestamps. Derive stable
# SPDX metadata from the locked dependency inputs for meaningful CI comparisons.
digest=hashlib.sha256((root/"backend/uv.lock").read_bytes()+(root/"frontend/package-lock.json").read_bytes()).hexdigest()
bom["documentNamespace"]="https://spdx.org/spdxdocs/SunsetTracker-"+digest
try:
    epoch=subprocess.run(["git","log","-1","--format=%ct","--","backend/uv.lock","frontend/package-lock.json"],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    created=dt.datetime.fromtimestamp(int(epoch or "0"),tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
except (OSError,subprocess.SubprocessError,ValueError):
    created="1970-01-01T00:00:00Z"
bom.setdefault("creationInfo",{})["created"]=created
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
    lic=meta.get("license"); pkg=root/"frontend"/path/"package.json"; texts={}
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
def npm_license(package):
    name=package.get("name", ""); version=package.get("versionInfo", "")
    encoded_name=urllib.parse.quote(name,safe="@")
    url="https://registry.npmjs.org/"+encoded_name+"/"+urllib.parse.quote(version,safe="")
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"SunsetTracker-SBOM/1.0","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=15) as response: data=json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        try:
            raw=subprocess.run(["curl","--fail","--silent","--show-error",url],check=True,capture_output=True,text=True,timeout=20).stdout
            data=json.loads(raw)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError): return None
    lic=data.get("license")
    if isinstance(lic,dict): lic=lic.get("type")
    if lic: return (lic,"npm registry","https://www.npmjs.com/package/"+name+"/v/"+version)
    repo=data.get("repository",{})
    repo=repo.get("url","") if isinstance(repo,dict) else str(repo)
    match=re.search(r"github\.com[:/]([^/]+)/([^/#.]+)",repo)
    if match:
        owner,project=match.groups()
        api="https://api.github.com/repos/"+owner+"/"+project+"/license"
        try:
            req=urllib.request.Request(api,headers={"User-Agent":"SunsetTracker-SBOM/1.0","Accept":"application/vnd.github+json"})
            with urllib.request.urlopen(req,timeout=15) as response: license_data=json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            try:
                raw=subprocess.run(["curl","--fail","--silent","--show-error","-H","Accept: application/vnd.github+json",api],check=True,capture_output=True,text=True,timeout=20).stdout
                license_data=json.loads(raw)
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError): return None
        spdx=(license_data.get("license") or {}).get("spdx_id")
        if spdx and spdx!="NOASSERTION":
            return (spdx,"upstream GitHub license API","https://github.com/"+owner+"/"+project+"/license")
    return None

def pypi_license(package):
    name=package.get("name", "")
    version=package.get("versionInfo", "")
    url="https://pypi.org/pypi/"+urllib.parse.quote(name,safe="")+"/"+urllib.parse.quote(version,safe="")+"/json"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"SunsetTracker-SBOM/1.0","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=15) as response: data=json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        # macOS Python installs can lack a configured CA bundle while curl uses
        # the system trust store. Keep TLS verification enabled via curl.
        try:
            raw=subprocess.run(["curl","--fail","--silent","--show-error",url],check=True,capture_output=True,text=True,timeout=20).stdout
            data=json.loads(raw)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None
    info=data.get("info",{})
    expression=info.get("license_expression")
    if expression: return (expression, "PyPI license_expression", url)
    # Prefer PyPI's OSI classifier over free-form legacy License text.
    classifier_map={
        "MIT License":"MIT", "BSD License":"BSD-3-Clause",
        "Apache Software License":"Apache-2.0", "ISC License (ISCL)":"ISC",
        "Mozilla Public License 2.0 (MPL 2.0)":"MPL-2.0",
        "GNU General Public License v3 (GPLv3)":"GPL-3.0-only",
        "GNU General Public License v2 (GPLv2)":"GPL-2.0-only",
        "GNU Affero General Public License v3":"AGPL-3.0-only",
    }
    for classifier in info.get("classifiers",[]):
        if classifier.startswith("License :: OSI Approved :: "):
            label=classifier.rsplit(" :: ",1)[-1]
            return (classifier_map.get(label,label), "PyPI OSI license classifier", url)
    legacy=(info.get("license") or "").strip()
    if legacy and len(legacy)<100 and "\n" not in legacy:
        return (legacy, "PyPI license field (review identifier)", url)
    return None

registry_targets=[p for p in bom.get("packages",[]) if ecosystem(p) in ("pypi","npm")]
registry_results={}
def lookup(package):
    return pypi_license(package) if ecosystem(package)=="pypi" else npm_license(package)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for package,result in zip(registry_targets,pool.map(lookup,registry_targets)):
        registry_results[(ecosystem(package),key(package.get("name","")))]=result

texts=[]
provenance={}
for p in bom.get("packages",[]):
    eco=ecosystem(p); normalized=key(p.get("name",""))
    # Keep stable package URLs, drop Syft's speculative CPE guesses.
    p["externalRefs"]=[r for r in p.get("externalRefs",[]) if r.get("referenceType")=="purl"]
    item=licenses.get((eco,normalized))
    source="installed package metadata"
    registry=registry_results.get((eco,normalized))
    if registry:
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
lines=["# Third-party legal notices","","Generated from sbom.spdx.json and package metadata. Review license terms before release.","","## Dependency licenses","","| Package | Version | License | Evidence |","|---|---:|---|---|"]
for p in sorted(bom.get("packages",[]),key=lambda x:(x.get("name","").lower(),x.get("versionInfo",""))):
    if p.get("name") in ("NOASSERTION",""): continue
    lic=p.get("licenseDeclared") or p.get("licenseConcluded") or "NOASSERTION"
    if lic in ("NOASSERTION", "NONE"): continue
    evidence=provenance.get((ecosystem(p),key(p.get("name",""))),"No registry/package license metadata found")
    lines.append("| "+p.get("name","Unknown").replace("|","\\|")+" | "+p.get("versionInfo","Unknown")+" | "+lic+" | "+evidence+" |")
lines += ["","## Included license and notice texts",""]
fence=chr(96)*3
for name,version,filename,content in sorted(texts):
    lines += ["### "+name+" "+version+" — "+filename,"",fence+"text",content.rstrip(),fence,""]
bom_path.write_text(json.dumps(bom,indent=2,ensure_ascii=False)+"\n")
notices_path.write_text("\n".join(lines).rstrip()+"\n")
