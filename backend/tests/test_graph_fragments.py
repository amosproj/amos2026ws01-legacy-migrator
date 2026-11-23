"""Check the graph-to-fragment adapter against the recorded Catalog export."""

from pathlib import Path

import pytest

from app.graph_fragments import fragment_positions
from app.source_fragments import SourceFragmentError, resolve_fragment
from app.source_loader_adapter import LoaderFragmentFetcher
from app.symbol_query import load_symbol_records, query_component_symbols
from shared_contracts.records import SymbolQueryResult

FIXTURES = Path(__file__).parent / "fixtures"
REPOSITORY = "legacy-example-catalog-service"
STEP = "step-06"
ROUTE_LINES = {"CategoryResource": 17, "ProductResource": 28}


@pytest.fixture
def routes() -> SymbolQueryResult:
    records = load_symbol_records(FIXTURES / "catalog-service-step-06-entities.jsonl")
    return query_component_symbols(
        (
            record
            for record in records
            if record.payload.kind == "class" and record.payload.name in ROUTE_LINES
        ),
        STEP,
        REPOSITORY,
    )


@pytest.fixture
def fetcher() -> LoaderFragmentFetcher:
    return LoaderFragmentFetcher.from_export(FIXTURES / "catalog-service-step-06-sources.jsonl")


@pytest.mark.parametrize("step_id", [STEP, "step-05"])
def test_adapter_keeps_result_order_and_source_positions(
    routes: SymbolQueryResult, step_id: str
) -> None:
    result = routes.model_copy(update={"step_id": step_id})
    positions = fragment_positions(result)

    assert len(positions) == len(ROUTE_LINES)
    for symbol, position in zip(result.symbols, positions, strict=True):
        assert position.stage == step_id
        assert position.model_dump(exclude={"stage"}) == symbol.source_span.model_dump()


def test_adapter_preserves_optional_columns(routes: SymbolQueryResult) -> None:
    original = routes.symbols[0]
    span = original.source_span.model_copy(update={"start_column": 0, "end_column": 5})
    symbol = original.model_copy(update={"source_span": span})
    result = routes.model_copy(update={"symbols": [symbol], "total_symbols": 1})

    (position,) = fragment_positions(result)

    assert position.start_column == 0
    assert position.end_column == 5


def test_adapter_provides_positions_for_both_catalog_routes(
    routes: SymbolQueryResult, fetcher: LoaderFragmentFetcher
) -> None:
    fragments = [resolve_fragment(position, fetcher) for position in fragment_positions(routes)]

    assert {Path(fragment.position.path).stem for fragment in fragments} == ROUTE_LINES.keys()
    for symbol, fragment in zip(routes.symbols, fragments, strict=True):
        line = ROUTE_LINES[symbol.name]
        resource = symbol.name.removesuffix("Resource")
        assert fragment.fragment == f'@Path("/CustomerOrderServicesWeb/jaxrs/{resource}")'
        assert fragment.github_url == (
            f"https://github.com/legacy-modernization-example/{REPOSITORY}/blob/"
            f"{symbol.source_span.commit_sha}/{symbol.source_span.path}#L{line}-L{line}"
        )


def test_lookup_reports_stale_query_position(
    routes: SymbolQueryResult, fetcher: LoaderFragmentFetcher
) -> None:
    original = routes.symbols[0]
    stale_span = original.source_span.model_copy(update={"commit_sha": "0" * 40})
    stale_symbol = original.model_copy(update={"source_span": stale_span})
    stale_result = routes.model_copy(update={"symbols": [stale_symbol], "total_symbols": 1})
    (position,) = fragment_positions(stale_result)

    with pytest.raises(SourceFragmentError) as error:
        resolve_fragment(position, fetcher)

    assert error.value.code == "commit_sha_mismatch"


def test_adapter_accepts_empty_query_results() -> None:
    result = query_component_symbols([], STEP, REPOSITORY)

    assert fragment_positions(result) == []
