"""Adapt typed graph hits to the source fragment service."""

from shared_contracts.records import SymbolQueryResult

from .source_fragments import FragmentPosition


def fragment_positions(result: SymbolQueryResult) -> list[FragmentPosition]:
    """Return one position per symbol in result order, carrying the query's stage."""
    return [
        FragmentPosition.model_validate(
            {**symbol.source_span.model_dump(), "stage": result.step_id}
        )
        for symbol in result.symbols
    ]
