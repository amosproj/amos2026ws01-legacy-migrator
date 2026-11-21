"""Persist observation facts as flat Neo4j nodes and reconstruct them on read."""

from typing import Any, LiteralString

from neo4j import Driver, ManagedTransaction

from migration_assistant.domain.pipeline import RelationshipHandoffResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
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
        """Atomically replace the observation nodes belonging to this snapshot."""
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

        self.driver.execute_query(
            "CREATE CONSTRAINT observation_identity IF NOT EXISTS "
            "FOR (n:Observation) REQUIRE (n.snapshot_id, n.observation_id) IS UNIQUE",
            database_="neo4j",
        )
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._replace_entities, handoff.snapshot_id, grouped)

    @staticmethod
    def _replace_entities(
        tx: ManagedTransaction, snapshot_id: str, grouped: dict[LiteralString, list[dict[str, Any]]]
    ) -> None:
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
