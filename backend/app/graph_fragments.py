"""Resolve chat evidence from an imported reference snapshot."""

import re

from neo4j.exceptions import DriverError, Neo4jError

from migration_assistant.api import load_snapshot
from shared_contracts.records import SnapshotIdentity, SymbolQueryResult

from .source_fragments import (
    FragmentPosition,
    SourceFragment,
    SourceFragmentError,
    resolve_fragment,
)
from .source_loader_adapter import LoaderFragmentFetcher
from .symbol_query import query_snapshot_symbols

CATALOG_REPOSITORY = "legacy-example-catalog-service"
ROUTE_TERMS = {"endpoint", "endpoints", "route", "routes", "endpunkt", "endpunkte", "routen"}


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
    fetcher: LoaderFragmentFetcher,
) -> list[SourceFragment]:
    """Find named Catalog symbols and resolve their pinned source evidence."""
    revisions = fetcher.revisions_for_stage(step_id)
    if not revisions:
        raise SourceFragmentError("stage_not_loaded", f"No source export is loaded for {step_id}.")
    if revisions != {member.repo_id: member.commit_sha for member in snapshot.source_members}:
        raise SourceFragmentError(
            "commit_sha_mismatch",
            "The graph snapshot and the source export have different repository revisions.",
        )
    try:
        result = query_snapshot_symbols(
            lambda snapshot_id: load_snapshot(snapshot_id).all_entities.values(),
            snapshot.snapshot_id,
            step_id,
            CATALOG_REPOSITORY,
        )
    except (DriverError, Neo4jError, ValueError) as error:
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
