"""Command line: check out one stage of the reference source and load its files (Issue #17).

Run with: python -m migration_assistant.bootstrap.cli
"""

import argparse
import sys
import traceback
from pathlib import Path

from pydantic import ValidationError

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.domain.checkout import CheckoutError
from migration_assistant.domain.reference_source import (
    ConfigError,
    ReferenceSourceConfig,
    default_config_path,
    is_remote_source,
    load_config,
)

EXIT_ERROR = 1
EXIT_UNEXPECTED = 2


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        _run(args)
    except (ConfigError, CheckoutError) as error:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: {' ; '.join(str(error).splitlines())}", file=sys.stderr)
        return EXIT_ERROR
    except Exception:
        if args.verbose:
            traceback.print_exc()
        print("ERROR: unexpected failure, rerun with --verbose", file=sys.stderr)
        return EXIT_UNEXPECTED
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m migration_assistant.bootstrap.cli",
        description="Check out a stage of the reference source and load its files.",
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
    parser.add_argument("--verbose", action="store_true", help="show the full traceback on errors")
    return parser.parse_args(argv)


def _run(args: argparse.Namespace) -> None:
    config_path = args.config or default_config_path()
    config = _with_overrides(load_config(config_path), args)
    if args.out is not None:
        _check_out_path(args.out, config)

    checkout = LocalGitAdapter().checkout(config)
    result = load_sources(config, checkout)

    print(f"config: {Path(config_path).as_posix()}")
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

    if args.out is not None:
        _write_jsonl(args.out, result.files)
        print(f"output: {args.out}")


def _with_overrides(config: ReferenceSourceConfig, args: argparse.Namespace) -> ReferenceSourceConfig:
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
            f"Invalid value for option '{'.'.join(str(p) for p in problem['loc'])}': {problem['msg']}"
            for problem in error.errors()
        ]
        raise ConfigError("\n".join(problems)) from error


def _check_out_path(out: Path, config: ReferenceSourceConfig) -> None:
    target = out.resolve()
    protected_paths = [("workspace", config.workspace)]
    if not is_remote_source(config.source):
        protected_paths.insert(0, ("source repository", Path(config.source)))
    for label, protected in protected_paths:
        protected = protected.resolve()
        if target == protected or protected in target.parents:
            raise ConfigError(f"--out must not be inside the {label}: {protected}")


def _write_jsonl(out: Path, files: list) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        for file in files:
            handle.write(file.model_dump_json(by_alias=True) + "\n")


if __name__ == "__main__":
    sys.exit(main())
