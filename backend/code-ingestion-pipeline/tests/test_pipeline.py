"""Pipeline wiring and real extraction from the loader's pinned checkout paths."""

import builtins
import json

import pytest
from conftest import git, tree_hashes

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.adapters.outbound.graphify import GraphifyAdapter
from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff
from migration_assistant.adapters.outbound.pipeline_storage import LocalPipelineStorage
from migration_assistant.application.pipeline import PipelineService
from migration_assistant.application.ports.pipeline import PersistenceWriter
from migration_assistant.bootstrap import cli
from migration_assistant.domain.pipeline import PipelineError


def service(
    graph_builder: GraphifyAdapter, persistence_writer: PersistenceWriter
) -> PipelineService:
    return PipelineService(
        git_repo=LocalGitAdapter(),
        source_loader=load_sources,
        graph_builder=graph_builder,
        handoff_writer=write_relationship_handoff,
        storage=LocalPipelineStorage(),
        persistence_writer=persistence_writer,
    )


def test_cli_builds_separate_graphs_without_source_copies(
    reference, pipeline_cli, tmp_path, persistence_writer
):
    code = cli.main(
        [
            "--config",
            str(reference.config_path),
            "--stage",
            "step-04a",
            "--components",
            "monolith",
            "catalog-service",
        ]
    )

    assert code == 0
    assert len(pipeline_cli) == 2
    for member, files, root, output in pipeline_cli:
        assert {file.repo_id for file in files} == {member.repo_id}
        assert all((member.local_path / file.path).is_file() for file in files)
        assert root == reference.workspace
        assert output.name == member.repo_id
        assert git(member.local_path, "status", "--porcelain") == ""
    (run,) = (tmp_path / "runs").iterdir()
    assert not (run / "sources").exists()
    assert (run / "sources.jsonl").is_file()
    assert (run / "bootstrap.log").is_file()
    assert (run / "snapshot-identity.json").is_file()
    assert (run / "code-graphs.jsonl").is_file()
    assert (run / "entities.jsonl").is_file()
    assert (run / "relationships.jsonl").is_file()
    persistence_writer.persist_handoff.assert_called_once()
    (handoff,) = persistence_writer.persist_handoff.call_args.args
    assert (
        handoff.snapshot_id
        == json.loads((run / "snapshot-identity.json").read_text())["snapshotId"]
    )


def test_empty_selection_does_not_start_graphify(
    reference, pipeline_cli, tmp_path, persistence_writer
):
    pipeline = service(GraphifyAdapter(), persistence_writer)
    with pytest.raises(PipelineError, match="No source files selected"):
        pipeline.run(reference.config(include=[".missing"]), tmp_path / "empty-run")
    assert pipeline_cli == []
    assert not (tmp_path / "empty-run").exists()
    persistence_writer.persist_handoff.assert_not_called()


def test_component_without_loaded_files_is_skipped(
    reference, pipeline_cli, tmp_path, persistence_writer
):
    result = service(GraphifyAdapter(), persistence_writer).run(
        reference.config(stage="step-04a", components=[], include=["Dockerfile"]),
        tmp_path / "runs",
    )
    assert list(result.graph_paths) == ["legacy-example-monolith"]
    assert len(pipeline_cli) == 1
    identity = json.loads((result.run_directory / "snapshot-identity.json").read_text())
    assert {member["repoId"] for member in identity["sourceMembers"]} == set(result.graph_paths)
    assert result.snapshot_id == identity["snapshotId"]


def test_cli_rejects_graph_mode():
    with pytest.raises(SystemExit) as error:
        cli.main(["--graph-mode", "per-component"])
    assert error.value.code == 2


def test_missing_graphify_is_a_component_error_with_partial_run(
    reference, tmp_path, monkeypatch, persistence_writer
):
    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("graphify"):
            raise ModuleNotFoundError("Graphify not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    # The standalone loader still works with Graphify imports forbidden.
    config = reference.config()
    assert load_sources(config, LocalGitAdapter().checkout(config)).counts.loaded == 3
    message = "component 'legacy-example-monolith'.*uv sync"
    with pytest.raises(PipelineError, match=message) as error:
        service(GraphifyAdapter(), persistence_writer).run(config, tmp_path / "runs")
    (run,) = (tmp_path / "runs").iterdir()
    assert str(run) in str(error.value)


def test_cli_unexpected_error_and_verbose_traceback(reference, pipeline_cli, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise KeyError("unexpected test failure")

    monkeypatch.setattr(cli, "load_sources", broken)
    assert cli.main(["--config", str(reference.config_path)]) == 2
    assert "unexpected failure, rerun with --verbose" in capsys.readouterr().err
    assert cli.main(["--config", str(reference.config_path), "--verbose"]) == 2
    assert "KeyError" in capsys.readouterr().err


def test_real_graphify_generates_only_minimal_artifacts_and_repeatable_facts(
    reference, tmp_path, persistence_writer
):
    pytest.importorskip("graphify")
    original_hashes = tree_hashes(reference.source)
    config = reference.config(stage="step-04a", components=[])
    pipeline = service(GraphifyAdapter(), persistence_writer)

    first = pipeline.run(config, tmp_path / "runs")
    second = pipeline.run(config, tmp_path / "runs")

    assert len(first.graph_paths) == 2
    assert first.run_directory != second.run_directory
    assert first.entity_count > 0
    assert first.relationship_count > 0
    assert tree_hashes(reference.source) == original_hashes
    for member in first.load_result.checkout.members:
        assert git(member.local_path, "status", "--porcelain") == ""
        graph = first.graph_paths[member.repo_id]
        data = json.loads(graph.read_text(encoding="utf-8"))
        assert data["built_at_commit"] == member.commit_sha
        assert data["graph"]["graphify_version"] == "0.9.100"
        assert all(node.get("community") is None for node in data["nodes"])
        sources = {node["source_file"] for node in data["nodes"] if node.get("source_file")}
        allowed = {file.path for file in first.load_result.files if file.repo_id == member.repo_id}
        assert sources <= allowed
        assert sources
        assert {path.name for path in graph.parent.iterdir() if path.is_file()} == {
            "graph.json",
            "graph.html",
        }
        assert (graph.parent / "cache").is_dir()
        assert (graph.parent / "graph.html").stat().st_size > 0
    for name in (
        "entities.jsonl",
        "relationships.jsonl",
        "code-graphs.jsonl",
        "snapshot-identity.json",
    ):
        assert (first.run_directory / name).read_bytes() == (
            second.run_directory / name
        ).read_bytes()
    entities = [
        json.loads(line)
        for line in (first.run_directory / "entities.jsonl").read_text().splitlines()
    ]
    relationships = [
        json.loads(line)
        for line in (first.run_directory / "relationships.jsonl").read_text().splitlines()
    ]
    entity_ids = {record["payload"]["observationId"] for record in entities}
    revisions = {member.repo_id: member.commit_sha for member in first.load_result.checkout.members}
    for entity in entities:
        if entity["recordType"] != "SymbolObservation":
            continue
        span = entity["payload"]["sourceSpan"]
        assert span["commitSha"] == revisions[span["repoId"]]
        assert not span["path"].startswith("components/")
    for relationship in relationships:
        assert relationship["payload"]["sourceObservationId"] in entity_ids
        assert relationship["payload"]["targetObservationId"] in entity_ids
