"""Check the typed lookup against recorded and freshly generated step-06 facts.

The recorded data is the Catalog-only export from PR #125. Set REFERENCE_SOURCE
to also run the checks against a fresh export of all components in the stage.
"""

import json
import os
from pathlib import Path

import pytest
import yaml

from app.symbol_query import load_symbol_records, query_component_symbols
from migration_assistant.bootstrap.cli import main as ingest
from migration_assistant.domain.reference_source import load_config
from shared_contracts.records import SymbolObservationRecord, SymbolQueryResult, SymbolQuerySymbol

FIXTURES = Path(__file__).parent / "fixtures"
INGESTION_CONFIG = (
    Path(__file__).parents[1] / "code-ingestion-pipeline/config/reference-source.yaml"
)

STEP_ID = "step-06"
COMPONENT = "legacy-example-catalog-service"
COMMIT_SHA = "474422cf156eb9bcce4267578b089a15edcc3733"
EXPECTED_SYMBOLS = 30


@pytest.fixture(scope="module", params=["recorded", "fresh"])
def exports(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, Path]:
    if request.param == "recorded":
        return (
            FIXTURES / "catalog-service-step-06-entities.jsonl",
            FIXTURES / "catalog-service-step-06-sources.jsonl",
        )

    source = os.environ.get("REFERENCE_SOURCE")
    if not source:
        pytest.skip("set REFERENCE_SOURCE to the local legacy-example-stages checkout")

    root = tmp_path_factory.mktemp("step-06-ingestion")
    config = load_config(INGESTION_CONFIG).model_dump(mode="json")
    config.update(
        source=str(Path(source).expanduser().resolve()),
        workspace=str(root / "checkout"),
        components=[],
    )
    config_path = root / "reference-source.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    output = root / "runs"
    assert (
        ingest(["--config", str(config_path), "--stage", STEP_ID, "--output-dir", str(output)]) == 0
    )
    (entities,) = output.glob("*/entities.jsonl")
    return entities, entities.with_name("sources.jsonl")


@pytest.fixture(scope="module")
def records(exports: tuple[Path, Path]) -> list[SymbolObservationRecord]:
    entities, _ = exports
    return load_symbol_records(entities)


@pytest.fixture(scope="module")
def result(records: list[SymbolObservationRecord]) -> SymbolQueryResult:
    return query_component_symbols(records, STEP_ID, COMPONENT)


@pytest.fixture(scope="module")
def raw_rows(exports: tuple[Path, Path]) -> list[dict[str, object]]:
    entities, _ = exports
    return [json.loads(line) for line in entities.read_text(encoding="utf-8").splitlines()]


def test_only_source_backed_symbols_are_loaded(
    raw_rows: list[dict[str, object]], records: list[SymbolObservationRecord]
) -> None:
    assert {"ExternalSymbolObservation", "UnresolvedSymbolObservation"} <= {
        row["recordType"] for row in raw_rows
    }
    expected_ids = [row["recordId"] for row in raw_rows if row["recordType"] == "SymbolObservation"]
    assert [record.record_id for record in records] == expected_ids


def test_result_is_typed_and_scoped_to_component(result: SymbolQueryResult) -> None:
    assert result.step_id == STEP_ID
    assert result.component == COMPONENT
    assert result.total_symbols == EXPECTED_SYMBOLS
    assert all(isinstance(symbol, SymbolQuerySymbol) for symbol in result.symbols)
    assert {symbol.repo_id for symbol in result.symbols} == {COMPONENT}


def test_symbols_keep_ingestion_identity_and_metadata(
    raw_rows: list[dict[str, object]], result: SymbolQueryResult
) -> None:
    payloads: dict[str, dict[str, object]] = {}
    for row in raw_rows:
        payload = row["payload"]
        assert isinstance(payload, dict)
        if row["recordType"] == "SymbolObservation" and payload["repoId"] == COMPONENT:
            payloads[payload["observationId"]] = payload
    assert {symbol.observation_id for symbol in result.symbols} == set(payloads)
    for symbol in result.symbols:
        payload = payloads[symbol.observation_id]
        assert symbol.id == symbol.observation_id
        assert symbol.name == payload["name"]
        assert symbol.qualified_name == payload["qualifiedName"]
        assert symbol.kind == payload["kind"]
        span = symbol.source_span.model_dump(by_alias=True, exclude_none=True)
        assert span == payload["sourceSpan"]


def test_every_span_resolves_to_a_line_in_the_loaded_sources(
    exports: tuple[Path, Path], result: SymbolQueryResult
) -> None:
    _, sources = exports
    line_counts = {}
    for line in sources.read_text(encoding="utf-8").splitlines():
        source = json.loads(line)
        key = (source["stage"], source["repoId"], source["commitSha"], source["path"])
        line_counts[key] = len(source["content"].splitlines())

    for symbol in result.symbols:
        span = symbol.source_span
        assert span.repo_id == COMPONENT
        assert span.commit_sha == COMMIT_SHA
        key = (result.step_id, span.repo_id, span.commit_sha, span.path)
        assert key in line_counts, f"{span.path} is missing from sources.jsonl"
        assert 1 <= span.start_line <= span.end_line <= line_counts[key]


@pytest.mark.parametrize(("name", "line"), [("Product", 15), ("ProductCategory", 7)])
def test_known_class_is_returned_with_its_position(
    result: SymbolQueryResult, name: str, line: int
) -> None:
    symbol = next(
        symbol for symbol in result.symbols if symbol.kind == "class" and symbol.name == name
    )
    assert symbol.source_span.path == f"src/main/java/com/ibm/catalog/{name}.java"
    assert symbol.source_span.start_line == line


def test_query_is_independent_of_input_order(
    records: list[SymbolObservationRecord], result: SymbolQueryResult
) -> None:
    assert query_component_symbols(reversed(records), STEP_ID, COMPONENT) == result


def test_unknown_component_returns_an_empty_result(records: list[SymbolObservationRecord]) -> None:
    empty = query_component_symbols(records, STEP_ID, "unknown-repo")
    assert empty.symbols == []
    assert empty.total_symbols == 0


def test_json_uses_the_camel_case_contract(result: SymbolQueryResult) -> None:
    data = result.model_dump(by_alias=True, mode="json")
    assert set(data) == {"stepId", "component", "symbols", "totalSymbols"}
    assert {"observationId", "qualifiedName", "repoId", "sourceSpan"} <= set(data["symbols"][0])
