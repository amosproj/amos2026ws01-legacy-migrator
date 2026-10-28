#!/bin/sh
# Change test: retire one component in the model, regenerate, show the diff.
# Expectation: only that element's lines change, in every format.
set -e
ID=${1:-monolith_liberty}
python3 - "$ID" <<'PY'
import json, sys
m = json.load(open("model/views.json"))
for c in m["containers"]:
    if c["id"] == sys.argv[1]:
        c["status"] = "decommissioned"
json.dump(m, open("/tmp/views_changed.json", "w"), indent=2)
PY
python3 generate.py /tmp/views_changed.json /tmp/out_changed >/dev/null
diff -r out /tmp/out_changed || true
echo "changed lines: $(diff -r out /tmp/out_changed | grep -c '^[<>]' || true)"
rm -rf /tmp/out_changed /tmp/views_changed.json
