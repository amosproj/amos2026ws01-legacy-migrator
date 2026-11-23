"""Read the canonical handoff files produced by ingestion."""

import json
from collections.abc import Callable, Collection
from pathlib import Path

from migration_assistant.domain.pipeline import (
    HandoffImportIssue,
    PipelineError,
    RelationshipHandoffResult,
)
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
    """Restore valid facts from one snapshot and report rejected rows."""
    issues: list[HandoffImportIssue] = []
    try:
        identity = SnapshotIdentity.model_validate_json(
            (directory / "snapshot-identity.json").read_text(encoding="utf-8")
        )
        entities = _read_facts(directory / "entities.jsonl", _entity_from_json, identity, issues)
        relationships = _read_facts(
            directory / "relationships.jsonl",
            RelationshipFact.from_json,
            identity,
            issues,
            endpoints={fact.observation_id for fact in entities.values()},
        )
    except (OSError, ValueError) as error:
        raise PipelineError(f"Cannot read handoff from {directory}: {error}") from error

    return RelationshipHandoffResult(
        entity_count=len(entities),
        relationship_count=len(relationships),
        snapshot_id=identity.snapshot_id,
        all_entities=entities,
        all_relationships=relationships,
        issues=tuple(issues),
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
    identity: SnapshotIdentity,
    issues: list[HandoffImportIssue],
    *,
    endpoints: Collection[str] = (),
) -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    observation_ids: set[str] = set()
    revisions = {member.repo_id: member.commit_sha for member in identity.source_members}
    with path.open("rb") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                fact = from_json(line.decode("utf-8"))
            except ValueError as error:
                issues.append(
                    HandoffImportIssue(str(path), line_number, "invalid_record", str(error))
                )
                continue

            issue = _fact_issue(
                fact, identity.snapshot_id, revisions, facts, observation_ids, endpoints
            )
            if issue is not None:
                issues.append(HandoffImportIssue(str(path), line_number, *issue))
                continue

            facts[fact.record_id] = fact
            if not isinstance(fact, RelationshipFact):
                observation_ids.add(fact.observation_id)
    return facts


def _fact_issue(
    fact: _EntityFact | RelationshipFact,
    snapshot_id: str,
    revisions: dict[str, str],
    records: Collection[str],
    observation_ids: set[str],
    endpoints: Collection[str],
) -> tuple[str, str] | None:
    if fact.snapshot_id != snapshot_id:
        return "snapshot_mismatch", f"Expected snapshot {snapshot_id}, got {fact.snapshot_id}"
    if fact.record_id in records:
        return "duplicate_record", f"Record ID {fact.record_id} already appeared"
    if isinstance(fact, SymbolObservationFact) and fact.repo_id != fact.source_span.repo_id:
        return "source_repo_mismatch", "Symbol repository disagrees with its source span"
    if isinstance(fact, (SymbolObservationFact, RelationshipFact)):
        span = fact.source_span
        if span is not None and revisions.get(span.repo_id) != span.commit_sha:
            return (
                "source_revision_mismatch",
                f"{span.repo_id} at {span.commit_sha} is outside this snapshot",
            )
    if isinstance(fact, RelationshipFact):
        missing = {fact.source_observation_id, fact.target_observation_id}.difference(endpoints)
        if missing:
            return "missing_endpoint", f"Unknown observation IDs: {', '.join(sorted(missing))}"
    elif fact.observation_id in observation_ids:
        return "duplicate_observation", f"Observation ID {fact.observation_id} already appeared"
    return None
