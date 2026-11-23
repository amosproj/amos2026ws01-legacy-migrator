"""Command line: load a reference stage and extract graphs and canonical facts per component."""

import argparse
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from neo4j.exceptions import DriverError, Neo4jError
from pydantic import ValidationError

from migration_assistant.api import ingest_step, persist_handoff
from migration_assistant.domain.checkout import CheckoutError
from migration_assistant.domain.pipeline import PipelineError
from migration_assistant.domain.reference_source import (
    ConfigError,
    ReferenceSourceConfig,
    default_config_path,
    load_config,
)
from migration_assistant.domain.sources import LoadResult

EXIT_ERROR = 1
EXIT_UNEXPECTED = 2
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / ".cache" / "ingestion"


def run_full_ingestion(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return _execute(args, _run_full_ingestion)


def run_persistence_from_handoff(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="persist-handoff", description="Persist a saved canonical handoff to Neo4j."
    )
    parser.add_argument(
        "--handoff-dir", type=Path, required=True, help="existing ingestion run folder"
    )
    parser.add_argument("--verbose", action="store_true", help="show the full traceback on errors")
    return _execute(parser.parse_args(argv), _persist_from_handoff)


def _execute(args: argparse.Namespace, action: Callable[[argparse.Namespace], None]) -> int:
    try:
        action(args)
    except (
        ConfigError,
        CheckoutError,
        PipelineError,
        DriverError,
        Neo4jError,
        OSError,
        KeyboardInterrupt,
    ) as error:
        if args.verbose:
            traceback.print_exc()
        message = " ; ".join(str(error).splitlines()) or "Interrupted"
        print(f"ERROR: {message}", file=sys.stderr)
        return EXIT_ERROR
    except Exception:
        if args.verbose:
            traceback.print_exc()
        print("ERROR: unexpected failure, rerun with --verbose", file=sys.stderr)
        return EXIT_UNEXPECTED
    return 0


def _persist_from_handoff(args: argparse.Namespace) -> None:
    handoff = persist_handoff(args.handoff_dir)
    print(
        f"Success. Persisted snapshot {handoff.snapshot_id}: "
        f"{handoff.entity_count} entities, {handoff.relationship_count} relationships"
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ingest",
        description="Load a reference stage and generate graphs and canonical facts per component.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="config file (default: config/reference-source.local.yaml if it exists, "
        "otherwise config/reference-source.yaml)",
    )
    parser.add_argument("--stage", help="override the stage for this run")
    parser.add_argument("--components", nargs="+", help="override the components for this run")
    parser.add_argument("--out", type=Path, help="write the loaded files as JSONL")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="parent directory for timestamped runs (default: .cache/ingestion in this subproject)",
    )
    parser.add_argument("--verbose", action="store_true", help="show the full traceback on errors")
    return parser.parse_args(argv)


def _run_full_ingestion(args: argparse.Namespace) -> None:
    config_path = args.config or default_config_path()
    config = _with_overrides(load_config(config_path), args)

    def on_loaded(loaded: LoadResult) -> None:
        print(f"config: {Path(config_path).as_posix()}")
        _print_loaded(loaded)

    result = ingest_step(
        config,
        args.output_dir,
        source_export=args.out,
        on_loaded=on_loaded,
        progress=lambda message: print(message, flush=True),
    )
    if args.out is not None:
        print(f"output: {args.out}")
    print(
        f"Graph handoff: {result.entity_count} entities, {result.relationship_count} relationships"
    )
    print(f"Success. Graphs: {result.run_directory / 'graphs'}")


def _print_loaded(result: LoadResult) -> None:
    checkout = result.checkout
    print(f"stage: {checkout.stage}")
    print(f"umbrella: {checkout.umbrella_ref} {checkout.umbrella_commit_sha}")
    for member in checkout.members:
        print(f"component: {member.repo_id} {member.commit_sha}")
    print(f"files loaded: {result.counts.loaded}")
    for language, count in result.counts.loaded_by_language.items():
        print(f"  {language}: {count}")
    print(f"files skipped: {result.counts.skipped}")
    for reason, count in result.counts.skipped_by_reason.items():
        print(f"  {reason}: {count}")


def _with_overrides(
    config: ReferenceSourceConfig, args: argparse.Namespace
) -> ReferenceSourceConfig:
    overrides = {}
    if args.stage is not None:
        overrides["stage"] = args.stage
    if args.components is not None:
        overrides["components"] = args.components
    if not overrides:
        return config
    try:
        return ReferenceSourceConfig.model_validate({**config.model_dump(), **overrides})
    except ValidationError as error:
        problems = [
            f"Invalid value for option '{'.'.join(str(p) for p in problem['loc'])}': "
            f"{problem['msg']}"
            for problem in error.errors()
        ]
        raise ConfigError("\n".join(problems)) from error


if __name__ == "__main__":
    sys.exit(run_full_ingestion())
