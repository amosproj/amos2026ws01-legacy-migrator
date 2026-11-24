"""Backend callers use Python values and exceptions rather than CLI arguments."""

from unittest.mock import MagicMock, Mock

import pytest
from neo4j import Driver
from neo4j.exceptions import ServiceUnavailable

from migration_assistant import api
from migration_assistant.adapters.outbound.neo4j import Neo4jPersistenceWriter
from migration_assistant.domain.pipeline import (
    PipelineError,
    PipelineResult,
    RelationshipHandoffResult,
)
from shared_contracts.records import ExternalSymbolObservationFact, RelationshipFact


@pytest.fixture
def api_database(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    driver = MagicMock(spec_set=Driver)
    driver.__enter__.return_value = driver
    driver.__exit__.return_value = False
    factory = Mock(return_value=driver)
    writer = Mock(spec_set=Neo4jPersistenceWriter)
    monkeypatch.setattr(api.GraphDatabase, "driver", factory)
    monkeypatch.setattr(api, "Neo4jPersistenceWriter", Mock(return_value=writer))
    return factory, driver, writer


@pytest.fixture
def populated_handoff():
    entity = ExternalSymbolObservationFact(
        record_type="ExternalSymbolObservation",
        record_id="a" * 64,
        snapshot_id="snapshot",
        observation_id="symbol",
        name="List",
        qualified_name="java.util.List",
    )
    return RelationshipHandoffResult(1, 0, "snapshot", {entity.record_id: entity}, {})


def test_ingest_step_forwards_inputs_and_returns_run_result(
    reference, tmp_path, api_database, monkeypatch
):
    _, driver, writer = api_database
    service = Mock()
    expected = Mock(spec_set=PipelineResult)
    service.run.return_value = expected
    monkeypatch.setattr(api, "PipelineService", Mock(return_value=service))
    config = reference.config()
    output = tmp_path / "runs"
    source_export = tmp_path / "sources.jsonl"
    on_loaded, progress = Mock(), Mock()

    result = api.ingest_step(
        config, output, source_export=source_export, on_loaded=on_loaded, progress=progress
    )

    assert result is expected
    assert api.PipelineService.call_args.kwargs["persistence_writer"] is writer
    service.run.assert_called_once_with(
        config, output, source_export=source_export, on_loaded=on_loaded, progress=progress
    )
    driver.verify_connectivity.assert_called_once()
    driver.__exit__.assert_called_once_with(None, None, None)


def test_persist_handoff_reads_before_connecting_and_returns_facts(
    tmp_path, api_database, monkeypatch, populated_handoff
):
    factory, driver, writer = api_database

    def read(directory):
        assert directory == tmp_path
        factory.assert_not_called()
        return populated_handoff

    monkeypatch.setattr(api, "read_relationship_handoff", read)

    assert api.persist_handoff(tmp_path) is populated_handoff
    writer.persist_handoff.assert_called_once_with(populated_handoff)
    driver.__exit__.assert_called_once_with(None, None, None)


@pytest.mark.parametrize("populated", [False, True])
def test_load_snapshot_returns_both_fact_dictionaries(api_database, populated):
    factory, driver, writer = api_database
    entities, relationships = {}, {}
    if populated:
        entity = ExternalSymbolObservationFact.model_validate(
            {
                "record_id": "a" * 64,
                "snapshot_id": "snapshot",
                "observation_id": "symbol",
                "name": "List",
                "qualified_name": "java.util.List",
            }
        )
        relationship = RelationshipFact.model_validate(
            {
                "record_id": "b" * 64,
                "snapshot_id": "snapshot",
                "relationship_type": "REFERENCES",
                "source_observation_id": "symbol",
                "target_observation_id": "symbol",
            }
        )
        entities[entity.record_id] = entity
        relationships[relationship.record_id] = relationship
    writer.load_entities.return_value = entities
    writer.load_relationships.return_value = relationships

    result = api.load_snapshot("snapshot")

    assert result.snapshot_id == "snapshot"
    assert result.all_entities is entities
    assert result.all_relationships is relationships
    assert result.entity_count == len(entities)
    assert result.relationship_count == len(relationships)
    writer.load_entities.assert_called_once_with("snapshot")
    writer.load_relationships.assert_called_once_with("snapshot")
    factory.assert_called_once_with("bolt://localhost:7687", auth=("neo4j", "change-this"))
    driver.verify_connectivity.assert_called_once()
    driver.__exit__.assert_called_once_with(None, None, None)


def test_connection_settings_are_read_per_operation(api_database, monkeypatch):
    factory, driver, writer = api_database
    writer.load_entities.return_value = {}
    writer.load_relationships.return_value = {}
    api.load_snapshot("first")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:17687")
    api.load_snapshot("second")

    assert factory.call_count == 2
    factory.assert_called_with("bolt://localhost:17687", auth=("neo4j", "change-this"))
    assert driver.__exit__.call_count == 2


@pytest.mark.parametrize("operation", ["ingest", "persist", "load"])
def test_operation_errors_propagate_and_close_connection(
    reference, tmp_path, api_database, monkeypatch, operation, populated_handoff
):
    _, driver, writer = api_database
    error = ServiceUnavailable("database unavailable")
    service = Mock()
    service.run.side_effect = error
    monkeypatch.setattr(api, "PipelineService", Mock(return_value=service))
    monkeypatch.setattr(
        api,
        "read_relationship_handoff",
        Mock(return_value=populated_handoff),
    )
    writer.persist_handoff.side_effect = error
    writer.load_entities.side_effect = error

    with pytest.raises(ServiceUnavailable) as raised:
        if operation == "ingest":
            api.ingest_step(reference.config(), tmp_path)
        elif operation == "persist":
            api.persist_handoff(tmp_path)
        else:
            api.load_snapshot("snapshot")

    assert raised.value is error
    driver.__exit__.assert_called_once()
    assert driver.__exit__.call_args.args[:2] == (ServiceUnavailable, error)


def test_connectivity_error_closes_connection(api_database):
    _, driver, _ = api_database
    driver.verify_connectivity.side_effect = ServiceUnavailable("cannot connect")

    with pytest.raises(ServiceUnavailable, match="cannot connect"):
        api.load_snapshot("snapshot")

    api.Neo4jPersistenceWriter.assert_not_called()
    driver.__exit__.assert_called_once()


def test_unreadable_handoff_propagates_without_connecting(tmp_path, api_database):
    factory, _, _ = api_database
    with pytest.raises(PipelineError, match="Cannot read handoff"):
        api.persist_handoff(tmp_path / "missing")
    factory.assert_not_called()
