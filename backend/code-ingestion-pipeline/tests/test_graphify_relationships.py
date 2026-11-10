from types import SimpleNamespace

import pytest

from migration_assistant.adapters.outbound.graphify_relationships import (
    CanonicalEntityIndex,
    normalize_graphify,
    normalize_graphify_facts,
    normalize_graphify_file,
    read_graphify,
)


def observation(observation_id: str, name: str, path: str, kind: str = "class"):
    return SimpleNamespace(
        observation_id=observation_id,
        snapshot_id="snapshot",
        repo_id="repo",
        path=path,
        kind=kind,
        name=name,
        qualified_name=f"app.{name}",
        source_span=SimpleNamespace(
            repo_id="repo", commit_sha="a" * 40, path=path, start_line=1, end_line=3
        ),
    )


def test_normalizes_graphify_edge_to_canonical_fact_with_evidence():
    entities = CanonicalEntityIndex(
        [
            observation("source-observation", "Order", "src/Order.java"),
            observation("target-observation", "Repository", "src/Repository.java"),
        ]
    )
    payload = {
        "nodes": [
            {
                "id": "n1",
                "repoId": "repo",
                "path": "src/Order.java",
                "kind": "class",
                "qualifiedName": "app.Order",
                "name": "Order",
            },
            {
                "id": "n2",
                "repoId": "repo",
                "path": "src/Repository.java",
                "kind": "class",
                "qualifiedName": "app.Repository",
                "name": "Repository",
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": "n1",
                "target": "n2",
                "type": "calls",
                "sourceSpan": {
                    "repoId": "repo",
                    "commitSha": "a" * 40,
                    "path": "src/Order.java",
                    "startLine": 10,
                    "endLine": 10,
                },
            }
        ],
    }

    result = normalize_graphify(payload, entities, snapshot_id="snapshot", extractor_version="1")

    assert len(result.facts) == 1
    fact = result.facts[0]
    assert fact.relationship_type == "CALLS"
    assert fact.source_observation_id == "source-observation"
    assert fact.target_observation_id == "target-observation"
    assert fact.source_span.start_line == 10
    assert fact.evidence_ids
    assert result.issues == []


def test_missing_and_ambiguous_endpoints_are_reported_without_facts():
    entities = CanonicalEntityIndex(
        [
            observation("one", "Order", "src/Order.java"),
            observation("two", "Order", "src/Order.java", kind="method"),
        ]
    )
    payload = {
        "nodes": [
            {
                "id": "missing",
                "repoId": "repo",
                "path": "src/Missing.java",
                "kind": "class",
                "qualifiedName": "app.Missing",
                "name": "Missing",
            },
            {"id": "ambiguous", "repoId": "repo", "path": "src/Order.java", "name": "Order"},
        ],
        "edges": [
            {"id": "missing-edge", "source": "missing", "target": "ambiguous", "type": "calls"},
            {"id": "unknown-edge", "source": "unknown", "target": "ambiguous", "type": "calls"},
        ],
    }

    result = normalize_graphify(payload, entities, snapshot_id="snapshot")

    assert result.facts == []
    assert {issue.code for issue in result.issues} == {"unresolved_source", "unresolved_target"}


def test_unsupported_types_and_invalid_payload_are_explicit():
    entities = CanonicalEntityIndex([observation("one", "Order", "src/Order.java")])
    result = normalize_graphify(
        {
            "nodes": [{"id": "n", "observationId": "one"}],
            "edges": [{"id": "edge", "source": "n", "target": "n", "type": "same_entity_as"}],
        },
        entities,
        snapshot_id="snapshot",
    )

    assert result.facts == []
    assert result.issues[0].code == "unsupported_type"
    with pytest.raises(ValueError, match="list-valued"):
        normalize_graphify({"nodes": [], "edges": {}}, entities, snapshot_id="snapshot")


def test_relationship_ids_and_canonical_jsonl_are_deterministic(tmp_path):
    entities = CanonicalEntityIndex(
        [
            observation("source", "Order", "src/Order.java"),
            observation("target", "Repository", "src/Repository.java"),
        ]
    )
    payload = {
        "nodes": [{"id": "a", "observationId": "source"}, {"id": "b", "observationId": "target"}],
        "edges": [
            {
                "source": "a",
                "target": "b",
                "type": "references",
                "sourceSpan": {
                    "repoId": "repo",
                    "commitSha": "a" * 40,
                    "path": "src/Order.java",
                    "startLine": 2,
                    "endLine": 2,
                },
            }
        ],
    }

    first = normalize_graphify(payload, entities, snapshot_id="snapshot")
    second = normalize_graphify(payload, entities, snapshot_id="snapshot")

    assert first == second
    assert first.to_jsonl() == second.to_jsonl()
    record = first.facts[0].to_record_dict()
    assert record["recordType"] == "Relationship"
    assert record["payload"]["relationshipType"] == "REFERENCES"
    assert record["evidenceReferences"] == ["git:repo@" + "a" * 40 + ":src/Order.java#L2-L2"]
    first.write_jsonl(tmp_path / "relationships.jsonl")
    assert (tmp_path / "relationships.jsonl").read_text().endswith("\n")


def test_graphify_json_reader_rejects_non_object(tmp_path):
    graph = tmp_path / "graph.json"
    graph.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        read_graphify(graph)


def test_graphify_file_can_be_normalized_without_graphify_installed(tmp_path):
    entities = CanonicalEntityIndex([observation("one", "Order", "src/Order.java")])
    graph = tmp_path / "graph.json"
    graph.write_text(
        '{"nodes":[{"id":"n","observationId":"one"}],'
        '"edges":[{"source":"n","target":"n","type":"calls",'
        '"sourceSpan":{"repoId":"repo","commitSha":"'
        + "a" * 40
        + '","path":"src/Order.java","startLine":1,"endLine":1}}]}',
        encoding="utf-8",
    )

    result = normalize_graphify_file(graph, entities, snapshot_id="snapshot")

    assert result.facts[0].relationship_type == "CALLS"


def test_native_graphify_links_produce_entities_and_valid_relationships():
    revision = "b" * 40
    payload = {
        "graph": {"graphify_version": "0.9.100"},
        "nodes": [
            {
                "id": "caller",
                "label": "OrderService.placeOrder",
                "_callable": True,
                "source_file": "repo/src/OrderService.java",
                "source_location": "L12",
            },
            {
                "id": "callee",
                "label": "OrderRepository.save",
                "_callable": True,
                "source_file": "repo/src/OrderRepository.java",
                "source_location": "L8",
            },
            {"id": "external", "label": "java.util.List", "external": True},
        ],
        "links": [
            {
                "source": "caller",
                "target": "callee",
                "relation": "calls",
                "source_file": "repo/src/OrderService.java",
                "source_location": "L20",
            },
            {
                "source": "caller",
                "target": "external",
                "relation": "references",
                "source_file": "repo/src/OrderService.java",
                "source_location": "L4",
            },
        ],
    }

    entities, result = normalize_graphify_facts(
        payload,
        snapshot_id="snapshot-1",
        source_revisions={"repo": revision},
        extractor_version="0.9.100",
    )

    assert len(entities) == 2
    assert {entity.record_type for entity in entities} == {"SymbolObservation"}
    assert len(result.facts) == 1
    fact = result.facts[0]
    entity_ids = {entity.observation_id for entity in entities}
    assert fact.source_observation_id in entity_ids
    assert fact.target_observation_id in entity_ids
    assert fact.relationship_type == "CALLS"
    assert fact.source_span.commit_sha == revision
    assert result.issues[0].code == "unresolved_target"
