"""Check Catalog evidence from the recorded export and the persisted chat path."""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.graph_fragments import fragment_positions
from app.llm import MockLlmProvider
from app.source_fragments import SourceFragmentError, resolve_fragment
from app.source_loader_adapter import LoaderFragmentFetcher
from app.symbol_query import load_symbol_records, query_component_symbols
from migration_assistant.api import ingest_step
from migration_assistant.domain.reference_source import load_config
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


@pytest.mark.skipif(
    not (os.environ.get("NEO4J_QUERY_TEST_URI") and os.environ.get("REFERENCE_SOURCE")),
    reason="set NEO4J_QUERY_TEST_URI and REFERENCE_SOURCE for the persisted chat example",
)
def test_chat_uses_the_persisted_catalog_fragments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEO4J_URI", os.environ["NEO4J_QUERY_TEST_URI"])
    config = load_config(
        Path(__file__).parents[1] / "code-ingestion-pipeline/config/reference-source.yaml"
    ).model_copy(
        update={
            "source": str(Path(os.environ["REFERENCE_SOURCE"]).expanduser().resolve()),
            "workspace": tmp_path / "checkout",
            "stage": STEP,
            "components": [],
        }
    )
    run = ingest_step(config, tmp_path / "runs").run_directory
    monkeypatch.setenv("GRAPH_RUN_DIR", str(run))
    provider = MockLlmProvider()
    complete = AsyncMock(
        return_value="The Catalog route declarations are in both resource classes."
    )
    monkeypatch.setattr(provider, "complete", complete)
    monkeypatch.setattr(main, "create_llm_provider", lambda: provider)
    question = "Where are the Product and Category endpoints implemented in the Catalog service?"
    data = {"query": question, "step_id": STEP}

    with TestClient(main.app) as client:
        response = client.post("/api/chat", json=data)
        missing_stage = client.post("/api/chat", json={**data, "step_id": "step-05"})
        no_hits = client.post(
            "/api/chat", json={**data, "query": "Where is the Checkout endpoint in Catalog?"}
        )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == ["sources", "evidence", "content"]
    evidence = json.loads(events[1]["text"])
    assert len(evidence) == 2
    for item in evidence:
        name = Path(item["position"]["path"]).stem
        line = ROUTE_LINES[name]
        assert item["position"]["startLine"] == item["position"]["endLine"] == line
        assert item["githubUrl"].endswith(f"/{name}.java#L{line}-L{line}")
        route = name.removesuffix("Resource")
        assert item["fragment"] == f'@Path("/CustomerOrderServicesWeb/jaxrs/{route}")'
    model_call = complete.await_args
    assert model_call is not None
    assert json.loads(model_call.args[0][-1]["content"]) == {
        "question": question,
        "sources": [
            {
                "filename": Path(item["position"]["path"]).name,
                "position": item["position"],
                "code": item["fragment"],
            }
            for item in evidence
        ],
    }
    for failure, code in ((missing_stage, "stage_not_loaded"), (no_hits, "no_source_hits")):
        events = [json.loads(line) for line in failure.text.splitlines()]
        assert [event["type"] for event in events] == ["sources", "error"]
        assert events[-1]["code"] == code

    stale_run = tmp_path / "stale-run"
    stale_run.mkdir()
    shutil.copyfile(run / "snapshot-identity.json", stale_run / "snapshot-identity.json")
    rows = [json.loads(line) for line in (run / "sources.jsonl").read_text().splitlines()]
    for row in rows:
        if row["repoId"] == REPOSITORY:
            row["commitSha"] = "0" * 40
    (stale_run / "sources.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setenv("GRAPH_RUN_DIR", str(stale_run))
    with TestClient(main.app) as client:
        stale = client.post("/api/chat", json=data)
    events = [json.loads(line) for line in stale.text.splitlines()]
    assert [event["type"] for event in events] == ["sources", "error"]
    assert events[-1]["code"] == "commit_sha_mismatch"
    complete.assert_awaited_once()
