"""Results and expected failures of a complete ingestion run."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from migration_assistant.domain.sources import LoadResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)


class PipelineError(Exception):
    """An ingestion stage could not produce its required outputs."""


@dataclass(frozen=True)
class HandoffImportIssue:
    """A row rejected while loading a saved run."""

    file: str
    line: int
    code: str
    message: str


class HandoffImportError(PipelineError):
    """A saved run has no valid entities to persist."""

    def __init__(self, directory: Path, issues: tuple[HandoffImportIssue, ...]) -> None:
        self.issues = issues
        super().__init__(f"No valid entities in {directory}. The existing snapshot was kept.")


@dataclass(frozen=True)
class RelationshipHandoffResult:
    """Facts, counts, and the deterministic snapshot identity produced by the handoff."""

    entity_count: int
    relationship_count: int
    snapshot_id: str
    all_entities: dict[
        str, SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
    ]
    all_relationships: dict[str, RelationshipFact]
    issues: tuple[HandoffImportIssue, ...] = ()

    def __iter__(self) -> Iterator[int]:
        """Keep existing two-value count unpacking working for the CLI."""
        yield self.entity_count
        yield self.relationship_count


@dataclass(frozen=True)
class PipelineResult:
    load_result: LoadResult
    run_directory: Path
    graph_paths: dict[str, Path]
    entity_count: int
    relationship_count: int
    snapshot_id: str
