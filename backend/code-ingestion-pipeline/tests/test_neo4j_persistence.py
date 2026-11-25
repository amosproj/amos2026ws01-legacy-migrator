"""Real Neo4j round trips; use a disposable database, never the demo volume.

Start an isolated server from the repository root:
    sudo docker run --rm -d --name amos-neo4j-persistence-test \
        -p 127.0.0.1:17687:7687 -e NEO4J_AUTH=neo4j/test-only-password neo4j:2026.10.2

Run from backend/code-ingestion-pipeline/:
    NEO4J_TEST_URI=bolt://localhost:17687 uv run --locked --project .. pytest \
        tests/test_neo4j_persistence.py -q
"""

import json
import os
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import ConstraintError

from migration_assistant.adapters.outbound.graphify_relationships import write_jsonl_records
from migration_assistant.adapters.outbound.neo4j import Neo4jPersistenceWriter
from migration_assistant.domain.pipeline import RelationshipHandoffResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)
from shared_contracts.source_span import SourceSpan

pytestmark = pytest.mark.skipif(
    not os.environ.get("NEO4J_TEST_URI"),
    reason="set NEO4J_TEST_URI to a disposable Neo4j server to run integration tests",
)


@pytest.fixture
def database():
    snapshot = f"neo4j-persistence-test-{uuid4().hex}"
    with GraphDatabase.driver(
        os.environ["NEO4J_TEST_URI"], auth=("neo4j", "test-only-password")
    ) as driver:
        driver.verify_connectivity()
        try:
            yield driver, snapshot
        finally:
            driver.execute_query(
                "MATCH (n:Observation) WHERE n.snapshot_id IN $snapshots DETACH DELETE n",
                snapshots=[snapshot, f"{snapshot}-other"],
                database_="neo4j",
            )


def handoff(snapshot, entities=None, relationships=None):
    if entities is None:
        span = SourceSpan(
            repo_id="source-repo",
            path="src/Service.java",
            commit_sha="a" * 40,
            start_line=2,
            end_line=8,
            start_column=0,
            end_column=12,
        )
        entities = [
            SymbolObservationFact(
                record_id=sha256(f"{snapshot}:located".encode()).hexdigest(),
                snapshot_id=snapshot,
                observation_id="located",
                kind="class",
                name='Größe "注文"\nService',
                qualified_name="demo.Service",
                repo_id="owner-repo",
                source_span=span,
                extractor_name="test-extractor",
                extractor_version="1.2.3",
            ),
            SymbolObservationFact(
                record_id=sha256(f"{snapshot}:no-columns".encode()).hexdigest(),
                snapshot_id=snapshot,
                observation_id="no-columns",
                kind="file",
                name="Service.java",
                qualified_name="src/Service.java",
                repo_id="source-repo",
                source_span=span.model_copy(update={"start_column": None, "end_column": None}),
            ),
            ExternalSymbolObservationFact(
                record_id=sha256(f"{snapshot}:external".encode()).hexdigest(),
                snapshot_id=snapshot,
                observation_id="external",
                name="List",
                qualified_name="java.util.List",
            ),
            UnresolvedSymbolObservationFact(
                record_id=sha256(f"{snapshot}:unresolved".encode()).hexdigest(),
                snapshot_id=snapshot,
                observation_id="unresolved",
                kind="class",
                name="Missing",
                qualified_name="demo.Missing",
                repo_id="source-repo",
                source_file="",
            ),
            UnresolvedSymbolObservationFact(
                record_id=sha256(f"{snapshot}:unknown".encode()).hexdigest(),
                snapshot_id=snapshot,
                observation_id="unknown",
                kind="method",
                name="unknown",
                qualified_name="unknown",
            ),
        ]
    relationships = relationships or []
    return RelationshipHandoffResult(
        entity_count=len(entities),
        relationship_count=len(relationships),
        snapshot_id=snapshot,
        all_entities={fact.record_id: fact for fact in entities},
        all_relationships={fact.record_id: fact for fact in relationships},
    )


def relationship(snapshot, name="edge", **updates):
    return RelationshipFact.model_validate(
        {
            "record_id": sha256(f"{snapshot}:relationship:{name}".encode()).hexdigest(),
            "snapshot_id": snapshot,
            "relationship_type": "REFERENCES",
            "source_observation_id": "located",
            "target_observation_id": "external",
        }
        | updates
    )


def relationship_facts(snapshot):
    span = SourceSpan(
        repo_id="edge-repo",
        path="src/Service.java",
        commit_sha="b" * 40,
        start_line=3,
        end_line=5,
        start_column=0,
        end_column=10,
    )
    return [
        relationship(
            snapshot,
            "rich",
            evidence_ids=["evidence-a", "evidence-b"],
            source_span=span,
            source_edge_id="",
            original_relationship_type="references",
            original_edge={
                "source": "raw-source",
                "target": "raw-target",
                "details": {"values": [None, True, 3, 2.5, {"text": 'Größe "注文"\n'}]},
            },
            extractor_name="test-extractor",
            extractor_version="1.2.3",
        ),
        relationship(snapshot, "parallel", original_edge={}),
        relationship(
            snapshot,
            "unknown-type",
            relationship_type="custom`reference",
            source_observation_id="unresolved",
            target_observation_id="located",
            source_edge_id="raw-edge",
        ),
        relationship(
            snapshot,
            "self-loop",
            relationship_type="CALLS",
            source_observation_id="located",
            target_observation_id="located",
            source_span=span.model_copy(update={"start_column": None, "end_column": None}),
        ),
    ]


def records_by_id(entities):
    return {key: fact.to_record_dict() for key, fact in entities.items()}


def test_persists_all_entity_categories_and_directed_relationships(database):
    driver, snapshot = database
    relationship = RelationshipFact(
        record_id="e" * 64,
        snapshot_id=snapshot,
        relationship_type="REFERENCES",
        source_observation_id="located",
        target_observation_id="external",
    )
    original = replace(
        handoff(snapshot),
        relationship_count=1,
        all_relationships={relationship.record_id: relationship},
    )
    Neo4jPersistenceWriter(driver).persist_handoff(original)

    records, _, _ = driver.execute_query(
        "MATCH (n:Observation {snapshot_id: $snapshot}) RETURN properties(n) AS props, "
        "labels(n) AS labels",
        snapshot=snapshot,
        database_="neo4j",
    )
    assert len(records) == len(original.all_entities)
    assert {row["props"]["record_id"] for row in records} == set(original.all_entities)
    for row in records:
        assert set(row["labels"]) == {"Observation", row["props"]["record_type"]}
        assert all(not isinstance(value, dict) for value in row["props"].values())
    edges, _, _ = driver.execute_query(
        "MATCH (source:Observation {snapshot_id: $snapshot})-[r]->(target:Observation) "
        "RETURN source.observation_id AS source, target.observation_id AS target, "
        "type(r) AS type, r.record_id AS record_id",
        snapshot=snapshot,
        database_="neo4j",
    )
    assert [row.data() for row in edges] == [
        {
            "source": "located",
            "target": "external",
            "type": "REFERENCES",
            "record_id": relationship.record_id,
        }
    ]


def test_reconstructs_identical_json_records(database, tmp_path):
    driver, snapshot = database
    original = handoff(snapshot)
    expected_path = tmp_path / "entities.jsonl"
    actual_path = tmp_path / "restored.jsonl"
    write_jsonl_records(
        sorted(original.all_entities.values(), key=lambda fact: fact.record_id), expected_path
    )

    writer = Neo4jPersistenceWriter(driver)
    writer.persist_handoff(original)
    restored = writer.load_entities(snapshot)
    assert restored == original.all_entities
    write_jsonl_records(sorted(restored.values(), key=lambda fact: fact.record_id), actual_path)

    expected = [json.loads(line) for line in expected_path.read_text(encoding="utf-8").splitlines()]
    actual = [json.loads(line) for line in actual_path.read_text(encoding="utf-8").splitlines()]
    assert len(actual) == len(expected)
    assert {row["recordId"]: row for row in actual} == {row["recordId"]: row for row in expected}


def test_replacement_removes_old_nodes_and_properties_without_duplicates(database):
    driver, snapshot = database
    writer = Neo4jPersistenceWriter(driver)
    original = handoff(snapshot)
    writer.persist_handoff(original)
    source, _, external, unresolved, _ = original.all_entities.values()
    replacements = [
        source.model_copy(
            update={
                "name": "Updated",
                "source_span": source.source_span.model_copy(
                    update={"start_column": None, "end_column": None}
                ),
            }
        ),
        unresolved.model_copy(update={"repo_id": None, "source_file": None}),
        external.model_copy(
            update={
                "record_id": "f" * 64,
                "observation_id": "new-external",
                "name": "New",
            }
        ),
    ]
    replacement = handoff(snapshot, replacements)
    writer.persist_handoff(replacement)
    writer.persist_handoff(replacement)

    restored = writer.load_entities(snapshot)
    assert restored == replacement.all_entities
    records, _, _ = driver.execute_query(
        "MATCH (n:Observation {snapshot_id: $snapshot}) RETURN count(n) AS count",
        snapshot=snapshot,
        database_="neo4j",
    )
    assert records[0]["count"] == len(replacements)


def test_empty_replacement_preserves_other_snapshot_with_same_observation_ids(database):
    driver, snapshot = database
    writer = Neo4jPersistenceWriter(driver)
    original = handoff(snapshot, relationships=relationship_facts(snapshot))
    other_snapshot = f"{snapshot}-other"
    other = handoff(other_snapshot, relationships=relationship_facts(other_snapshot))
    writer.persist_handoff(original)
    writer.persist_handoff(other)
    assert records_by_id(writer.load_entities(snapshot)) == records_by_id(original.all_entities)

    writer.persist_handoff(handoff(snapshot, []))
    assert writer.load_entities(snapshot) == {}
    assert writer.load_relationships(snapshot) == {}
    assert records_by_id(writer.load_entities(other.snapshot_id)) == records_by_id(
        other.all_entities
    )
    assert writer.load_relationships(other.snapshot_id) == other.all_relationships


def test_reading_absent_snapshot_returns_empty_dictionary(database):
    driver, snapshot = database
    assert Neo4jPersistenceWriter(driver).load_entities(snapshot) == {}
    assert Neo4jPersistenceWriter(driver).load_relationships(snapshot) == {}


def test_failed_replacement_rolls_back_deletion(database):
    driver, snapshot = database
    writer = Neo4jPersistenceWriter(driver)
    original = handoff(snapshot, relationships=relationship_facts(snapshot))
    writer.persist_handoff(original)
    external = next(
        fact
        for fact in original.all_entities.values()
        if isinstance(fact, ExternalSymbolObservationFact)
    )
    duplicate = external.model_copy(update={"record_id": "f" * 64})

    with pytest.raises(ConstraintError):
        writer.persist_handoff(handoff(snapshot, [external, duplicate]))

    assert writer.load_entities(snapshot) == original.all_entities
    assert writer.load_relationships(snapshot) == original.all_relationships


def test_reconstructs_identical_relationship_records_and_native_graph(database, tmp_path):
    driver, snapshot = database
    original = handoff(snapshot, relationships=relationship_facts(snapshot))
    expected_path = tmp_path / "relationships.jsonl"
    actual_path = tmp_path / "restored-relationships.jsonl"
    write_jsonl_records(
        sorted(original.all_relationships.values(), key=lambda fact: fact.record_id), expected_path
    )
    writer = Neo4jPersistenceWriter(driver)
    writer.persist_handoff(original)
    restored = writer.load_relationships(snapshot)
    assert restored == original.all_relationships
    assert writer.load_entities(snapshot) == original.all_entities
    write_jsonl_records(sorted(restored.values(), key=lambda fact: fact.record_id), actual_path)
    expected = [json.loads(line) for line in expected_path.read_text(encoding="utf-8").splitlines()]
    actual = [json.loads(line) for line in actual_path.read_text(encoding="utf-8").splitlines()]
    assert len(actual) == len(expected)
    assert {row["recordId"]: row for row in actual} == {row["recordId"]: row for row in expected}

    edges, _, _ = driver.execute_query(
        "MATCH (source:Observation {snapshot_id: $snapshot})-[r]->(target:Observation) "
        "RETURN source.observation_id AS source, target.observation_id AS target, "
        "type(r) AS type, properties(r) AS props",
        snapshot=snapshot,
        database_="neo4j",
    )
    assert len(edges) == len(original.all_relationships)
    for edge in edges:
        fact = original.all_relationships[edge["props"]["record_id"]]
        assert (edge["source"], edge["target"], edge["type"]) == (
            fact.source_observation_id,
            fact.target_observation_id,
            fact.relationship_type,
        )
        assert all(not isinstance(value, dict) for value in edge["props"].values())


def test_relationship_replacement_removes_stale_edges_and_properties(database):
    driver, snapshot = database
    writer = Neo4jPersistenceWriter(driver)
    facts = relationship_facts(snapshot)
    writer.persist_handoff(handoff(snapshot, relationships=facts))
    replacement = facts[0].model_copy(
        update={
            "source_span": None,
            "original_edge": None,
            "original_relationship_type": None,
            "source_edge_id": None,
            "evidence_ids": [],
        }
    )
    updated = handoff(snapshot, relationships=[replacement])
    writer.persist_handoff(updated)
    writer.persist_handoff(updated)
    assert writer.load_relationships(snapshot) == updated.all_relationships
    edges, _, _ = driver.execute_query(
        "MATCH (:Observation {snapshot_id: $snapshot})-[r]->() RETURN count(r) AS count",
        snapshot=snapshot,
        database_="neo4j",
    )
    assert edges[0]["count"] == 1

    writer.persist_handoff(handoff(snapshot))
    assert writer.load_relationships(snapshot) == {}
    assert writer.load_entities(snapshot) == updated.all_entities


@pytest.mark.parametrize("role", ["source", "target"])
@pytest.mark.parametrize("exists_in_other_snapshot", [False, True])
def test_missing_endpoints_roll_back_nodes_and_edges(database, role, exists_in_other_snapshot):
    driver, snapshot = database
    writer = Neo4jPersistenceWriter(driver)
    original = handoff(snapshot, relationships=relationship_facts(snapshot))
    writer.persist_handoff(original)
    if exists_in_other_snapshot:
        other_snapshot = f"{snapshot}-other"
        other = handoff(
            other_snapshot,
            entities=[
                ExternalSymbolObservationFact(
                    record_id="f" * 64,
                    snapshot_id=other_snapshot,
                    observation_id="missing",
                    name="Other snapshot only",
                    qualified_name="other.Missing",
                )
            ],
        )
        writer.persist_handoff(other)

    invalid = relationship(snapshot, "invalid", **{f"{role}_observation_id": "missing"})
    entities = [
        fact.model_copy(update={"name": "Should roll back"})
        for fact in original.all_entities.values()
    ]
    with pytest.raises(ValueError) as error:
        writer.persist_handoff(handoff(snapshot, entities=entities, relationships=[invalid]))
    assert invalid.record_id in str(error.value)
    assert role in str(error.value)
    assert "missing" in str(error.value)
    assert snapshot in str(error.value)
    assert writer.load_entities(snapshot) == original.all_entities
    assert writer.load_relationships(snapshot) == original.all_relationships
    if exists_in_other_snapshot:
        assert writer.load_entities(other_snapshot) == other.all_entities


@pytest.mark.parametrize(
    "relationship_type", ["REFERENCES", "custom`reference", r"custom\u0060type"]
)
def test_relationship_record_id_is_unique_within_native_type(database, relationship_type):
    driver, snapshot = database
    fact = relationship(snapshot, relationship_type=relationship_type)
    writer = Neo4jPersistenceWriter(driver)
    writer.persist_handoff(handoff(snapshot, relationships=[fact]))
    with pytest.raises(ConstraintError):
        driver.execute_query(
            "MATCH (source:Observation {snapshot_id: $snapshot, observation_id: 'located'}), "
            "(target:Observation {snapshot_id: $snapshot, observation_id: 'external'}) "
            "CREATE (source)-[:$($relationship_type) {record_id: $record_id}]->(target)",
            snapshot=snapshot,
            record_id=fact.record_id,
            relationship_type=relationship_type,
            database_="neo4j",
        )
    assert writer.load_relationships(snapshot) == {fact.record_id: fact}
