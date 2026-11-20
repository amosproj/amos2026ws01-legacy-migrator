#!/usr/bin/env python3
"""Validate required SBOM metadata and report unresolved supplier/hash data."""
import json, sys
from collections import defaultdict
from pathlib import Path

bom=json.loads(Path(sys.argv[1]).read_text())
errors=[]; reviews=[]; ci=bom.get('creationInfo',{})
if not any(x.startswith('Organization: AMOS Project') for x in ci.get('creators',[])):
    errors.append('missing SBOM author Organization: AMOS Project')
if not ci.get('created'): errors.append('missing SBOM timestamp')
packages=bom.get('packages',[]); ids={p.get('SPDXID') for p in packages}
ids.update(f.get('SPDXID') for f in bom.get('files',[]))
for p in packages:
    name=p.get('name','?'); pid=p.get('SPDXID')
    for field in ('name','versionInfo','SPDXID'):
        if not p.get(field) or (field=='versionInfo' and p[field].lower() in ('unversioned','unknown')):
            errors.append(f'{name}: missing or invalid {field}')
    if pid and not any(r.get('referenceType')=='purl' for r in p.get('externalRefs',[])):
        errors.append(f'{name}: missing PURL identifier')
    version=p.get('versionInfo','')
    if p.get('supplier') in (None,'NOASSERTION'): reviews.append(('supplier unresolved',f'{name} {version}'))
    if not p.get('checksums'): reviews.append(('artifact checksum unavailable',f'{name} {version}'))
    if p.get('licenseDeclared') in (None,'NOASSERTION','NONE'): reviews.append(('license unresolved',f'{name} {version}'))
rels=bom.get('relationships',[])
if not rels: errors.append('missing component relationships')
for r in rels:
    if r.get('spdxElementId')!='SPDXRef-DOCUMENT' and r.get('spdxElementId') not in ids:
        errors.append(f"relationship has unknown source: {r.get('spdxElementId')}")
    if r.get('relatedSpdxElement')!='SPDXRef-DOCUMENT' and r.get('relatedSpdxElement') not in ids:
        errors.append(f"relationship has unknown target: {r.get('relatedSpdxElement')}")
groups=defaultdict(list)
for category,name in reviews: groups[category].append(name)
for category,names in sorted(groups.items()):
    print(f'REVIEW: {category}: {len(names)} package(s); examples: '+', '.join(names[:8]))
for msg in errors: print('ERROR:',msg)
print(f'Completeness: {len(packages)} packages, {len(errors)} errors, {len(reviews)} review items')
sys.exit(bool(errors))
