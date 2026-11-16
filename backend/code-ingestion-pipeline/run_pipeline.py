"""Run bootstrap and Graphify in the same active Python environment."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))
sys.path.insert(0, str(PROJECT_DIR.parent))


@dataclass(frozen=True)
class RelationshipHandoffResult:
    """Counts and the deterministic snapshot identity produced by the handoff."""

    entity_count: int
    relationship_count: int
    snapshot_id: str

    def __iter__(self) -> Iterator[int]:
        """Keep existing two-value count unpacking working for the CLI."""
        yield self.entity_count
        yield self.relationship_count


def safe_relative(value: str) -> PurePosixPath:
    """Keep JSONL paths inside the analysis folder, on Linux and Windows."""
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or PureWindowsPath(value).drive
        or "\\" in value
        or any(
            part in ("", ".", "..")
            or part.casefold() == ".git"
            or any(c in part for c in '<>:"|?*\x00')
            or part.endswith((".", " "))
            or PureWindowsPath(part).is_reserved()
            for part in value.split("/")
        )
    ):
        raise ValueError(f"Unsafe source path: {value!r}")
    return path


def prepare_sources(jsonl: Path, root: Path) -> list[str]:
    """Reconstruct bootstrap-selected files from JSONL; return component names."""
    records = []
    files, directories, components = set(), set(), set()
    with jsonl.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
                repo = safe_relative(row["repoId"])
                if len(repo.parts) != 1:
                    raise ValueError("Component name must be a single folder name")
                path = repo / safe_relative(row["path"])
                key = path.as_posix().casefold()
                parents = {p.as_posix().casefold() for p in path.parents if p != PurePosixPath(".")}
                if key in files or key in directories or parents & files:
                    raise ValueError(f"Duplicate or conflicting source path: {path}")
                files.add(key)
                directories.update(parents)
                records.append((path, row["content"].encode(row["encoding"])))
                components.add(str(repo))
            except (KeyError, TypeError, ValueError, LookupError, AttributeError) as error:
                raise ValueError(f"Invalid bootstrap JSONL at line {number}: {error}") from error
    if not records:
        raise ValueError(
            "Bootstrap selected no source files; check the stage, components and filters."
        )
    for path, data in records:
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return sorted(components)


def run_logged(command: list[str], cwd: Path, log: Path, env: dict) -> None:
    """Keep subprocess diagnostics in the run folder."""
    with log.open("w", encoding="utf-8") as handle:
        try:
            subprocess.run(
                command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, check=True
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"Command failed with exit code {error.returncode}; see {log}"
            ) from error


def build_graph(source: Path, output: Path) -> None:
    """Extract, then generate communities, report and HTML using Graphify."""
    output.mkdir(parents=True)
    env = {
        **os.environ,
        "GRAPHIFY_BACKEND": "none",
        "GRAPHIFY_OUT": "graphify-out",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        # These copies have no Git history; don't stamp our project's commit.
        "GIT_CEILING_DIRECTORIES": os.pathsep.join([str(source.parent), str(output.parent)]),
    }
    command = [sys.executable, "-m", "graphify"]
    run_logged(
        [*command, "extract", str(source), "--out", str(output), "--code-only", "--no-cluster"],
        output,
        output / "extract.log",
        env,
    )
    run_logged([*command, "cluster-only", str(output)], output, output / "cluster.log", env)
    for name in ("graph.json", "graph.html", "GRAPH_REPORT.md"):
        artifact = output / "graphify-out" / name
        if not artifact.is_file() or not artifact.stat().st_size:
            raise RuntimeError(f"Graphify did not produce {name}; see logs in {output}")


def write_relationship_handoff(
    graph_paths: list[Path],
    sources_jsonl: Path,
    run: Path,
    *,
    graph_mode: str = "combined",
) -> RelationshipHandoffResult:
    """Write per-repository CodeGraph roots, entity records, and relationships."""
    run.mkdir(parents=True, exist_ok=True)
    from migration_assistant.adapters.outbound.graphify_relationships import (
        normalize_graphify_facts,
        read_graphify,
        write_jsonl_records,
    )
    from shared_contracts.records import SCHEMA_VERSION, CodeGraphFact
    from shared_contracts.snapshot_identity import compute_snapshot_identity

    source_revisions: dict[str, str] = {}
    selected_paths: dict[str, set[str]] = {}
    source_line_counts: dict[tuple[str, str], int] = {}
    with sources_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            source = json.loads(line)
            repo_id, commit_sha = source["repoId"], source["commitSha"]
            previous = source_revisions.setdefault(repo_id, commit_sha)
            if previous != commit_sha:
                raise ValueError(f"Component {repo_id!r} has multiple source revisions")
            path = source.get("path")
            if not isinstance(path, str) or not path:
                raise ValueError(
                    "Every source manifest row must include a repository-relative path"
                )
            selected_paths.setdefault(repo_id, set()).add(path)
            content = source.get("content")
            if isinstance(content, str):
                source_line_counts[(repo_id, path)] = len(content.splitlines())
    if not source_revisions:
        raise ValueError("Cannot create relationship handoff from an empty source manifest")
    if not graph_paths:
        raise ValueError("Cannot create relationship handoff without Graphify graph files")

    extractor_versions = set()
    missing_version = False
    for graph_path in graph_paths:
        graph_metadata = read_graphify(graph_path).get("graph", {})
        version = (
            graph_metadata.get("graphify_version") if isinstance(graph_metadata, dict) else None
        )
        if version:
            extractor_versions.add(str(version))
        else:
            missing_version = True
    if missing_version:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as package_version

        try:
            extractor_versions.add(package_version("graphifyy"))
        except PackageNotFoundError as error:
            raise ValueError(
                "Graphify output has no version metadata and graphifyy is not installed"
            ) from error
    extraction_config = {
        "pipeline": {"name": "graphify-code-ingestion", "version": SCHEMA_VERSION},
        "graphMode": graph_mode,
        "graphify": {"backend": "none", "codeOnly": True, "cluster": False},
        "selectedFiles": [
            {"repoId": repo_id, "paths": sorted(paths)}
            for repo_id, paths in sorted(selected_paths.items())
        ],
    }
    identity = compute_snapshot_identity(
        source_revisions,
        [{"name": "graphify", "version": version} for version in extractor_versions],
        extraction_config,
    )
    snapshot_id = identity.snapshot_id
    (run / "snapshot-identity.json").write_text(
        identity.model_dump_json(by_alias=True) + "\n",
        encoding="utf-8",
    )
    all_entities = {}
    all_relationships = {}
    issues = []
    for graph_path in graph_paths:
        default_repo_id = None
        if graph_mode == "per-component":
            default_repo_id = graph_path.parent.parent.name
        elif len(source_revisions) == 1:
            default_repo_id = next(iter(source_revisions))
        entities, result = normalize_graphify_facts(
            read_graphify(graph_path),
            snapshot_id=snapshot_id,
            source_revisions=source_revisions,
            source_line_counts=source_line_counts,
            default_repo_id=default_repo_id,
        )
        all_entities.update({fact.record_id: fact for fact in entities})
        all_relationships.update({fact.record_id: fact for fact in result.facts})
        issues.extend(result.issues)

    members_by_repo: dict[str, list[Any]] = {repo_id: [] for repo_id in source_revisions}
    for fact in all_entities.values():
        if fact.record_type == "SymbolObservation":
            repo_id = fact.source_span.repo_id
        elif fact.record_type == "UnresolvedSymbolObservation":
            repo_id = fact.repo_id
        else:
            continue
        if repo_id in members_by_repo:
            members_by_repo[repo_id].append(fact)

    extractor_version = ",".join(sorted(extractor_versions))
    code_graphs = []
    for repo_id, commit_sha in sorted(source_revisions.items()):
        members = sorted(members_by_repo[repo_id], key=lambda fact: fact.observation_id)
        member_ids = [fact.observation_id for fact in members]
        file_ids = [fact.observation_id for fact in members if fact.kind == "file"]
        record_id = hashlib.sha256(
            json.dumps(
                [snapshot_id, "CodeGraph", repo_id, commit_sha],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        code_graphs.append(
            CodeGraphFact(
                schema_version=SCHEMA_VERSION,
                record_type="CodeGraph",
                record_id=record_id,
                snapshot_id=snapshot_id,
                repo_id=repo_id,
                commit_sha=commit_sha,
                member_observation_ids=member_ids,
                file_observation_ids=file_ids,
                extractor_version=extractor_version,
            )
        )

    write_jsonl_records(
        sorted(all_entities.values(), key=lambda fact: fact.record_id),
        run / "entities.jsonl",
    )
    write_jsonl_records(code_graphs, run / "code-graphs.jsonl")
    write_jsonl_records(
        sorted(all_relationships.values(), key=lambda fact: fact.record_id),
        run / "relationships.jsonl",
    )
    if issues:
        issue_file = run / "relationship-issues.jsonl"
        issue_file.write_text(
            "".join(issue.model_dump_json() + "\n" for issue in issues), encoding="utf-8"
        )
    return RelationshipHandoffResult(
        entity_count=len(all_entities),
        relationship_count=len(all_relationships),
        snapshot_id=snapshot_id,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--stage")
    parser.add_argument("--components", nargs="+")
    parser.add_argument("--graph-mode", choices=("combined", "per-component"), default="combined")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / ".cache" / "ingestion")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not shutil.which("git"):
            raise RuntimeError("Git is missing from PATH.")
        if any(importlib.util.find_spec(name) is None for name in ("pydantic", "yaml")):
            raise RuntimeError("Complete Documentation/ingestion/reference-loader.md setup first.")
        if importlib.util.find_spec("graphify") is None:
            raise RuntimeError("Run python setup.py in the ingestion virtual environment first.")
        output = args.output_dir.expanduser().resolve()
        if output == REPO_ROOT or REPO_ROOT in output.parents:
            ignored = subprocess.run(
                ["git", "check-ignore", "--quiet", "--", str(output / ".pipeline-output-check")],
                cwd=PROJECT_DIR,
            )
            if ignored.returncode:
                raise ValueError(
                    "Output inside this repository must be Git-ignored; use .cache/ingestion."
                )
        output.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-")
        run = Path(tempfile.mkdtemp(prefix=stamp, dir=output))
        print(f"Run folder: {run}", flush=True)
        jsonl = run / "sources.jsonl"
        command = [sys.executable, "-m", "migration_assistant.bootstrap.cli", "--out", str(jsonl)]
        if args.config is not None:
            command.extend(["--config", str(args.config.expanduser().resolve())])
        if args.stage is not None:
            command.extend(["--stage", args.stage])
        if args.components is not None:
            command.extend(["--components", *args.components])
        if args.verbose:
            command.append("--verbose")
        env = {**os.environ, "PYTHONPATH": str(PROJECT_DIR / "src"), "PYTHONIOENCODING": "utf-8"}
        print("Loading reference files with bootstrap...", flush=True)
        run_logged(command, PROJECT_DIR, run / "bootstrap.log", env)
        sources = run / "sources"
        components = prepare_sources(jsonl, sources)
        groups = (
            {"combined": sources}
            if args.graph_mode == "combined"
            else {repo: sources / repo for repo in components}
        )
        graph_paths = []
        for name, source in groups.items():
            print(f"Generating graph: {name}", flush=True)
            graph_output = run / "graphs" / name
            build_graph(source, graph_output)
            graph_paths.append(graph_output / "graphify-out" / "graph.json")
        entity_count, relationship_count = write_relationship_handoff(
            graph_paths, jsonl, run, graph_mode=args.graph_mode
        )
        print(f"Graph handoff: {entity_count} entities, {relationship_count} relationships")
        print(f"Success. Graphs: {run / 'graphs'}")
        return 0
    except (RuntimeError, OSError, ValueError, KeyboardInterrupt) as error:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: {error or 'Interrupted'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
