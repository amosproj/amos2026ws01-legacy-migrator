"""Typed symbol lookup over persisted snapshots and canonical exports."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path

from shared_contracts.records import (
    ExternalSymbolObservationFact,
    SymbolObservationFact,
    SymbolObservationRecord,
    SymbolQueryResult,
    SymbolQuerySymbol,
    UnresolvedSymbolObservationFact,
)

SYMBOL_RECORD_TYPE = "SymbolObservation"
type SnapshotEntity = (
    SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
)


def load_symbol_records(entities_jsonl: Path) -> list[SymbolObservationRecord]:
    """Return the source-backed symbol records from an ``entities.jsonl`` file.

    External and unresolved observations are skipped: they have no verified
    source span, so they cannot become a ``SymbolQuerySymbol``.
    """
    records: list[SymbolObservationRecord] = []
    with entities_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("recordType") != SYMBOL_RECORD_TYPE:
                continue
            records.append(SymbolObservationRecord.model_validate(raw))
    return records


def to_query_symbol(record: SymbolObservationRecord | SymbolObservationFact) -> SymbolQuerySymbol:
    """Map one canonical symbol record to a typed query row, keeping its evidence."""
    payload = record.payload if isinstance(record, SymbolObservationRecord) else record
    return SymbolQuerySymbol(
        id=payload.observation_id,
        name=payload.name,
        observation_id=payload.observation_id,
        kind=payload.kind,
        qualified_name=payload.qualified_name,
        repo_id=payload.repo_id,
        source_span=payload.source_span,
    )


def query_component_symbols(
    records: Iterable[SymbolObservationRecord | SymbolObservationFact],
    step_id: str,
    component: str,
) -> SymbolQueryResult:
    """Build a ``SymbolQueryResult`` from records already selected for ``step_id``.

    ``component`` is the repository ID used in the facts, for example
    ``legacy-example-catalog-service``. The caller selects the snapshot for the
    stage before calling this function. Symbols are sorted by file and line.
    """
    symbols = [symbol for symbol in map(to_query_symbol, records) if symbol.repo_id == component]
    symbols.sort(
        key=lambda symbol: (
            symbol.source_span.path,
            symbol.source_span.start_line,
            symbol.qualified_name,
        )
    )
    return SymbolQueryResult(
        step_id=step_id,
        component=component,
        symbols=symbols,
        total_symbols=len(symbols),
    )


def query_snapshot_symbols(
    load_entities: Callable[[str], Iterable[SnapshotEntity]],
    snapshot_id: str,
    step_id: str,
    component: str,
) -> SymbolQueryResult:
    """Query source-backed symbols in one explicitly selected snapshot."""
    records = (
        fact
        for fact in load_entities(snapshot_id)
        if isinstance(fact, SymbolObservationFact) and fact.repo_id == component
    )
    return query_component_symbols(records, step_id, component)
