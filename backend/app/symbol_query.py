"""Typed symbol lookup over canonical ingestion facts (issue #95, first pass).

Reads the ``entities.jsonl`` handoff written by the ingestion pipeline and
returns the source-backed symbols of one component as a ``SymbolQueryResult``.
Until the graph store from #94 exists, this file reader stands in for it; the
same mapping will later be applied to rows read from the store.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from shared_contracts.records import (
    SymbolObservationRecord,
    SymbolQueryResult,
    SymbolQuerySymbol,
)

SYMBOL_RECORD_TYPE = "SymbolObservation"


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


def to_query_symbol(record: SymbolObservationRecord) -> SymbolQuerySymbol:
    """Map one canonical symbol record to a typed query row, keeping its evidence."""
    payload = record.payload
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
    records: Iterable[SymbolObservationRecord],
    step_id: str,
    component: str,
) -> SymbolQueryResult:
    """Return the symbols of ``component`` as a ``SymbolQueryResult`` for ``step_id``.

    ``component`` is the repository ID used in the facts, for example
    ``legacy-example-catalog-service``. Symbols are sorted by file and line so
    repeated queries over the same facts return the same result.
    """
    symbols = [to_query_symbol(record) for record in records if record.payload.repo_id == component]
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
