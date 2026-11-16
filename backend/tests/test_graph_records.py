"""Tests for the record-based graph contract and retained identity helpers."""

import hashlib

from app.graph_schema.models import compute_entity_id, compute_file_id, normalize_path
from shared_contracts.records import (
    SCHEMA_VERSION,
    CodeGraphFact,
    RelationshipFact,
    SourceSpan,
    SymbolObservationFact,
)


def test_identity_helpers_retain_issue_21_hash_formulas():
    assert normalize_path("\\src\\orders\\Order.java/") == "src/orders/Order.java"
    file_token = "snapshot:legacy:src/orders/Order.java"
    assert compute_file_id("snapshot", "legacy", "src\\orders\\Order.java") == (
        hashlib.sha256(file_token.encode("utf-8")).hexdigest()
    )

    entity_token = "snapshot:legacy:src/orders/Order.java:method:Order.save:save(Order)"
    assert (
        compute_entity_id(
            "snapshot",
            "legacy",
            "src/orders/Order.java",
            "method",
            "Order.save",
            "save(Order)",
        )
        == hashlib.sha256(entity_token.encode("utf-8")).hexdigest()
    )


def test_file_and_entity_identity_is_scoped_to_repository_and_signature():
    assert compute_file_id("snapshot", "legacy", "src/Order.java") != compute_file_id(
        "snapshot", "target", "src/Order.java"
    )
    assert compute_entity_id(
        "snapshot", "repo", "src/Order.java", "method", "Order.save", "save(Order)"
    ) != compute_entity_id(
        "snapshot", "repo", "src/Order.java", "method", "Order.save", "save(Customer)"
    )


def test_component_subgraph_root_references_its_observations():
    root = CodeGraphFact(
        schema_version=SCHEMA_VERSION,
        record_type="CodeGraph",
        record_id="a" * 64,
        snapshot_id="b" * 64,
        repo_id="legacy",
        commit_sha="c" * 40,
        member_observation_ids=["file-1", "class-1"],
        file_observation_ids=["file-1"],
    )

    record = root.to_record_dict()
    assert record["recordType"] == "CodeGraph"
    assert record["payload"]["repoId"] == "legacy"
    assert record["payload"]["memberObservationIds"] == ["file-1", "class-1"]
    assert record["payload"]["fileObservationIds"] == ["file-1"]


def test_symbol_observation_keeps_source_span_in_canonical_record():
    span = SourceSpan(
        repo_id="legacy",
        path="src/Order.java",
        commit_sha="c" * 40,
        start_line=12,
        end_line=18,
    )
    entity = SymbolObservationFact(
        schema_version=SCHEMA_VERSION,
        record_type="SymbolObservation",
        record_id="d" * 64,
        snapshot_id="b" * 64,
        observation_id="class-1",
        kind="class",
        name="Order",
        qualified_name="src/Order.java::Order::graph-node-1",
        repo_id="legacy",
        source_span=span,
    )

    assert entity.to_record_dict()["payload"]["sourceSpan"] == {
        "repoId": "legacy",
        "path": "src/Order.java",
        "commitSha": "c" * 40,
        "startLine": 12,
        "endLine": 18,
    }


def test_unknown_relationship_keeps_original_type_and_graphify_provenance():
    raw_edge = {
        "id": "edge-9",
        "source": "node-1",
        "target": "node-2",
        "type": "case_of",
        "confidence": 0.87,
    }
    span = SourceSpan(
        repo_id="legacy",
        path="src/Order.java",
        commit_sha="c" * 40,
        start_line=21,
        end_line=21,
    )
    relationship = RelationshipFact(
        schema_version=SCHEMA_VERSION,
        record_type="Relationship",
        record_id="e" * 64,
        snapshot_id="b" * 64,
        relationship_type="case_of",
        source_observation_id="class-1",
        target_observation_id="external-1",
        evidence_ids=["git:evidence-1"],
        source_span=span,
        source_edge_id="edge-9",
        original_relationship_type="case_of",
        original_edge=raw_edge,
    )

    payload = relationship.to_record_dict()["payload"]
    assert payload["relationshipType"] == "case_of"
    assert payload["originalRelationshipType"] == "case_of"
    assert payload["sourceEdgeId"] == "edge-9"
    assert payload["originalEdge"] == raw_edge
    assert payload["sourceSpan"]["path"] == "src/Order.java"
