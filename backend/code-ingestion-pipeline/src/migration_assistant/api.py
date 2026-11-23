"""Python entry points for ingestion, handoff persistence, and snapshot reads."""

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from neo4j import GraphDatabase

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.adapters.outbound.graphify import GraphifyAdapter
from migration_assistant.adapters.outbound.graphify_relationships import write_relationship_handoff
from migration_assistant.adapters.outbound.neo4j import Neo4jPersistenceWriter
from migration_assistant.adapters.outbound.pipeline_storage import LocalPipelineStorage
from migration_assistant.adapters.outbound.relationship_handoff import read_relationship_handoff
from migration_assistant.application.pipeline import PipelineService
from migration_assistant.domain.pipeline import (
    HandoffImportError,
    PipelineResult,
    RelationshipHandoffResult,
)
from migration_assistant.domain.reference_source import ReferenceSourceConfig
from migration_assistant.domain.sources import LoadResult

__all__ = ["ingest_step", "load_snapshot", "persist_handoff"]


def ingest_step(
    config: ReferenceSourceConfig,
    output_dir: Path,
    *,
    source_export: Path | None = None,
    on_loaded: Callable[[LoadResult], None] | None = None,
    progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Generate and persist the stage selected by config, returning its run result."""
    with _persistence_writer() as writer:
        service = PipelineService(
            git_repo=LocalGitAdapter(),
            source_loader=load_sources,
            graph_builder=GraphifyAdapter(),
            handoff_writer=write_relationship_handoff,
            storage=LocalPipelineStorage(),
            persistence_writer=writer,
        )
        return service.run(
            config,
            output_dir,
            source_export=source_export,
            on_loaded=on_loaded,
            progress=progress,
        )


def persist_handoff(handoff_dir: Path) -> RelationshipHandoffResult:
    """Persist valid facts from an existing run and return any rejected rows."""
    handoff = read_relationship_handoff(handoff_dir)
    if not handoff.all_entities:
        raise HandoffImportError(handoff_dir, handoff.issues)
    with _persistence_writer() as writer:
        writer.persist_handoff(handoff)
    return handoff


def load_snapshot(snapshot_id: str) -> RelationshipHandoffResult:
    """Load entities and relationships; absent snapshots return empty dictionaries."""
    with _persistence_writer() as writer:
        entities = writer.load_entities(snapshot_id)
        relationships = writer.load_relationships(snapshot_id)
    return RelationshipHandoffResult(
        entity_count=len(entities),
        relationship_count=len(relationships),
        snapshot_id=snapshot_id,
        all_entities=entities,
        all_relationships=relationships,
    )


@contextmanager
def _persistence_writer() -> Generator[Neo4jPersistenceWriter]:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    with GraphDatabase.driver(uri, auth=("neo4j", "change-this")) as driver:
        driver.verify_connectivity()
        yield Neo4jPersistenceWriter(driver)
