from neo4j import Driver

from migration_assistant.domain.pipeline import RelationshipHandoffResult

class Neo4jPersistenceWriter:
    def __init__(self, driver: Driver) -> None:
        self.driver = driver

    def persist_handoff(self, handoff: RelationshipHandoffResult) -> None:
        records, _, _ = self.driver.execute_query("RETURN 1 AS result", database_="neo4j")
        print(f"Neo4j query result: {records[0]['result']}")
        print(
            f"Handoff received: {len(handoff.all_entities)} entities, "
            f"{len(handoff.all_relationships)} relationships"
        )
