"""Command line: load a reference stage and extract graphs and canonical facts per component.

Run from code-ingestion-pipeline/ with: uv run --project .. ingest
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

from neo4j import GraphDatabase
from pydantic import ValidationError

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.adapters.outbound.graphify import GraphifyAdapter
from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff
from migration_assistant.adapters.outbound.neo4j import Neo4jPersistenceWriter
from migration_assistant.adapters.outbound.pipeline_storage import LocalPipelineStorage
from migration_assistant.application.pipeline import PipelineService
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        _run(args)
    except (ConfigError, CheckoutError, PipelineError, OSError, KeyboardInterrupt) as error:
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


def _run(args: argparse.Namespace) -> None:
    config_path = args.config or default_config_path()
    config = _with_overrides(load_config(config_path), args)

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")

    with GraphDatabase.driver(uri, auth=("neo4j", "change-this")) as driver:
        driver.verify_connectivity()
        writer = Neo4jPersistenceWriter(driver)

        service = PipelineService(
            git_repo=LocalGitAdapter(),
            source_loader=load_sources,
            graph_builder=GraphifyAdapter(),
            handoff_writer=write_relationship_handoff,
            storage=LocalPipelineStorage(),
            persistence_writer=writer,
        )

        def on_loaded(loaded: LoadResult) -> None:
            print(f"config: {Path(config_path).as_posix()}")
            _print_loaded(loaded)

        result = service.run(
            config,
            args.output_dir,
            source_export=args.out,
            on_loaded=on_loaded,
            progress=lambda message: print(message, flush=True),
        )
        if args.out is not None:
            print(f"output: {args.out}")
        print(
            f"Graph handoff: {result.entity_count} entities, "
            f"{result.relationship_count} relationships"
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
    sys.exit(main())
