"""Tests for the source fragment lookup and its offline export."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.source_fragments import FragmentPosition, extract_fragment
from app.source_loader_adapter import LoaderFragmentFetcher
from migration_assistant.adapters.outbound.pipeline_storage import LocalPipelineStorage
from shared_contracts.records import SymbolObservationRecord
from shared_contracts.source_file import SourceFile
from shared_contracts.source_span import SourceSpan

_SHA = "a" * 40
_PREVIOUS_SHA = "b" * 40
_PATH = "src/main/java/com/example/CatalogService.java"
_PUBLIC_URL = "https://github.com/example/catalog-service"


@pytest.fixture
def sources() -> list[SourceFile]:
    content = "line1\nline2\nline3\n"
    current = SourceFile(
        repo_id="catalog-service",
        origin="legacy",
        stage="step-06",
        commit_sha=_SHA,
        public_url=_PUBLIC_URL,
        path=_PATH,
        language="java",
        size_bytes=len(content.encode("utf-8")),
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        encoding="utf-8",
        content=content,
    )
    return [
        current,
        current.model_copy(
            update={"stage": "step-05", "commit_sha": _PREVIOUS_SHA, "content": "previous\n"}
        ),
    ]


@pytest.fixture
def client(
    sources: list[SourceFile], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    export = tmp_path / "sources.jsonl"
    LocalPipelineStorage().write_sources(export, sources)
    monkeypatch.setenv("SOURCE_LOAD_RESULT", str(export))
    with TestClient(app) as client:
        yield client


def _position(**overrides: str | int) -> FragmentPosition:
    span = SourceSpan(
        repo_id="catalog-service", path=_PATH, commit_sha=_SHA, start_line=2, end_line=3
    )
    return FragmentPosition.model_validate({**span.model_dump(), "stage": "step-06", **overrides})


def test_extract_fragment_escapes_path_and_keeps_line_boundaries() -> None:
    position = _position(path="src/A #1.java", start_column=1, end_column=3)
    fragment = extract_fragment(position, "one\n  two\nthree\n", "java", _PUBLIC_URL)

    assert fragment.fragment == "  two\nthree"
    assert fragment.total_lines == 3
    assert fragment.github_url == f"{_PUBLIC_URL}/blob/{_SHA}/src/A%20%231.java#L2-L3"
    assert fragment.position == position


def test_extract_fragment_uses_physical_git_lines() -> None:
    position = _position(start_line=1, end_line=2)
    content = "first\u2028line\r\nsecond\r\n"
    fragment = extract_fragment(position, content, "java", _PUBLIC_URL)

    assert fragment.fragment == "first\u2028line\nsecond"
    assert fragment.total_lines == 2


def test_loader_exposes_stage_revisions_and_rejects_mixed_commits(
    sources: list[SourceFile],
) -> None:
    fetcher = LoaderFragmentFetcher(sources)
    assert fetcher.revisions_for_stage("step-06") == {"catalog-service": _SHA}
    assert fetcher.revisions_for_stage("step-05") == {"catalog-service": _PREVIOUS_SHA}
    assert fetcher.revisions_for_stage("step-01") == {}

    mixed = sources[0].model_copy(update={"path": "Other.java", "commit_sha": _PREVIOUS_SHA})
    with pytest.raises(ValueError, match="multiple revisions for catalog-service in step-06"):
        LoaderFragmentFetcher([*sources, mixed])


def test_api_resolves_shared_span_from_ingestion_export(client: TestClient) -> None:
    position = _position(end_line=2)
    response = client.post("/api/source-fragment", json=position.model_dump(by_alias=True))

    assert response.status_code == 200
    body = response.json()
    assert body["fragment"] == "line2"
    assert body["fragmentSha256"] == hashlib.sha256(b"line2").hexdigest()
    assert body["githubUrl"] == f"{_PUBLIC_URL}/blob/{_SHA}/{_PATH}#L2-L2"
    assert body["position"] == position.model_dump(by_alias=True, exclude_none=True)


@pytest.mark.parametrize(("resource", "line_number"), [("Product", 28), ("Category", 17)])
def test_api_resolves_catalog_demo_route(
    monkeypatch: pytest.MonkeyPatch, resource: str, line_number: int
) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    entities = fixtures / "catalog-service-step-06-entities.jsonl"
    sources = fixtures / "catalog-service-step-06-sources.jsonl"
    monkeypatch.setenv("SOURCE_LOAD_RESULT", str(sources))
    rows = map(json.loads, entities.read_text(encoding="utf-8").splitlines())
    record = next(
        SymbolObservationRecord.model_validate(row)
        for row in rows
        if row["recordType"] == "SymbolObservation"
        and row["payload"]["kind"] == "class"
        and row["payload"]["name"] == f"{resource}Resource"
    )
    span = record.payload.source_span
    position = {"stage": "step-06", **span.model_dump(by_alias=True, exclude_none=True)}
    commit = "474422cf156eb9bcce4267578b089a15edcc3733"
    path = f"src/main/java/com/ibm/catalog/{resource}Resource.java"
    with TestClient(app) as client:
        response = client.post("/api/source-fragment", json=position)
        stale = client.post("/api/source-fragment", json={**position, "commitSha": "0" * 40})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["position"] == position
    assert body["fragment"] == f'@Path("/CustomerOrderServicesWeb/jaxrs/{resource}")'
    assert body["githubUrl"] == (
        "https://github.com/legacy-modernization-example/legacy-example-catalog-service"
        f"/blob/{commit}/{path}#L{line_number}-L{line_number}"
    )
    assert stale.status_code == 404
    assert stale.json()["detail"]["code"] == "commit_sha_mismatch"


def test_api_selects_source_by_stage(client: TestClient) -> None:
    position = _position(stage="step-05", commit_sha=_PREVIOUS_SHA, start_line=1, end_line=1)
    response = client.post("/api/source-fragment", json=position.model_dump(by_alias=True))

    assert response.status_code == 200
    assert response.json()["fragment"] == "previous"
    assert response.json()["githubUrl"] == f"{_PUBLIC_URL}/blob/{_PREVIOUS_SHA}/{_PATH}#L1-L1"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"path": "missing.java"}, "path_not_loaded"),
        ({"repo_id": "unknown-repository"}, "path_not_loaded"),
        ({"stage": "step-04a"}, "path_not_loaded"),
        ({"commit_sha": _PREVIOUS_SHA}, "commit_sha_mismatch"),
        ({"end_line": 4}, "line_range_out_of_bounds"),
    ],
)
def test_api_reports_unresolvable_positions(
    client: TestClient, overrides: dict[str, str | int], code: str
) -> None:
    response = client.post(
        "/api/source-fragment", json=_position(**overrides).model_dump(by_alias=True)
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize("overrides", [{"endLine": 1}, {"path": "../outside.java"}])
def test_api_rejects_invalid_span(client: TestClient, overrides: dict[str, int | str]) -> None:
    payload = {**_position().model_dump(by_alias=True), **overrides}

    assert client.post("/api/source-fragment", json=payload).status_code == 422


def test_api_accepts_legacy_loader_export(
    sources: list[SourceFile], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export = tmp_path / "load-result.json"
    export.write_text(
        json.dumps(
            {"checkout": {"stage": "step-06"}, "files": [sources[0].model_dump(by_alias=True)]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOURCE_LOAD_RESULT", str(export))
    with TestClient(app) as client:
        response = client.post("/api/source-fragment", json=_position().model_dump(by_alias=True))

    assert response.status_code == 200
    assert response.json()["fragment"] == "line2\nline3"


@pytest.mark.parametrize("export_content", [None, "", "invalid JSON\n"])
def test_api_reports_unavailable_export(
    export_content: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SOURCE_LOAD_RESULT", raising=False)
    if export_content is not None:
        export = tmp_path / "sources.jsonl"
        export.write_text(export_content, encoding="utf-8")
        monkeypatch.setenv("SOURCE_LOAD_RESULT", str(export))

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/source-fragment", json=_position().model_dump(by_alias=True))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "fetcher_unavailable"
