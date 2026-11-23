"""Read the canonical handoff files produced by ingestion."""

import json
from collections.abc import Callable
from pathlib import Path

from migration_assistant.domain.pipeline import PipelineError, RelationshipHandoffResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    SnapshotIdentity,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)

type _EntityFact = (
    SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
)

_ENTITY_FACT_TYPES: dict[str, type[_EntityFact]] = {
    "SymbolObservation": SymbolObservationFact,
    "ExternalSymbolObservation": ExternalSymbolObservationFact,
    "UnresolvedSymbolObservation": UnresolvedSymbolObservationFact,
}


def read_relationship_handoff(directory: Path) -> RelationshipHandoffResult:
    """Restore saved facts; consistency checks belong to writing and persistence."""
    try:
        identity = SnapshotIdentity.model_validate_json(
            (directory / "snapshot-identity.json").read_text(encoding="utf-8")
        )
        entities = _read_facts(directory / "entities.jsonl", _entity_from_json)
        relationships = _read_facts(directory / "relationships.jsonl", RelationshipFact.from_json)
    except (OSError, ValueError) as error:
        raise PipelineError(f"Cannot read handoff from {directory}: {error}") from error

    return RelationshipHandoffResult(
        entity_count=len(entities),
        relationship_count=len(relationships),
        snapshot_id=identity.snapshot_id,
        all_entities=entities,
        all_relationships=relationships,
    )


def _entity_from_json(data: str) -> _EntityFact:
    record = json.loads(data)
    if not isinstance(record, dict) or not isinstance(record.get("recordType"), str):
        raise ValueError("Expected an entity object with recordType")
    fact_type = _ENTITY_FACT_TYPES.get(record["recordType"])
    if fact_type is None:
        raise ValueError(f"Unknown entity recordType: {record['recordType']}")
    return fact_type.from_json(data)


def _read_facts[Fact: _EntityFact | RelationshipFact](
    path: Path,
    from_json: Callable[[str], Fact],
) -> dict[str, Fact]:
    facts = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                fact = from_json(line)
                facts[fact.record_id] = fact
            except ValueError as error:
                raise ValueError(f"{path}:{line_number}: {error}") from error
    return facts
