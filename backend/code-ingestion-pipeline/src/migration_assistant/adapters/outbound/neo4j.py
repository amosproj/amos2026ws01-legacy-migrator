"""Persist observation and relationship facts and reconstruct them on read."""

import json
from hashlib import sha256
from typing import Any, LiteralString, cast

from neo4j import Driver, ManagedTransaction

from migration_assistant.domain.pipeline import RelationshipHandoffResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)

type EntityFact = (
    SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
)

_FACT_TYPES: dict[LiteralString, type[EntityFact]] = {
    "SymbolObservation": SymbolObservationFact,
    "ExternalSymbolObservation": ExternalSymbolObservationFact,
    "UnresolvedSymbolObservation": UnresolvedSymbolObservationFact,
}


class Neo4jPersistenceWriter:
    def __init__(self, driver: Driver) -> None:
        self.driver = driver

    def persist_handoff(self, handoff: RelationshipHandoffResult) -> None:
        """Atomically replace the observation subgraph belonging to this snapshot."""
        grouped: dict[LiteralString, list[dict[str, Any]]] = {label: [] for label in _FACT_TYPES}
        for fact in handoff.all_entities.values():
            properties = fact.model_dump(exclude={"source_span"}, exclude_none=True)
            if isinstance(fact, SymbolObservationFact):
                properties.update(
                    {
                        f"span_{key}": value
                        for key, value in fact.source_span.model_dump(exclude_none=True).items()
                    }
                )
            grouped[fact.record_type].append(properties)

        relationships: list[dict[str, Any]] = []
        for fact in handoff.all_relationships.values():
            properties = fact.model_dump(
                exclude={
                    "record_type",
                    "relationship_type",
                    "source_observation_id",
                    "target_observation_id",
                    "source_span",
                    "original_edge",
                },
                exclude_none=True,
            )
            if fact.source_span is not None:
                properties.update(
                    {
                        f"span_{key}": value
                        for key, value in fact.source_span.model_dump(exclude_none=True).items()
                    }
                )
            if fact.original_edge is not None:
                properties["original_edge_json"] = json.dumps(
                    fact.original_edge, ensure_ascii=False
                )
            relationships.append(
                {
                    "relationship_type": str(fact.relationship_type),
                    "source_observation_id": fact.source_observation_id,
                    "target_observation_id": fact.target_observation_id,
                    "properties": properties,
                }
            )

        self.driver.execute_query(
            "CREATE CONSTRAINT observation_identity IF NOT EXISTS "
            "FOR (n:Observation) REQUIRE (n.snapshot_id, n.observation_id) IS UNIQUE",
            database_="neo4j",
        )
        for relationship_type in {row["relationship_type"] for row in relationships}:
            # Preserve literal backslashes through Cypher's Unicode-escape preprocessing.
            escaped_type = relationship_type.replace("\\", r"\u005C").replace("`", "``")
            # Constraint types require a quoted identifier; names and data remain parameters.
            query = cast(
                LiteralString,
                "CREATE CONSTRAINT $name IF NOT EXISTS "
                f"FOR ()-[r:`{escaped_type}`]-() REQUIRE r.record_id IS UNIQUE",
            )
            self.driver.execute_query(
                query,
                name=f"relationship_record_id_{sha256(relationship_type.encode()).hexdigest()}",
                database_="neo4j",
            )
        with self.driver.session(database="neo4j") as session:
            session.execute_write(
                self._replace_snapshot, handoff.snapshot_id, grouped, relationships
            )

    @staticmethod
    def _replace_snapshot(
        tx: ManagedTransaction,
        snapshot_id: str,
        grouped: dict[LiteralString, list[dict[str, Any]]],
        relationships: list[dict[str, Any]],
    ) -> None:
        tx.run(
            "MATCH (:Observation {snapshot_id: $snapshot_id})-[r]->"
            "(:Observation {snapshot_id: $snapshot_id}) "
            "WHERE r.snapshot_id = $snapshot_id DELETE r",
            snapshot_id=snapshot_id,
        ).consume()
        tx.run(
            "MATCH (n:Observation {snapshot_id: $snapshot_id}) DELETE n",
            snapshot_id=snapshot_id,
        ).consume()
        for label, entities in grouped.items():
            if entities:
                tx.run(
                    f"UNWIND $entities AS entity CREATE (n:Observation:{label}) SET n = entity",
                    entities=entities,
                ).consume()

        if relationships:
            missing = tx.run(
                "UNWIND $relationships AS relationship "
                "OPTIONAL MATCH (source:Observation {snapshot_id: $snapshot_id, "
                "observation_id: relationship.source_observation_id}) "
                "OPTIONAL MATCH (target:Observation {snapshot_id: $snapshot_id, "
                "observation_id: relationship.target_observation_id}) "
                "WITH relationship, source, target WHERE source IS NULL OR target IS NULL "
                "RETURN relationship.properties.record_id AS record_id, "
                "relationship.source_observation_id AS source_id, "
                "relationship.target_observation_id AS target_id, "
                "source IS NULL AS source_missing LIMIT 1",
                snapshot_id=snapshot_id,
                relationships=relationships,
            ).single()
            if missing is not None:
                role = "source" if missing["source_missing"] else "target"
                raise ValueError(
                    f"Relationship {missing['record_id']} missing {role} observation "
                    f"{missing[f'{role}_id']} in snapshot {snapshot_id}"
                )
            tx.run(
                "UNWIND $relationships AS relationship "
                "MATCH (source:Observation {snapshot_id: $snapshot_id, "
                "observation_id: relationship.source_observation_id}), "
                "(target:Observation {snapshot_id: $snapshot_id, "
                "observation_id: relationship.target_observation_id}) "
                "CREATE (source)-[r:$(relationship.relationship_type)]->(target) "
                "SET r = relationship.properties",
                snapshot_id=snapshot_id,
                relationships=relationships,
            ).consume()

    def load_entities(self, snapshot_id: str) -> dict[str, EntityFact]:
        """Read one snapshot into the same fact dictionary shape as all_entities."""
        records, _, _ = self.driver.execute_query(
            "MATCH (n:Observation {snapshot_id: $snapshot_id}) "
            "RETURN properties(n) AS properties ORDER BY n.record_id",
            snapshot_id=snapshot_id,
            database_="neo4j",
        )
        entities = {}
        for record in records:
            properties = record["properties"]
            values = {
                key: value for key, value in properties.items() if not key.startswith("span_")
            }
            if values["record_type"] == "SymbolObservation":
                values["source_span"] = {
                    key.removeprefix("span_"): value
                    for key, value in properties.items()
                    if key.startswith("span_")
                }
            fact = _FACT_TYPES[values["record_type"]].model_validate(values)
            entities[fact.record_id] = fact
        return entities

    def load_relationships(self, snapshot_id: str) -> dict[str, RelationshipFact]:
        """Reconstruct one snapshot's relationship facts from edges and their endpoints."""
        records, _, _ = self.driver.execute_query(
            "MATCH (source:Observation {snapshot_id: $snapshot_id})-[r]->"
            "(target:Observation {snapshot_id: $snapshot_id}) "
            "WHERE r.snapshot_id = $snapshot_id "
            "RETURN properties(r) AS properties, type(r) AS relationship_type, "
            "source.observation_id AS source_id, target.observation_id AS target_id "
            "ORDER BY r.record_id",
            snapshot_id=snapshot_id,
            database_="neo4j",
        )
        relationships = {}
        for record in records:
            properties = record["properties"]
            values = {
                key: value
                for key, value in properties.items()
                if not key.startswith("span_") and key != "original_edge_json"
            }
            values.update(
                relationship_type=record["relationship_type"],
                source_observation_id=record["source_id"],
                target_observation_id=record["target_id"],
            )
            span = {
                key.removeprefix("span_"): value
                for key, value in properties.items()
                if key.startswith("span_")
            }
            if span:
                values["source_span"] = span
            if "original_edge_json" in properties:
                values["original_edge"] = json.loads(properties["original_edge_json"])
            fact = RelationshipFact.model_validate(values)
            relationships[fact.record_id] = fact
        return relationships
