import json

from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff


def test_pipeline_writes_graph_loader_handoff_with_resolvable_endpoints(tmp_path):
    revision = "c" * 40
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

    entity_count, relationship_count = write_relationship_handoff(
        [graph], {"repo": revision}, tmp_path / "run"
    )

    entities = [
        json.loads(line) for line in (tmp_path / "run/entities.jsonl").read_text().splitlines()
    ]
    relationships = [
        json.loads(line) for line in (tmp_path / "run/relationships.jsonl").read_text().splitlines()
    ]
    entity_ids = {entity["payload"]["observationId"] for entity in entities}
    assert (entity_count, relationship_count) == (2, 1)
    assert all(rel["payload"]["sourceObservationId"] in entity_ids for rel in relationships)
    assert all(rel["payload"]["targetObservationId"] in entity_ids for rel in relationships)
    assert relationships[0]["payload"]["extractor"]["version"] == "0.9.100"
