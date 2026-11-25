"""Replay saved facts without checking out repositories or extracting graphs."""

import json

import pytest
from neo4j.exceptions import ServiceUnavailable

from migration_assistant import api
from migration_assistant.adapters.outbound.graphify_relationships import write_jsonl_records
from migration_assistant.adapters.outbound.relationship_handoff import read_relationship_handoff
from migration_assistant.bootstrap import cli
from migration_assistant.domain.pipeline import RelationshipHandoffResult
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)
from shared_contracts.snapshot_identity import compute_snapshot_identity
from shared_contracts.source_span import SourceSpan


@pytest.fixture
def saved_handoff(tmp_path):
    identity = compute_snapshot_identity(
        {"repo": "a" * 40}, [{"name": "graphify", "version": "0.9.100"}], {}
    )
    (tmp_path / "snapshot-identity.json").write_text(
        identity.model_dump_json(by_alias=True), encoding="utf-8"
    )
    span = SourceSpan(
        repo_id="repo", path="Service.java", commit_sha="a" * 40, start_line=1, end_line=4
    )
    common = {"snapshot_id": identity.snapshot_id, "extractor_version": "0.9.100"}
    entities = [
        SymbolObservationFact.model_validate(
            common
            | {
                "record_id": "b" * 64,
                "observation_id": "service",
                "kind": "class",
                "name": "Größe",
                "qualified_name": "demo.Service",
                "repo_id": "repo",
                "source_span": span,
            }
        ),
        ExternalSymbolObservationFact.model_validate(
            common
            | {
                "record_id": "c" * 64,
                "observation_id": "external",
                "name": "List",
                "qualified_name": "java.util.List",
            }
        ),
        UnresolvedSymbolObservationFact.model_validate(
            common
            | {
                "record_id": "d" * 64,
                "observation_id": "unknown",
                "kind": "method",
                "name": "unknown",
                "qualified_name": "unknown",
                "source_file": "",
            }
        ),
    ]
    relationships = [
        RelationshipFact.model_validate(
            common
            | {
                "record_id": "e" * 64,
                "relationship_type": "custom`reference",
                "source_observation_id": "service",
                "target_observation_id": "external",
                "source_span": span,
                "evidence_ids": ["evidence"],
                "source_edge_id": "raw-edge",
                "original_relationship_type": "references",
                "original_edge": {"details": {"values": [None, True, "注文"]}},
            }
        )
    ]
    write_jsonl_records(entities, tmp_path / "entities.jsonl")
    write_jsonl_records(relationships, tmp_path / "relationships.jsonl")
    return tmp_path, RelationshipHandoffResult(
        len(entities),
        len(relationships),
        identity.snapshot_id,
        {fact.record_id: fact for fact in entities},
        {fact.record_id: fact for fact in relationships},
    )


def test_reads_all_fact_types_and_preserves_provenance(saved_handoff):
    directory, expected = saved_handoff
    assert read_relationship_handoff(directory) == expected


@pytest.mark.parametrize("with_optional_values", [False, True])
def test_fact_json_round_trips(saved_handoff, with_optional_values):
    _, handoff = saved_handoff
    for fact in [*handoff.all_entities.values(), *handoff.all_relationships.values()]:
        if with_optional_values:
            fact = fact.model_copy(
                update={"extractor_name": "custom-extractor", "extractor_version": "1.2.3"}
            )
            if isinstance(fact, SymbolObservationFact):
                fact = fact.model_copy(
                    update={
                        "source_span": fact.source_span.model_copy(
                            update={"start_column": 0, "end_column": 12}
                        )
                    }
                )
            elif isinstance(fact, UnresolvedSymbolObservationFact):
                fact = fact.model_copy(update={"repo_id": "repo", "source_file": "Missing.java"})
        elif isinstance(fact, RelationshipFact):
            fact = fact.model_copy(
                update={
                    "source_span": None,
                    "source_edge_id": None,
                    "original_relationship_type": None,
                    "original_edge": None,
                    "evidence_ids": [],
                }
            )
        assert type(fact).from_json(fact.to_jsonl()) == fact


def test_cli_persists_saved_handoff(saved_handoff, cli_persistence, persistence_writer, capsys):
    directory, expected = saved_handoff
    assert cli.run_persistence_from_handoff(["--handoff-dir", str(directory)]) == 0
    persistence_writer.persist_handoff.assert_called_once_with(expected)
    assert expected.snapshot_id in capsys.readouterr().out


def test_cli_imports_valid_rows_and_reports_rejected_ones(
    saved_handoff, cli_persistence, persistence_writer, capsys
):
    directory, expected = saved_handoff
    path = directory / "entities.jsonl"
    rows = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(rows[0])
    record["snapshotId"] = "f" * 64
    rows[0] = json.dumps(record)
    rows.extend(["not JSON", rows[1]])
    duplicate_observation = json.loads(rows[1])
    duplicate_observation["recordId"] = "a" * 64
    rows.append(json.dumps(duplicate_observation))
    wrong_commit = json.loads(next(iter(expected.all_entities.values())).to_jsonl())
    wrong_commit["payload"]["sourceSpan"]["commitSha"] = "a" * 39 + "b"
    rows.append(json.dumps(wrong_commit))
    wrong_repo = json.loads(next(iter(expected.all_entities.values())).to_jsonl())
    wrong_repo["payload"]["repoId"] = "different-repo"
    rows.append(json.dumps(wrong_repo))
    path.write_bytes(("\n".join(rows) + "\n").encode("utf-8") + b"\xff\n")

    assert cli.run_persistence_from_handoff(["--handoff-dir", str(directory)]) == 0
    persistence_writer.persist_handoff.assert_called_once()
    (handoff,) = persistence_writer.persist_handoff.call_args.args
    assert set(handoff.all_entities) == set(expected.all_entities) - {record["recordId"]}
    assert handoff.all_relationships == {}
    errors = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [(error["file"], error["line"], error["code"]) for error in errors] == [
        (str(path), 1, "snapshot_mismatch"),
        (str(path), 4, "invalid_record"),
        (str(path), 5, "duplicate_record"),
        (str(path), 6, "duplicate_observation"),
        (str(path), 7, "source_revision_mismatch"),
        (str(path), 8, "source_repo_mismatch"),
        (str(path), 9, "invalid_record"),
        (str(directory / "relationships.jsonl"), 1, "missing_endpoint"),
    ]
    assert all(error["message"] for error in errors)


@pytest.mark.parametrize(
    "corruption",
    [
        "missing-file",
        "invalid-json",
        "invalid-payload",
        "invalid-identity",
        "unknown-type",
        "missing-type",
        "invalid-record",
    ],
)
def test_invalid_handoff_fails_before_connecting(
    saved_handoff, cli_persistence, persistence_writer, capsys, corruption
):
    directory, _ = saved_handoff
    path = directory / "entities.jsonl"
    rows = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(rows[0])
    if corruption == "missing-file":
        path.unlink()
    elif corruption == "invalid-json":
        path.write_text("not json\n", encoding="utf-8")
    elif corruption == "invalid-identity":
        (directory / "snapshot-identity.json").write_text("{}", encoding="utf-8")
    elif corruption == "invalid-record":
        path.write_text("[]\n", encoding="utf-8")
    else:
        if corruption == "invalid-payload":
            del record["payload"]["sourceSpan"]
        elif corruption == "unknown-type":
            record["recordType"] = "CodeGraph"
        elif corruption == "missing-type":
            del record["recordType"]
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert cli.run_persistence_from_handoff(["--handoff-dir", str(directory)]) == 1
    api.GraphDatabase.driver.assert_not_called()
    persistence_writer.persist_handoff.assert_not_called()
    error = capsys.readouterr().err
    assert str(directory) in error
    if corruption in {"missing-file", "invalid-identity"}:
        assert "Cannot read handoff" in error
    else:
        assert "The existing snapshot was kept" in error
        row = json.loads(error.splitlines()[0])
        assert row["file"] == str(path)
        assert row["line"] == 1
        assert row["code"] == "invalid_record"


def test_empty_handoff_keeps_existing_snapshot(saved_handoff, cli_persistence, persistence_writer):
    directory, _ = saved_handoff
    (directory / "entities.jsonl").write_text("", encoding="utf-8")
    assert cli.run_persistence_from_handoff(["--handoff-dir", str(directory)]) == 1
    api.GraphDatabase.driver.assert_not_called()
    persistence_writer.persist_handoff.assert_not_called()


def test_cli_reports_neo4j_failure(saved_handoff, cli_persistence, persistence_writer, capsys):
    directory, _ = saved_handoff
    persistence_writer.persist_handoff.side_effect = ServiceUnavailable("Neo4j unavailable")
    assert cli.run_persistence_from_handoff(["--handoff-dir", str(directory)]) == 1
    assert "Neo4j unavailable" in capsys.readouterr().err


def test_cli_requires_handoff_directory():
    with pytest.raises(SystemExit) as error:
        cli.run_persistence_from_handoff([])
    assert error.value.code == 2
