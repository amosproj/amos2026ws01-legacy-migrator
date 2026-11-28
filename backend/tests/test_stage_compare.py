"""Check the stage comparison on hand-made runs and, when present, real step-05/06 runs.

The real runs live in the git-ignored ``code-ingestion-pipeline/.cache/compare``
folder. CI has no access to the private reference repository, so that test is
skipped when the folder is missing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.stage_compare import (
    REQUIRED_FILES,
    ChangeStatus,
    FileCategory,
    StageComparison,
    StageDataError,
    categorize_file,
    compare_stages,
    load_stage,
    main,
    render_markdown,
)

COMPARE_CACHE = Path(__file__).parents[1] / "code-ingestion-pipeline/.cache/compare"
EXTRACTOR = {"name": "graphify", "version": "test"}


def _sha(text: str, length: int = 64) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:length]


class RunBuilder:
    """Write a minimal but contract-valid run folder for one stage."""

    def __init__(self, root: Path, stage: str, members: dict[str, str]) -> None:
        self.dir = root / stage / "run"
        self.stage = stage
        self.members = {repo_id: _sha(commit, 40) for repo_id, commit in members.items()}
        self.snapshot_id = _sha(f"snapshot-{stage}")
        self.sources: list[dict[str, Any]] = []
        self.entities: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []

    def file(self, repo_id: str, path: str, content: str) -> RunBuilder:
        self.sources.append(
            {
                "repoId": repo_id,
                "origin": "legacy",
                "stage": self.stage,
                "commitSha": self.members[repo_id],
                "publicUrl": f"https://example.invalid/{repo_id}",
                "path": path,
                "language": "java",
                "sizeBytes": len(content),
                "contentSha256": _sha(content),
                "encoding": "utf-8",
                "content": content,
            }
        )
        return self

    def _entity(self, record_type: str, payload: dict[str, Any], evidence: list[str]) -> str:
        observation_id = _sha(f"{self.stage}-{len(self.entities)}-{payload['qualifiedName']}")
        self.entities.append(
            {
                "schemaVersion": "1.0.0",
                "recordType": record_type,
                "recordId": _sha(f"record-{observation_id}"),
                "snapshotId": self.snapshot_id,
                "payload": {"observationId": observation_id, **payload, "extractor": EXTRACTOR},
                "evidenceReferences": evidence,
            }
        )
        return observation_id

    def symbol(self, repo_id: str, path: str, name: str, line: int = 1, kind: str = "class") -> str:
        commit = self.members[repo_id]
        span = {
            "repoId": repo_id,
            "path": path,
            "commitSha": commit,
            "startLine": line,
            "endLine": line,
        }
        payload = {
            "kind": kind,
            "name": name,
            "qualifiedName": f"{path}::{name}",
            "repoId": repo_id,
            "sourceSpan": span,
        }
        evidence = [f"git:{repo_id}@{commit}:{path}#L{line}-L{line}"]
        return self._entity("SymbolObservation", payload, evidence)

    def unresolved(self, repo_id: str, name: str) -> str:
        payload = {
            "kind": "symbol",
            "name": name,
            "qualifiedName": name,
            "repoId": repo_id,
            "sourceStatus": "unresolved",
        }
        return self._entity("UnresolvedSymbolObservation", payload, [])

    def external(self, name: str) -> str:
        payload = {"kind": "external", "name": name, "qualifiedName": name}
        return self._entity("ExternalSymbolObservation", payload, [])

    def relate(self, relationship_type: str, source: str, target: str) -> RunBuilder:
        self.relationships.append(
            {
                "schemaVersion": "1.0.0",
                "recordType": "Relationship",
                "recordId": _sha(f"rel-{self.stage}-{len(self.relationships)}"),
                "snapshotId": self.snapshot_id,
                "payload": {
                    "relationshipType": relationship_type,
                    "sourceObservationId": source,
                    "targetObservationId": target,
                    "evidenceIds": [],
                    "sourceSpan": None,
                    "extractor": EXTRACTOR,
                },
                "evidenceReferences": [f"rel:{self.stage}:{len(self.relationships)}"],
            }
        )
        return self

    def write(self) -> Path:
        self.dir.mkdir(parents=True)
        identity = {
            "sourceMembers": [
                {"repoId": repo_id, "commitSha": commit} for repo_id, commit in self.members.items()
            ],
            "sourceSnapshotId": _sha(f"source-{self.stage}"),
            "schemaVersion": "1.0.0",
            "extractors": [EXTRACTOR],
            "extractorSetDigest": _sha("extractors"),
            "extractionConfig": {},
            "extractionConfigDigest": _sha("config"),
            "snapshotId": self.snapshot_id,
        }
        (self.dir / "snapshot-identity.json").write_text(json.dumps(identity), encoding="utf-8")
        for name, rows in (
            ("sources.jsonl", self.sources),
            ("entities.jsonl", self.entities),
            ("relationships.jsonl", self.relationships),
        ):
            text = "".join(json.dumps(row) + "\n" for row in rows)
            (self.dir / name).write_text(text, encoding="utf-8")
        return self.dir


def _earlier(root: Path) -> Path:
    run = RunBuilder(root, "step-a", {"alpha": "a1", "beta": "b1", "gamma": "c1"})
    run.file("alpha", "Main.java", "class Main {}").file("alpha", "Util.java", "class Util {}")
    run.file("alpha", "Old.java", "class Old {}").file("beta", "B.java", "class B {}")
    run.file("gamma", "G.java", "class G {}")
    main_ = run.symbol("alpha", "Main.java", "Main")
    util = run.symbol("alpha", "Util.java", "Util")
    old = run.symbol("alpha", "Old.java", "Old")
    run.unresolved("alpha", "Override")
    b = run.symbol("beta", "B.java", "B")
    g = run.symbol("gamma", "G.java", "G")
    listing = run.external("java.util.List")
    run.relate("CALLS", main_, util).relate("CALLS", old, util)
    run.relate("IMPORTS", main_, listing).relate("REFERENCES", b, listing)
    run.relate("IMPORTS", g, listing)
    return run.write()


def _later(root: Path) -> Path:
    run = RunBuilder(root, "step-b", {"alpha": "a2", "beta": "b1", "delta": "d1"})
    run.file("alpha", "Main.java", "class Main { int x; }")
    run.file("alpha", "Util.java", "class Util {}")
    run.file("alpha", "New.java", "class New {}").file("beta", "B.java", "class B {}")
    run.file("delta", "D.java", "class D {}")
    main_ = run.symbol("alpha", "Main.java", "Main", line=2)
    util = run.symbol("alpha", "Util.java", "Util")
    new = run.symbol("alpha", "New.java", "New")
    run.unresolved("alpha", "Override")
    run.unresolved("alpha", "Override")  # repeated key with no other stable field
    b = run.symbol("beta", "B.java", "B")
    d = run.symbol("delta", "D.java", "D")
    listing = run.external("java.util.List")
    kafka = run.external("kafka")
    run.relate("CALLS", main_, util).relate("CALLS", main_, util).relate("CALLS", new, util)
    run.relate("IMPORTS", main_, listing).relate("REFERENCES", b, listing)
    run.relate("IMPORTS", d, kafka)
    run.relate("CALLS", main_, _sha("not-an-entity"))
    return run.write()


@pytest.fixture
def comparison(tmp_path: Path) -> StageComparison:
    return compare_stages(_earlier(tmp_path), _later(tmp_path))


def _component(comparison: StageComparison, repo_id: str):
    return next(summary for summary in comparison.components if summary.repo_id == repo_id)


def test_component_status_is_derived_from_members_and_changes(
    comparison: StageComparison,
) -> None:
    assert comparison.state == "ready"
    assert (comparison.earlier.stage, comparison.later.stage) == ("step-a", "step-b")
    statuses = {summary.repo_id: summary.status for summary in comparison.components}
    assert statuses == {
        "alpha": ChangeStatus.MODIFIED,
        "beta": ChangeStatus.UNCHANGED,
        "delta": ChangeStatus.ADDED,
        "gamma": ChangeStatus.REMOVED,
    }
    alpha = _component(comparison, "alpha")
    assert alpha.earlier_commit_sha == _sha("a1", 40)
    assert alpha.later_commit_sha == _sha("a2", 40)
    assert _component(comparison, "delta").earlier_commit_sha is None


def test_files_are_matched_by_repo_and_path(comparison: StageComparison) -> None:
    alpha = _component(comparison, "alpha").files
    assert (alpha.added, alpha.removed, alpha.modified, alpha.unchanged) == (1, 1, 1, 1)
    changes = {(change.repo_id, change.path): change for change in comparison.files}
    assert changes[("alpha", "Main.java")].status is ChangeStatus.MODIFIED
    assert changes[("alpha", "New.java")].status is ChangeStatus.ADDED
    assert changes[("alpha", "Old.java")].status is ChangeStatus.REMOVED
    assert changes[("gamma", "G.java")].status is ChangeStatus.REMOVED
    assert ("alpha", "Util.java") not in changes  # unchanged rows are only counted
    modified = changes[("alpha", "Main.java")]
    assert modified.earlier_evidence == f"git:alpha@{_sha('a1', 40)}:Main.java"
    assert modified.later_evidence == f"git:alpha@{_sha('a2', 40)}:Main.java"


def test_symbols_follow_their_file_and_keep_both_sides_evidence(
    comparison: StageComparison,
) -> None:
    alpha = _component(comparison, "alpha").symbols
    # Main modified, Util and the merged Override unchanged, New added, Old removed
    assert (alpha.added, alpha.removed, alpha.modified, alpha.unchanged) == (1, 1, 1, 2)
    changes = {(change.repo_id, change.qualified_name): change for change in comparison.symbols}
    main_ = changes[("alpha", "Main.java::Main")]
    assert main_.status is ChangeStatus.MODIFIED
    assert main_.earlier_evidence == [f"git:alpha@{_sha('a1', 40)}:Main.java#L1-L1"]
    assert main_.later_evidence == [f"git:alpha@{_sha('a2', 40)}:Main.java#L2-L2"]
    assert changes[("alpha", "New.java::New")].status is ChangeStatus.ADDED
    assert changes[("alpha", "Old.java::Old")].later_observation_ids == []
    assert ("alpha", "Override") not in changes

    external = comparison.unattributed_symbols
    assert (external.added, external.unchanged) == (1, 1)
    assert changes[(None, "kafka")].record_type == "ExternalSymbolObservation"


def test_relationships_are_matched_by_type_and_endpoint_keys(
    comparison: StageComparison,
) -> None:
    changes = {
        (change.relationship_type, change.source.qualified_name, change.target.qualified_name): (
            change.status,
            change.earlier_count,
            change.later_count,
        )
        for change in comparison.relationships
    }
    assert changes == {
        ("CALLS", "Main.java::Main", "Util.java::Util"): (ChangeStatus.ADDED, 1, 2),
        ("CALLS", "New.java::New", "Util.java::Util"): (ChangeStatus.ADDED, 0, 1),
        ("CALLS", "Old.java::Old", "Util.java::Util"): (ChangeStatus.REMOVED, 1, 0),
        ("IMPORTS", "D.java::D", "kafka"): (ChangeStatus.ADDED, 0, 1),
        ("IMPORTS", "G.java::G", "java.util.List"): (ChangeStatus.REMOVED, 1, 0),
    }
    alpha = _component(comparison, "alpha").relationships
    assert (alpha.added, alpha.removed, alpha.unchanged) == (2, 1, 1)
    assert _component(comparison, "beta").relationships.unchanged == 1
    assert (comparison.earlier_unmapped_relationships, comparison.later_unmapped_relationships) == (
        0,
        1,
    )


def test_markdown_report_summarizes_components(comparison: StageComparison) -> None:
    report = render_markdown(comparison)
    assert report.startswith("# Stage comparison: step-a → step-b")
    assert "| delta | added |" in report
    assert "| gamma | removed |" in report
    assert "earlier 0, later 1" in report


def test_identical_runs_are_unchanged(tmp_path: Path) -> None:
    run_dir = _earlier(tmp_path)
    comparison = compare_stages(run_dir, run_dir)
    assert {summary.status for summary in comparison.components} == {ChangeStatus.UNCHANGED}
    assert (comparison.files, comparison.symbols, comparison.relationships) == ([], [], [])


def test_missing_run_folder_is_insufficient_data(tmp_path: Path) -> None:
    comparison = compare_stages(_earlier(tmp_path), tmp_path / "step-b" / "missing")
    assert comparison.state == "insufficient_data"
    assert comparison.components == []
    assert comparison.problems == [f"{tmp_path / 'step-b' / 'missing'}: run folder does not exist"]
    assert "**Insufficient data**" in render_markdown(comparison)


@pytest.mark.parametrize("missing_file", REQUIRED_FILES)
def test_missing_stage_file_is_insufficient_data(tmp_path: Path, missing_file: str) -> None:
    later = _later(tmp_path)
    (later / missing_file).unlink()
    comparison = compare_stages(_earlier(tmp_path), later)
    assert comparison.state == "insufficient_data"
    assert comparison.problems == [f"{later}: missing {missing_file}"]


def test_component_without_sources_is_insufficient_data(tmp_path: Path) -> None:
    run = RunBuilder(tmp_path, "step-a", {"alpha": "a1", "beta": "b1"})
    run.file("alpha", "Main.java", "class Main {}")
    with pytest.raises(StageDataError, match="no files for component beta"):
        load_stage(run.write())


def test_symbol_in_unlisted_file_is_insufficient_data(tmp_path: Path) -> None:
    run = RunBuilder(tmp_path, "step-a", {"alpha": "a1"})
    run.file("alpha", "Main.java", "class Main {}")
    run.symbol("alpha", "Gone.java", "Gone")
    with pytest.raises(StageDataError, match=r"Gone\.java is not in sources\.jsonl"):
        load_stage(run.write())


def test_malformed_jsonl_is_insufficient_data(tmp_path: Path) -> None:
    later = _later(tmp_path)
    with (later / "entities.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    comparison = compare_stages(_earlier(tmp_path), later)
    assert comparison.state == "insufficient_data"
    assert "unreadable data" in comparison.problems[0]


def test_cli_writes_markdown_and_signals_insufficient_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "report.md"
    assert main([str(_earlier(tmp_path)), str(_later(tmp_path)), "--md", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == capsys.readouterr().out
    assert main([str(tmp_path / "nope"), str(tmp_path / "nope")]) == 2


def _moved_runs(root: Path) -> tuple[Path, Path]:
    """``Svc.java`` moves unchanged; ``Edited.java`` moves and gains a method."""
    runs: list[Path] = []
    for stage, folder, edited in (("step-a", "old", "v1"), ("step-b", "new", "v2")):
        run = RunBuilder(root, stage, {"alpha": stage})
        run.file("alpha", f"{folder}/Svc.java", "class Svc { void run() {} }")
        run.file("alpha", f"{folder}/Edited.java", f"class Edited {{}} // {edited}")
        run.file("alpha", "Util.java", "class Util {}")
        svc = run.symbol("alpha", f"{folder}/Svc.java", "Svc")
        method = run.symbol("alpha", f"{folder}/Svc.java", ".run()", line=1, kind="method")
        # the edit shifts the class down one line, so only kind + name can pair it
        edited_class = run.symbol(
            "alpha", f"{folder}/Edited.java", "Edited", line=1 if edited == "v1" else 2
        )
        if edited == "v2":
            run.symbol("alpha", f"{folder}/Edited.java", ".extra()", line=3, kind="method")
        util = run.symbol("alpha", "Util.java", "Util")
        run.relate("DECLARES_MEMBER", svc, method).relate("CALLS", method, util)
        run.relate("CALLS", edited_class, util)
        runs.append(run.write())
    return runs[0], runs[1]


def test_identical_file_with_new_path_is_moved(tmp_path: Path) -> None:
    comparison = compare_stages(*_moved_runs(tmp_path))

    alpha = _component(comparison, "alpha")
    assert alpha.status is ChangeStatus.MODIFIED
    files = {change.path: change for change in comparison.files}
    moved = files["new/Svc.java"]
    assert (moved.status, moved.previous_path) == (ChangeStatus.MOVED, "old/Svc.java")
    assert moved.earlier_evidence == f"git:alpha@{_sha('step-a', 40)}:old/Svc.java"
    assert "old/Svc.java" not in files

    symbols = {change.qualified_name: change for change in comparison.symbols}
    for name in ("Svc", ".run()"):
        change = symbols[f"new/Svc.java::{name}"]
        assert change.status is ChangeStatus.MOVED
        assert change.previous_qualified_name == f"old/Svc.java::{name}"
        assert (change.previous_path, change.path) == ("old/Svc.java", "new/Svc.java")
        assert change.earlier_evidence and change.later_evidence
        assert f"old/Svc.java::{name}" not in symbols

    # Every relationship endpoint was paired, so no relationship changed.
    assert comparison.relationships == []
    assert alpha.relationships.unchanged == 3


def test_edited_file_with_unique_name_is_moved_modified(tmp_path: Path) -> None:
    comparison = compare_stages(*_moved_runs(tmp_path))

    files = {change.path: change for change in comparison.files}
    edited = files["new/Edited.java"]
    assert (edited.status, edited.previous_path) == (
        ChangeStatus.MOVED_MODIFIED,
        "old/Edited.java",
    )
    assert edited.earlier_content_sha256 != edited.later_content_sha256
    assert "old/Edited.java" not in files

    symbols = {change.qualified_name: change for change in comparison.symbols}
    paired = symbols["new/Edited.java::Edited"]
    assert paired.status is ChangeStatus.MOVED_MODIFIED
    assert paired.previous_qualified_name == "old/Edited.java::Edited"
    assert symbols["new/Edited.java::.extra()"].status is ChangeStatus.ADDED
    assert "old/Edited.java::Edited" not in symbols

    alpha = _component(comparison, "alpha")
    assert (alpha.files.moved, alpha.files.moved_modified, alpha.files.unchanged) == (1, 1, 1)
    assert (alpha.symbols.added, alpha.symbols.moved, alpha.symbols.moved_modified) == (1, 2, 1)
    report = render_markdown(comparison)
    assert "moved: `alpha:old/Svc.java` → `new/Svc.java`" in report
    assert "moved_modified: `alpha:old/Edited.java` → `new/Edited.java`" in report


def test_ambiguous_file_name_stays_removed_and_added(tmp_path: Path) -> None:
    runs: list[Path] = []
    for stage, paths in (("step-a", ["a/pom.xml", "b/pom.xml"]), ("step-b", ["c/pom.xml"])):
        run = RunBuilder(tmp_path, stage, {"alpha": stage})
        for path in paths:
            run.file("alpha", path, f"<project>{stage}:{path}</project>")
        runs.append(run.write())

    comparison = compare_stages(*runs)

    files = _component(comparison, "alpha").files
    assert (files.added, files.removed, files.moved, files.moved_modified) == (1, 2, 0, 0)


def test_shared_hash_falls_back_to_file_name_and_stays_moved(tmp_path: Path) -> None:
    runs: list[Path] = []
    for stage, paths in (("step-a", ["a/x.txt", "a/y.txt"]), ("step-b", ["b/x.txt", "b/y.txt"])):
        run = RunBuilder(tmp_path, stage, {"alpha": stage})
        for path in paths:
            run.file("alpha", path, "same content")
        runs.append(run.write())

    comparison = compare_stages(*runs)

    moves = {(change.previous_path, change.path, change.status) for change in comparison.files}
    assert moves == {
        ("a/x.txt", "b/x.txt", ChangeStatus.MOVED),
        ("a/y.txt", "b/y.txt", ChangeStatus.MOVED),
    }


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("Dockerfile", FileCategory.DEPLOYMENT),
        ("docker/Dockerfile.native", FileCategory.DEPLOYMENT),
        ("docker-compose.yml", FileCategory.DEPLOYMENT),
        ("nginx-catalog.conf", FileCategory.DEPLOYMENT),
        ("OCPdeploy/db2-dc.yaml", FileCategory.DEPLOYMENT),
        ("k8s/deploy/service.yml", FileCategory.DEPLOYMENT),
        ("createOrderDB.sql", FileCategory.DB_ACCESS),
        ("src/main/resources/META-INF/persistence.xml", FileCategory.DB_ACCESS),
        ("ejbModule/META-INF/orm.xml", FileCategory.DB_ACCESS),
        ("src/org/example/dao/OrderDao.java", FileCategory.DB_ACCESS),
        ("src/com/example/ProductRepository.java", FileCategory.DB_ACCESS),
        ("liberty/server.xml", FileCategory.CONFIG),
        ("WebContent/WEB-INF/web.xml", FileCategory.CONFIG),
        ("pom.xml", FileCategory.CONFIG),
        ("src/main/resources/application.properties", FileCategory.CONFIG),
        ("resources/jmx_exporter/jmx-config.yml", FileCategory.CONFIG),
        ("src/org/example/Order.java", FileCategory.CODE),
        ("WebContent/index.html", FileCategory.CODE),
        ("dojo_depot/depot/ProductController.js", FileCategory.CODE),
        ("populateDB.sh", FileCategory.CODE),
    ],
)
def test_categorize_file(path: str, category: FileCategory) -> None:
    assert categorize_file(path) is category


def test_changed_files_are_counted_per_category(tmp_path: Path) -> None:
    runs: list[Path] = []
    for stage, extra in (("step-a", []), ("step-b", ["Dockerfile", "schema.sql"])):
        run = RunBuilder(tmp_path, stage, {"alpha": stage})
        run.file("alpha", "pom.xml", f"<project>{stage}</project>")
        run.file("alpha", "Main.java", "class Main {}")
        for path in extra:
            run.file("alpha", path, path)
        runs.append(run.write())

    comparison = compare_stages(*runs)

    by_category = _component(comparison, "alpha").changed_files_by_category
    assert {category: counts.changed for category, counts in by_category.items()} == {
        FileCategory.CONFIG: 1,
        FileCategory.DEPLOYMENT: 1,
        FileCategory.DB_ACCESS: 1,
    }
    assert by_category[FileCategory.CONFIG].modified == 1
    report = render_markdown(comparison)
    assert "## Deployment & DB-access changes" in report
    assert "- added: `alpha:Dockerfile`" in report
    assert "- added: `alpha:schema.sql`" in report


def _single_run(stage: str) -> Path | None:
    runs = sorted(path for path in (COMPARE_CACHE / stage).glob("*") if path.is_dir())
    return runs[-1] if runs else None


def test_real_step_05_to_step_06() -> None:
    earlier, later = _single_run("step-05"), _single_run("step-06")
    if earlier is None or later is None:
        pytest.skip(f"no step-05/step-06 runs under {COMPARE_CACHE}")

    comparison = compare_stages(earlier, later)

    assert comparison.state == "ready", comparison.problems
    statuses = {summary.repo_id: summary.status for summary in comparison.components}
    assert statuses.pop("legacy-example-catalog-service") is ChangeStatus.ADDED
    assert set(statuses) == {
        "legacy-example-db2",
        "legacy-example-frontend-dojo",
        "legacy-example-monolith",
        "legacy-example-proxy",
    }
    assert ChangeStatus.ADDED not in statuses.values()
    assert ChangeStatus.REMOVED not in statuses.values()
