"""Resolve chat evidence from an imported reference snapshot."""

import re
from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from typing import Protocol, runtime_checkable

from shared_contracts.records import (
    ExternalSymbolObservationFact,
    SnapshotIdentity,
    SymbolObservationFact,
    SymbolQueryResult,
    UnresolvedSymbolObservationFact,
)

from .source_fragments import (
    FragmentFetcher,
    FragmentPosition,
    SourceFragment,
    SourceFragmentError,
    resolve_fragment,
)

CATALOG_REPOSITORY = "legacy-example-catalog-service"
ROUTE_TERMS = {"endpoint", "endpoints", "route", "routes", "endpunkt", "endpunkte", "routen"}
GRAPH_INSTALL_MESSAGE = (
    "Graph chat requires the persistence, symbol query and source revision changes."
)
type _SnapshotEntity = (
    SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
)


class _SnapshotFacts(Protocol):
    @property
    def all_entities(self) -> Mapping[str, _SnapshotEntity]: ...


@runtime_checkable
class _SnapshotReader(Protocol):
    def load_snapshot(self, snapshot_id: str) -> _SnapshotFacts: ...


@runtime_checkable
class _SnapshotQuery(Protocol):
    def query_snapshot_symbols(
        self,
        load_entities: Callable[[str], Iterable[_SnapshotEntity]],
        snapshot_id: str,
        step_id: str,
        component: str,
    ) -> SymbolQueryResult: ...


@runtime_checkable
class _StageFragmentFetcher(FragmentFetcher, Protocol):
    def revisions_for_stage(self, stage: str) -> dict[str, str]: ...


def fragment_positions(result: SymbolQueryResult) -> list[FragmentPosition]:
    """Return one position per symbol in result order, carrying the query's stage."""
    return [
        FragmentPosition.model_validate(
            {**symbol.source_span.model_dump(), "stage": result.step_id}
        )
        for symbol in result.symbols
    ]


def resolve_question_fragments(
    question: str,
    step_id: str,
    snapshot: SnapshotIdentity,
    fetcher: FragmentFetcher,
) -> list[SourceFragment]:
    """Find named Catalog symbols and resolve their pinned source evidence."""
    if not isinstance(fetcher, _StageFragmentFetcher):
        raise SourceFragmentError("graph_integration_unavailable", GRAPH_INSTALL_MESSAGE)
    try:
        reader = import_module("migration_assistant.api")
        query = import_module("app.symbol_query")
        neo4j_errors = import_module("neo4j.exceptions")
    except ModuleNotFoundError as error:
        if error.name not in {"migration_assistant.api", "neo4j", "neo4j.exceptions"}:
            raise
        raise SourceFragmentError("graph_integration_unavailable", GRAPH_INSTALL_MESSAGE) from error
    if not isinstance(reader, _SnapshotReader) or not isinstance(query, _SnapshotQuery):
        raise SourceFragmentError("graph_integration_unavailable", GRAPH_INSTALL_MESSAGE)

    revisions = fetcher.revisions_for_stage(step_id)
    if not revisions:
        raise SourceFragmentError("stage_not_loaded", f"No source export is loaded for {step_id}.")
    if revisions != {member.repo_id: member.commit_sha for member in snapshot.source_members}:
        raise SourceFragmentError(
            "commit_sha_mismatch",
            "The graph snapshot and the source export have different repository revisions.",
        )
    try:
        result = query.query_snapshot_symbols(
            lambda snapshot_id: reader.load_snapshot(snapshot_id).all_entities.values(),
            snapshot.snapshot_id,
            step_id,
            CATALOG_REPOSITORY,
        )
    except (neo4j_errors.DriverError, neo4j_errors.Neo4jError, ValueError) as error:
        raise SourceFragmentError(
            "graph_lookup_failed", "Could not read the Catalog symbols from Neo4j."
        ) from error
    if not result.symbols:
        raise SourceFragmentError(
            "catalog_not_loaded", f"No Catalog symbols are stored for the selected {step_id} run."
        )

    terms = set(re.findall(r"\w+", question.casefold()))
    if terms & ROUTE_TERMS:
        hits = [
            symbol
            for symbol in result.symbols
            if symbol.kind == "class"
            and symbol.name.endswith("Resource")
            and (
                symbol.name.casefold() in terms
                or symbol.name.removesuffix("Resource").casefold() in terms
            )
        ]
    else:
        hits = [
            symbol
            for symbol in result.symbols
            if symbol.kind != "file"
            and symbol.name.strip(".").removesuffix("()").casefold() in terms
        ]
    if not hits:
        raise SourceFragmentError(
            "no_source_hits", "No Catalog symbols matched. Try naming an endpoint or a symbol."
        )

    selected = result.model_copy(update={"symbols": hits, "total_symbols": len(hits)})
    return [resolve_fragment(position, fetcher) for position in fragment_positions(selected)]
