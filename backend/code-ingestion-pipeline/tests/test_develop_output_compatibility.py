"""Byte-for-byte compatibility with frozen develop canonical handoff outputs."""

import json
from pathlib import Path

import pytest

from migration_assistant.adapters.outbound.graphify import GraphifyAdapter
from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff
from migration_assistant.adapters.outbound.pipeline_storage import LocalPipelineStorage
from migration_assistant.domain.checkout import ComponentCheckout
from migration_assistant.domain.sources import SourceFile

FIXTURES = Path(__file__).parent / "fixtures"
CANONICAL_FILES = {
    "entities.jsonl",
    "relationships.jsonl",
    "code-graphs.jsonl",
    "snapshot-identity.json",
    "relationship-issues.jsonl",
}


def assert_develop_bytes(run: Path, expected: Path) -> None:
    actual_names = {path.name for path in run.iterdir()} & CANONICAL_FILES
    assert actual_names == {path.name for path in expected.iterdir()}
    for name in sorted(actual_names):
        assert (run / name).read_bytes() == (expected / name).read_bytes(), name


def test_canonical_handoff_preserves_develop_bytes(tmp_path):
    fixture = FIXTURES / "develop-handoff"
    handoff = write_relationship_handoff(
        sorted((fixture / "graphs").glob("*/graphify-out/graph.json")),
        fixture / "sources.jsonl",
        tmp_path,
        graph_mode="per-component",
    )

    assert_develop_bytes(tmp_path, fixture / "expected")
    identity = json.loads((tmp_path / "snapshot-identity.json").read_text())
    assert handoff.snapshot_id == identity["snapshotId"]


def test_direct_checkout_extraction_preserves_develop_bytes(tmp_path):
    pytest.importorskip("graphify")
    fixture = FIXTURES / "develop-direct-checkout"
    source = SourceFile.model_validate_json((fixture / "sources.jsonl").read_text())
    checkout = tmp_path / "checkout" / "components" / source.repo_id
    path = checkout / source.path
    path.parent.mkdir(parents=True)
    path.write_bytes(source.content.encode(source.encoding))
    # A checkout can contain unselected files; they must not enter extraction.
    (path.parent / "Excluded.java").write_text("class Excluded {}\n")
    member = ComponentCheckout(
        repo_id=source.repo_id,
        ref=source.stage,
        commit_sha=source.commit_sha,
        local_path=checkout,
        public_url=source.public_url,
    )
    run = tmp_path / "run"
    graph = GraphifyAdapter().build(
        member, [source], tmp_path / "checkout", run / "graphs" / source.repo_id
    )
    LocalPipelineStorage().write_sources(run / "sources.jsonl", [source])
    write_relationship_handoff([graph], run / "sources.jsonl", run, graph_mode="per-component")

    assert_develop_bytes(run, fixture / "expected")
