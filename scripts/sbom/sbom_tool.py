#!/usr/bin/env python3
"""Collect installed Python distribution metadata for SPDX enrichment."""
from __future__ import annotations

import argparse
import json
import re
from importlib import metadata
from pathlib import Path


LICENCE_FILE_RE = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors|copyright)([.\-_][^/]*)?$", re.I)


def norm_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def inspect_dists(output: Path) -> None:
    result = {}
    for distribution in metadata.distributions():
        package_metadata = distribution.metadata
        name = package_metadata.get("Name")
        if not name:
            continue
        files = [str(path) for path in (distribution.files or [])]
        license_files = sorted({
            path for path in files
            if LICENCE_FILE_RE.search(path) and (".dist-info/" in path or "/licenses/" in path)
        })
        texts = {}
        for relative_path in license_files[:20]:
            try:
                content = Path(distribution.locate_file(relative_path)).read_text(
                    encoding="utf-8", errors="replace"
                )
                filename = relative_path.split("/licenses/")[-1].split("/")[-1]
                texts[filename] = content[:200_000]
            except OSError:
                continue
        key = norm_name(name)
        result[key] = {
            "name": name,
            "version": package_metadata.get("Version"),
            "author": (package_metadata.get("Author") or "").strip() or None,
            "author_email": (package_metadata.get("Author-email") or "").strip() or None,
            "maintainer": (package_metadata.get("Maintainer") or "").strip() or None,
            "maintainer_email": (package_metadata.get("Maintainer-email") or "").strip() or None,
            "home_page": (package_metadata.get("Home-page") or "").strip() or None,
            "license_expression": package_metadata.get("License-Expression"),
            "license": (package_metadata.get("License") or "").strip()[:500] or None,
            "classifiers": sorted(
                classifier for classifier in package_metadata.get_all("Classifier", [])
                if classifier.startswith("License ::")
            ),
            "requires_dist": package_metadata.get_all("Requires-Dist", []),
            "license_file_headers": package_metadata.get_all("License-File", []),
            "licence_files": texts,
        }
    output.write_text(json.dumps(dict(sorted(result.items())), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect-dists")
    inspect_parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    inspect_dists(arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
