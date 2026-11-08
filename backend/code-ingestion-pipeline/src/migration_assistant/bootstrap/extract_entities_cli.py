"""CLI to extract code entities from loaded sources or mock input (Issue #19).

Usage:
  python -m migration_assistant.bootstrap.extract_entities_cli --sources sources.jsonl --out entities.jsonl
  python -m migration_assistant.bootstrap.extract_entities_cli --mock mock_entities.json --out entities.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from migration_assistant.adapters.extraction.code_entity_extractor import (
    CodeEntityExtractor,
)
from migration_assistant.domain.sources import SourceFile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m migration_assistant.bootstrap.extract_entities_cli",
        description="Extract code entities into canonical graph fact JSONL (Issue #19).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--sources",
        type=Path,
        help="path to sources.jsonl file produced by bootstrap",
    )
    group.add_argument(
        "--mock",
        type=Path,
        help="path to JSON file containing predefined/mock parser entity records",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="destination path for canonical entities JSONL output",
    )
    parser.add_argument(
        "--snapshot-id",
        type=str,
        default="snapshot-default",
        help="snapshot identifier scoping the extracted entity facts",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print detailed tracebacks on errors",
    )

    args = parser.parse_args(argv)
    try:
        extractor = CodeEntityExtractor()
        if args.sources:
            if not args.sources.is_file():
                raise FileNotFoundError(f"Sources file not found: {args.sources}")
            sources: list[SourceFile] = []
            with args.sources.open("r", encoding="utf-8") as handle:
                for line_num, line in enumerate(handle, 1):
                    cleaned = line.strip()
                    if not cleaned:
                        continue
                    try:
                        sources.append(SourceFile.model_validate_json(cleaned))
                    except Exception as err:
                        raise ValueError(f"Invalid JSON at line {line_num} in {args.sources}: {err}") from err

            result = extractor.extract_from_sources(sources, args.snapshot_id)
        else:
            if not args.mock.is_file():
                raise FileNotFoundError(f"Mock records file not found: {args.mock}")
            with args.mock.open("r", encoding="utf-8") as handle:
                mock_data = json.load(handle)
                if not isinstance(mock_data, list):
                    raise ValueError(f"Mock input in {args.mock} must be a JSON array")
            result = extractor.extract_from_mock(mock_data, args.snapshot_id)

        # Write canonical JSONL output
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            for line in result.to_jsonl_lines():
                handle.write(line + "\n")

        print(f"Extracted {result.summary.total_entities} entities from {result.summary.files_scanned} files.")
        for kind, count in result.summary.counts_by_kind.items():
            print(f"  {kind}: {count}")
        print(f"Output saved to: {args.out}")
        return 0

    except Exception as error:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
