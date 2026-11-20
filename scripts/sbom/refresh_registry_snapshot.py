#!/usr/bin/env python3
"""Refresh missing npm/PyPI license records for Syft SPDX packages."""
import datetime as dt, hashlib, json, sys, urllib.parse, urllib.request, os
from pathlib import Path

root=Path(__file__).resolve().parents[2]
def norm(s):
 import re
 return re.sub(r'[-_.]+','-',s or '').lower()
bom=json.loads(Path(sys.argv[1]).read_text())
py_meta=json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv)>2 else {}
pkg_lock=json.loads((root/'frontend/package-lock.json').read_text())
local=set()
for n,m in py_meta.items():
 if m.get('license_expression') or m.get('license') or m.get('classifiers'): local.add(('pypi',norm(n),m.get('version')))
for path,m in pkg_lock.get('packages',{}).items():
 if not path.startswith('node_modules/'): continue
 n=m.get('name') or path.rsplit('node_modules/',1)[-1]
 if '/node_modules/' in n: n=n.rsplit('/node_modules/',1)[-1]
 license=m.get('license')
 installed=Path(os.environ.get('SBOM_FRONTEND_NODE_MODULES',str(root/'frontend/node_modules')))/path.removeprefix('node_modules/')/'package.json'
 if installed.is_file():
  try: license=json.loads(installed.read_text()).get('license',license)
  except (OSError,json.JSONDecodeError): pass
 if license: local.add(('npm',norm(n),m.get('version')))
path=root/'scripts/sbom/registry-license-snapshot.json'
snapshot=json.loads(path.read_text()) if path.exists() else {'schemaVersion':1,'packages':{}}
for p in bom.get('packages',[]):
 refs=[r.get('referenceLocator','') for r in p.get('externalRefs',[]) if r.get('referenceType')=='purl']
 eco='pypi' if any(x.startswith('pkg:pypi/') for x in refs) else 'npm' if any(x.startswith('pkg:npm/') for x in refs) else None
 if not eco: continue
 name,ver=p.get('name',''),p.get('versionInfo','')
 if (eco,norm(name),ver) in local: continue
 key=f'{eco}:{norm(name)}@{ver}'
 if key in snapshot['packages'] or p.get('licenseDeclared') not in (None,'NOASSERTION','NONE'): continue
 url=(f'https://pypi.org/pypi/{urllib.parse.quote(name,safe="")}/{urllib.parse.quote(ver,safe="")}/json' if eco=='pypi' else f'https://registry.npmjs.org/{urllib.parse.quote(name,safe="@")}/{urllib.parse.quote(ver,safe="")}')
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'AMOS-SBOM/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=20) as r: raw=r.read()
  data=json.loads(raw); info=data.get('info',{}) if eco=='pypi' else data
  lic=info.get('license_expression') or info.get('license')
  if isinstance(lic,dict): lic=lic.get('type')
  source=url
  if not lic and eco=='pypi':
   m={'MIT License':'MIT','BSD License':'BSD-3-Clause','Apache Software License':'Apache-2.0','ISC License (ISCL)':'ISC'}
   for c in info.get('classifiers',[]):
    if c.startswith('License :: OSI Approved :: '): lic=m.get(c.rsplit(' :: ',1)[-1]); break
  if lic:
   snapshot['packages'][key]={'license':lic,'source':'PyPI registry' if eco=='pypi' else 'npm registry','sourceUrl':source,'retrievedAt':dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'responseSha256':hashlib.sha256(raw).hexdigest()}
   print('snapshotted',key)
 except Exception as e: print(f'lookup failed for {key}: {e}',file=sys.stderr)
path.write_text(json.dumps(snapshot,indent=2,sort_keys=True)+'\n')
