"""Pytest coverage for the source fragment lookup (Issue #67)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.source_fragments import (
    FragmentPosition,
    SourceFragmentError,
    extract_fragment,
)
from app.source_loader_adapter import LoaderFragmentFetcher

_SHA = "a" * 40
_OTHER_SHA = "b" * 40


def _load_result(content: str = "line1\nline2\nline3\n") -> dict:
    """A LoadResult shaped like the #17 loader's JSON output (camelCase)."""
    return {
        "checkout": {
            "stage": "step-06",
            "umbrellaRef": "step-06",
            "umbrellaCommitSha": _SHA,
            "workspace": "/tmp/unused-in-tests",
            "members": [
                {
                    "repoId": "catalog-service",
                    "origin": "legacy",
                    "ref": "step-06",
                    "commitSha": _SHA,
                    "localPath": "/tmp/unused-in-tests",
                    "publicUrl": "https://github.com/example/catalog-service",
                }
            ],
        },
        "files": [
            {
                "repoId": "catalog-service",
                "origin": "legacy",
                "stage": "step-06",
                "commitSha": _SHA,
                "publicUrl": "https://github.com/example/catalog-service",
                "path": "src/main/java/com/example/CatalogService.java",
                "language": "java",
                "sizeBytes": len(content),
                "contentSha256": "0" * 64,
                "encoding": "utf-8",
                "content": content,
            }
        ],
        "skipped": [],
        "counts": {"loaded": 1, "skipped": 0},
    }


def _position(**overrides) -> FragmentPosition:
    defaults = {
        "repoId": "catalog-service",
        "stage": "step-06",
        "path": "src/main/java/com/example/CatalogService.java",
        "commitSha": _SHA,
        "startLine": 2,
        "endLine": 3,
    }
    defaults.update(overrides)
    return FragmentPosition(**defaults)


def test_extract_fragment_slices_requested_lines() -> None:
    fragment = extract_fragment(
        _position(), "line1\nline2\nline3\n", "java", "https://github.com/example/catalog-service"
    )

    assert fragment.fragment == "line2\nline3"
    assert fragment.total_lines == 3
    assert fragment.github_url.endswith("#L2-L3")
    assert fragment.position.repo_id == "catalog-service"


def test_extract_fragment_reports_line_range_out_of_bounds() -> None:
    with pytest.raises(SourceFragmentError) as excinfo:
        extract_fragment(_position(startLine=1, endLine=9), "one line\n", "java", "url")

    assert excinfo.value.code == "line_range_out_of_bounds"


def test_loader_fetcher_serves_loaded_file() -> None:
    fetcher = LoaderFragmentFetcher.from_load_result_json(_load_result())

    content, language, public_url, _size = fetcher.fetch(_position())

    assert content == "line1\nline2\nline3\n"
    assert language == "java"
    assert public_url.endswith("catalog-service")


def test_loader_fetcher_rejects_unknown_path() -> None:
    fetcher = LoaderFragmentFetcher.from_load_result_json(_load_result())

    with pytest.raises(SourceFragmentError) as excinfo:
        fetcher.fetch(_position(path="does/not/exist.java"))

    assert excinfo.value.code == "path_not_loaded"


def test_loader_fetcher_rejects_sha_mismatch() -> None:
    fetcher = LoaderFragmentFetcher.from_load_result_json(_load_result())

    with pytest.raises(SourceFragmentError) as excinfo:
        fetcher.fetch(_position(commitSha=_OTHER_SHA))

    assert excinfo.value.code == "commit_sha_mismatch"


def test_api_returns_requested_fragment() -> None:
    with TestClient(app) as client:
        app.state.fragment_fetcher = LoaderFragmentFetcher.from_load_result_json(_load_result())
        try:
            response = client.post(
                "/api/source-fragment",
                json={
                    "repoId": "catalog-service",
                    "stage": "step-06",
                    "path": "src/main/java/com/example/CatalogService.java",
                    "commitSha": _SHA,
                    "startLine": 2,
                    "endLine": 2,
                },
            )
        finally:
            app.state.fragment_fetcher = None

    assert response.status_code == 200
    body = response.json()
    assert body["fragment"] == "line2"
    assert body["githubUrl"].endswith("#L2-L2")


def test_api_reports_structured_error_for_unknown_path() -> None:
    with TestClient(app) as client:
        app.state.fragment_fetcher = LoaderFragmentFetcher.from_load_result_json(_load_result())
        try:
            response = client.post(
                "/api/source-fragment",
                json={
                    "repoId": "catalog-service",
                    "stage": "step-06",
                    "path": "missing.java",
                    "commitSha": _SHA,
                    "startLine": 1,
                    "endLine": 1,
                },
            )
        finally:
            app.state.fragment_fetcher = None

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "path_not_loaded"


def test_api_rejects_inverted_line_range() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/source-fragment",
            json={
                "repoId": "catalog-service",
                "stage": "step-06",
                "path": "x.java",
                "commitSha": _SHA,
                "startLine": 5,
                "endLine": 2,
            },
        )

    assert response.status_code == 422


def test_api_reports_missing_fetcher_structurally() -> None:
    app.state.fragment_fetcher = None
    with TestClient(app) as client:
        response = client.post(
            "/api/source-fragment",
            json={
                "repoId": "catalog-service",
                "stage": "step-06",
                "path": "x.java",
                "commitSha": _SHA,
                "startLine": 1,
                "endLine": 1,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "fetcher_unavailable"
