#!/usr/bin/env python3
"""Compare generated SPDX JSON while ignoring its informational creation time."""
import difflib
import json
import sys
from pathlib import Path

left_path, right_path = map(Path, sys.argv[1:3])
left = json.loads(left_path.read_text())
right = json.loads(right_path.read_text())
for doc in (left, right):
    doc.get("creationInfo", {}).pop("created", None)
if left == right:
    print("SBOM matches (ignoring creationInfo.created).")
    raise SystemExit(0)
left_text = json.dumps(left, indent=2, ensure_ascii=False).splitlines()
right_text = json.dumps(right, indent=2, ensure_ascii=False).splitlines()
sys.stdout.writelines(difflib.unified_diff(left_text, right_text, fromfile=str(left_path), tofile=str(right_path), lineterm="\n"))
raise SystemExit(1)
