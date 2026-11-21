"""Tests for the typed symbol lookup over step-06 catalog-service facts (issue #95).

The fixtures are the unmodified ingestion output for
``ingest --stage step-06 --components catalog-service``.
"""

import json
from pathlib import Path

import pytest

from app.symbol_query import load_symbol_records, query_component_symbols
from shared_contracts.records import SymbolQueryResult, SymbolQuerySymbol

FIXTURES = Path(__file__).parent / "fixtures"
ENTITIES = FIXTURES / "catalog-service-step-06-entities.jsonl"
SOURCES = FIXTURES / "catalog-service-step-06-sources.jsonl"

STEP_ID = "step-06"
COMPONENT = "legacy-example-catalog-service"
COMMIT_SHA = "474422cf156eb9bcce4267578b089a15edcc3733"
EXPECTED_SYMBOLS = 30


@pytest.fixture(scope="module")
def result() -> SymbolQueryResult:
    return query_component_symbols(load_symbol_records(ENTITIES), STEP_ID, COMPONENT)


def _raw_symbol_payloads() -> dict[str, dict]:
    payloads = {}
    for line in ENTITIES.read_text(encoding="utf-8").splitlines():
        raw = json.loads(line)
        if raw["recordType"] == "SymbolObservation":
            payloads[raw["payload"]["observationId"]] = raw["payload"]
    return payloads


def test_only_source_backed_symbols_are_loaded():
    # The fixture also holds external and unresolved observations without a span.
    all_lines = ENTITIES.read_text(encoding="utf-8").splitlines()
    assert len(all_lines) > EXPECTED_SYMBOLS
    assert len(load_symbol_records(ENTITIES)) == EXPECTED_SYMBOLS


def test_result_is_typed_and_scoped_to_step_and_component(result: SymbolQueryResult):
    assert result.step_id == STEP_ID
    assert result.component == COMPONENT
    assert result.total_symbols == EXPECTED_SYMBOLS
    assert all(isinstance(symbol, SymbolQuerySymbol) for symbol in result.symbols)


def test_symbols_keep_ingestion_identity_and_metadata(result: SymbolQueryResult):
    payloads = _raw_symbol_payloads()
    assert {symbol.observation_id for symbol in result.symbols} == set(payloads)
    for symbol in result.symbols:
        payload = payloads[symbol.observation_id]
        assert symbol.id == symbol.observation_id
        assert symbol.name == payload["name"]
        assert symbol.qualified_name == payload["qualifiedName"]
        assert symbol.kind == payload["kind"]
        span = symbol.source_span.model_dump(by_alias=True, exclude_none=True)
        assert span == payload["sourceSpan"]


def test_every_span_resolves_to_a_line_in_the_loaded_sources(result: SymbolQueryResult):
    line_counts = {}
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        source = json.loads(line)
        key = (source["repoId"], source["commitSha"], source["path"])
        line_counts[key] = len(source["content"].splitlines())

    for symbol in result.symbols:
        span = symbol.source_span
        assert span.repo_id == COMPONENT
        assert span.commit_sha == COMMIT_SHA
        key = (span.repo_id, span.commit_sha, span.path)
        assert key in line_counts, f"{span.path} is missing from sources.jsonl"
        assert 1 <= span.start_line <= span.end_line <= line_counts[key]


def test_known_class_is_returned_with_its_position(result: SymbolQueryResult):
    product = next(
        symbol for symbol in result.symbols if symbol.kind == "class" and symbol.name == "Product"
    )
    assert product.source_span.path == "src/main/java/com/ibm/catalog/Product.java"
    assert product.source_span.start_line == 15


def test_query_is_repeatable(result: SymbolQueryResult):
    again = query_component_symbols(load_symbol_records(ENTITIES), STEP_ID, COMPONENT)
    assert again == result


def test_unknown_component_returns_an_empty_result():
    empty = query_component_symbols(load_symbol_records(ENTITIES), STEP_ID, "unknown-repo")
    assert empty.symbols == []
    assert empty.total_symbols == 0


def test_json_uses_the_camel_case_contract(result: SymbolQueryResult):
    data = result.model_dump(by_alias=True, mode="json")
    assert set(data) == {"stepId", "component", "symbols", "totalSymbols"}
    assert {"observationId", "qualifiedName", "repoId", "sourceSpan"} <= set(data["symbols"][0])
