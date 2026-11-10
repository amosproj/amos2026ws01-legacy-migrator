"""Acceptance criterion 2: relevant source files are detected and loaded."""

import hashlib

import pytest
from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources

PUBLIC_URL = "https://example.test/org"
LATIN1_SQL = "-- Größe\nSELECT 'ä';\n".encode("latin-1")


@pytest.fixture
def loaded(reference):
    config = reference.config()
    return load_sources(config, LocalGitAdapter().checkout(config))


def _files(loaded):
    return {file.path: file for file in loaded.files}


def _skipped(loaded):
    return {file.path: file.reason for file in loaded.skipped}


def test_expected_files_are_loaded_with_language(loaded):
    languages = {path: file.language for path, file in _files(loaded).items()}

    assert languages == {"legacy.sql": "sql", "pom.xml": "xml", "src/Main.java": "java"}


def test_files_are_sorted_by_path(loaded):
    paths = [file.path for file in loaded.files]

    assert paths == sorted(paths)


def test_images_settings_and_other_types_are_skipped_with_reason(loaded):
    skipped = _skipped(loaded)

    assert skipped["logo.png"] == "excluded"
    assert skipped[".settings/config.xml"] == "excluded"
    assert skipped["notes.txt"] == "not_included"


def test_oversized_and_binary_files_are_skipped(loaded):
    skipped = _skipped(loaded)

    assert skipped["big.xml"] == "too_large"
    assert skipped["zeros.xml"] == "binary"


def test_latin1_file_is_decoded_and_labelled(loaded):
    sql = _files(loaded)["legacy.sql"]

    assert sql.encoding == "latin-1"
    assert "Größe" in sql.content
    assert sql.size_bytes == len(LATIN1_SQL)


def test_utf8_file_is_labelled_utf8(loaded):
    assert _files(loaded)["pom.xml"].encoding == "utf-8"


def test_github_url_uses_public_url_full_sha_and_path(reference, loaded):
    java = _files(loaded)["src/Main.java"]
    sha = reference.origin.sha_step_00

    assert java.github_url == f"{PUBLIC_URL}/legacy-example-monolith/blob/{sha}/src/Main.java"


def test_commit_shas_are_full_length(reference, loaded):
    assert len(loaded.checkout.umbrella_commit_sha) == 40
    for member in loaded.checkout.members:
        assert len(member.commit_sha) == 40
    for file in loaded.files:
        assert len(file.commit_sha) == 40
        assert file.commit_sha == reference.origin.sha_step_00


def test_content_hash_matches_content(loaded):
    pom = _files(loaded)["pom.xml"]

    assert pom.content_sha256 == hashlib.sha256(pom.content.encode("utf-8")).hexdigest()


def test_counts_match_lists(loaded):
    assert loaded.counts.loaded == len(loaded.files) == 3
    assert loaded.counts.skipped == len(loaded.skipped)
    assert loaded.counts.loaded_by_language == {"java": 1, "sql": 1, "xml": 1}
    assert loaded.counts.skipped_by_reason == {
        "binary": 1,
        "excluded": 2,
        "not_included": 1,
        "too_large": 1,
    }


def test_deeply_nested_file_is_loaded(reference):
    from conftest import DEEP_FILE

    config = reference.config(stage="step-04a")
    result = LocalGitAdapter().checkout(config)
    loaded = load_sources(config, result)

    deep = {file.path: file for file in loaded.files}.get(DEEP_FILE)
    deep_skips = [s for s in loaded.skipped if "deeply_nested" in s.path]
    assert deep is not None, f"not loaded; skipped entries: {deep_skips}; counts: {loaded.counts}"
    assert len(deep.path) > 260
    assert deep.language == "java"
    assert deep.content.strip() == "class Deep {}"
    assert not [s for s in loaded.skipped if s.reason == "unreadable"]


def test_unreadable_file_is_skipped_with_os_error(reference, monkeypatch):
    from pathlib import Path

    config = reference.config()
    result = LocalGitAdapter().checkout(config)
    real_read_bytes = Path.read_bytes

    def read_bytes(self):
        if self.name == "pom.xml":
            raise PermissionError(13, "Permission denied")
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    loaded = load_sources(config, result)

    unreadable = [s for s in loaded.skipped if s.reason == "unreadable"]
    assert [s.path for s in unreadable] == ["pom.xml"]
    assert "Permission denied" in unreadable[0].detail
    assert {f.path for f in loaded.files} == {"legacy.sql", "src/Main.java"}


def test_folder_that_cannot_be_entered_is_skipped_with_os_error(reference, monkeypatch):
    import os

    config = reference.config()
    result = LocalGitAdapter().checkout(config)
    real_scandir = os.scandir

    def scandir(path="."):
        if str(path).replace("\\", "/").endswith("/src"):
            raise PermissionError(13, "Permission denied", str(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)

    loaded = load_sources(config, result)

    skipped = [s for s in loaded.skipped if s.reason == "unreadable_dir"]
    assert [s.path for s in skipped] == ["src"]
    assert "Permission denied" in skipped[0].detail
    assert {f.path for f in loaded.files} == {"legacy.sql", "pom.xml"}
