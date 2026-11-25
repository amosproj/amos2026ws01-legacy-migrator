import json

from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff
from migration_assistant.adapters.outbound.relationship_handoff import read_relationship_handoff
from shared_contracts.records import SnapshotIdentity


def test_pipeline_writes_graph_loader_handoff_with_resolvable_endpoints(tmp_path):
    revision = "c" * 40
    sources = tmp_path / "sources.jsonl"
    sources.write_text(
        json.dumps({"repoId": "repo", "commitSha": revision, "path": "src/OrderService.java"})
        + "\n",
        encoding="utf-8",
    )
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "graph": {"graphify_version": "0.9.100"},
                "nodes": [
                    {
                        "id": "a",
                        "label": "OrderService",
                        "_callable_class": True,
                        "source_file": "repo/src/OrderService.java",
                        "source_location": "L2",
                    },
                    {
                        "id": "b",
                        "label": "OrderRepository",
                        "_callable_class": True,
                        "source_file": "repo/src/OrderRepository.java",
                        "source_location": "L5",
                    },
                ],
                "links": [
                    {
                        "source": "a",
                        "target": "b",
                        "relation": "calls",
                        "source_file": "repo/src/OrderService.java",
                        "source_location": "L10",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    handoff = write_relationship_handoff([graph], sources, tmp_path / "run")
    assert read_relationship_handoff(tmp_path / "run") == handoff
    entity_count, relationship_count = handoff

    entities = [
        json.loads(line) for line in (tmp_path / "run/entities.jsonl").read_text().splitlines()
    ]
    relationships = [
        json.loads(line) for line in (tmp_path / "run/relationships.jsonl").read_text().splitlines()
    ]
    code_graphs = [
        json.loads(line) for line in (tmp_path / "run/code-graphs.jsonl").read_text().splitlines()
    ]
    entity_ids = {entity["payload"]["observationId"] for entity in entities}
    assert len(code_graphs) == 1
    assert code_graphs[0]["recordType"] == "CodeGraph"
    assert set(code_graphs[0]["payload"]["memberObservationIds"]) == entity_ids
    assert code_graphs[0]["payload"]["repoId"] == "repo"
    assert (entity_count, relationship_count) == (2, 1)
    assert all(rel["payload"]["sourceObservationId"] in entity_ids for rel in relationships)
    assert all(rel["payload"]["targetObservationId"] in entity_ids for rel in relationships)
    assert relationships[0]["payload"]["extractor"]["version"] == "0.9.100"
    identity = json.loads((tmp_path / "run/snapshot-identity.json").read_text())
    SnapshotIdentity.model_validate(identity)
    assert handoff.snapshot_id == identity["snapshotId"]
    assert all(entity["snapshotId"] == handoff.snapshot_id for entity in entities)
    assert all(relationship["snapshotId"] == handoff.snapshot_id for relationship in relationships)
    assert identity["snapshotId"] == relationships[0]["snapshotId"]
    assert len(identity["snapshotId"]) == 64
    assert identity["snapshotId"] == identity["snapshotId"].lower()
    assert not (tmp_path / "run/relationship-issues.jsonl").exists()
