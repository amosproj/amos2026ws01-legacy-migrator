import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.contracts import SourceSpan as BackendSourceSpan
from app.graph.models import (
    GraphEdge as QueryGraphEdge,
)
from app.graph.models import (
    GraphNode as QueryGraphNode,
)
from app.graph.models import (
    SymbolQueryResult as QuerySymbolQueryResult,
)
from app.graph_schema.models import SourceSpan as GraphSchemaSourceSpan
from migration_assistant.domain import SourceSpan as IngestionSourceSpan
from shared_contracts import RelationshipType, SourceSpan
from shared_contracts.graph_identity import compute_entity_id, compute_file_id
from shared_contracts.node_types import GraphNodeType as CompatibilityGraphNodeType
from shared_contracts.records import (
    SCHEMA_VERSION,
    CompareRequest,
    ComparisonResult,
    GraphEdge,
    GraphNode,
    GraphNodeType,
    MigrationManifest,
    MigrationMember,
    MigrationStep,
    RelationshipFact,
    SnapshotSelector,
    SymbolObservationFact,
    SymbolQueryResult,
    SymbolQuerySymbol,
)
from shared_contracts.records import (
    RelationshipType as RecordRelationshipType,
)
from shared_contracts.relationship_types import (
    RelationshipType as CompatibilityRelationshipType,
)
from shared_contracts.schema import project_contract_schema, validate_project_contract
from shared_contracts.snapshot_identity import canonical_json, compute_snapshot_identity


def test_ingestion_and_backend_export_the_same_source_span_model():
    assert IngestionSourceSpan is BackendSourceSpan is GraphSchemaSourceSpan is SourceSpan
    span = SourceSpan(
        repo_id="catalog-service",
        path="src\\CatalogService.java",
        commit_sha="a" * 40,
        start_line=12,
        end_line=15,
    )

    assert span.path == "src/CatalogService.java"
    assert span.model_dump(by_alias=True, exclude_none=True) == {
        "repoId": "catalog-service",
        "path": "src/CatalogService.java",
        "commitSha": "a" * 40,
        "startLine": 12,
        "endLine": 15,
    }


def test_graph_and_query_layers_reuse_the_shared_node_edge_and_query_models():
    assert QueryGraphNode is GraphNode
    assert QueryGraphEdge is GraphEdge
    assert QuerySymbolQueryResult is SymbolQueryResult
    assert RecordRelationshipType is RelationshipType is CompatibilityRelationshipType
    assert GraphNodeType is CompatibilityGraphNodeType

    span = SourceSpan(
        repo_id="repo",
        path="src/Order.java",
        commit_sha="f" * 40,
        start_line=4,
        end_line=7,
    )
    code_node = SymbolObservationFact(
        record_id="a" * 64,
        snapshot_id="snapshot-1",
        observation_id="observation-1",
        kind="class",
        name="Order",
        qualified_name="app.Order",
        repo_id="repo",
        source_span=span,
    )
    edge = GraphEdge(
        id="edge-1",
        source_id="source-1",
        target_id="target-1",
        relationship_type=RelationshipType.CALLS,
    )

    assert code_node.source_span is span
    assert code_node.to_record_dict()["payload"]["observationId"] == "observation-1"
    assert edge.to_record() == {
        "id": "edge-1",
        "sourceId": "source-1",
        "targetId": "target-1",
        "relationshipType": "CALLS",
        "properties": {},
    }


def test_graph_identity_helpers_keep_repository_and_signature_in_identity():
    assert compute_file_id("snapshot", "legacy", "src\\Order.java") == compute_file_id(
        "snapshot", "legacy", "src/Order.java"
    )
    assert compute_file_id("snapshot", "legacy", "src/Order.java") != compute_file_id(
        "snapshot", "target", "src/Order.java"
    )
    assert compute_entity_id(
        "snapshot", "repo", "src/Order.java", "method", "Order.save", "save(Order)"
    ) != compute_entity_id(
        "snapshot", "repo", "src/Order.java", "method", "Order.save", "save(Customer)"
    )


def test_source_span_rejects_non_relative_paths_and_invalid_ranges():
    with pytest.raises(ValueError, match="repository-relative"):
        SourceSpan(
            repo_id="repo",
            path="../src/File.java",
            commit_sha="a" * 40,
            start_line=1,
            end_line=1,
        )
    with pytest.raises(ValueError, match="end_line"):
        SourceSpan(
            repo_id="repo",
            path="src/File.java",
            commit_sha="a" * 40,
            start_line=4,
            end_line=3,
        )


def test_snapshot_identity_follows_the_four_input_analysis_formula():
    identity = compute_snapshot_identity(
        {"repo-b": "b" * 40, "repo-a": "a" * 40},
        [{"name": "graphify", "version": "0.9.100"}],
        {"graphMode": "combined", "selectedFiles": ["src/A.java"]},
    )
    source_id = sha256(
        canonical_json(
            [
                {"repoId": "repo-a", "commitSha": "a" * 40},
                {"repoId": "repo-b", "commitSha": "b" * 40},
            ]
        )
    ).hexdigest()
    assert identity.source_snapshot_id == source_id
    assert (
        identity.snapshot_id
        == sha256(
            canonical_json(
                {
                    "sourceSnapshotId": identity.source_snapshot_id,
                    "schemaVersion": SCHEMA_VERSION,
                    "extractorSetDigest": identity.extractor_set_digest,
                    "extractionConfigDigest": identity.extraction_config_digest,
                }
            )
        ).hexdigest()
    )
    assert len(identity.snapshot_id) == 64
    assert not identity.snapshot_id.startswith("snapshot:")


def test_snapshot_identity_is_order_independent_and_changes_with_extractors_or_config():
    base = compute_snapshot_identity(
        {"repo": "a" * 40},
        [{"name": "graphify", "version": "0.9.100"}],
        {"graphMode": "combined"},
    )
    reordered = compute_snapshot_identity(
        {"repo": "a" * 40},
        [{"version": "0.9.100", "name": "graphify"}],
        {"graphMode": "combined"},
    )
    changed_extractor = compute_snapshot_identity(
        {"repo": "a" * 40},
        [{"name": "graphify", "version": "0.9.101"}],
        {"graphMode": "combined"},
    )
    changed_config = compute_snapshot_identity(
        {"repo": "a" * 40},
        [{"name": "graphify", "version": "0.9.100"}],
        {"graphMode": "per-component"},
    )

    assert base.snapshot_id == reordered.snapshot_id
    assert base.snapshot_id != changed_extractor.snapshot_id
    assert base.snapshot_id != changed_config.snapshot_id


def test_project_contract_covers_pinned_migration_input_and_comparison_output():
    manifest = MigrationManifest(
        project_id="reference-system",
        steps=[
            MigrationStep(
                step_id="step-03",
                ordinal=3,
                members=[
                    MigrationMember(
                        repo_id="legacy-repo",
                        origin="legacy",
                        commit_sha="a" * 40,
                        ref="refs/tags/step-03",
                    ),
                    MigrationMember(
                        repo_id="target-repo",
                        origin="target",
                        commit_sha="b" * 40,
                    ),
                ],
            )
        ],
    )
    assert manifest.steps[0].members[0].commit_sha == "a" * 40

    with pytest.raises(ValueError, match="step_id values must be unique"):
        MigrationManifest(
            project_id="reference-system",
            steps=[
                MigrationStep(step_id="same", ordinal=1, members=[manifest.steps[0].members[0]]),
                MigrationStep(step_id="same", ordinal=2, members=[manifest.steps[0].members[1]]),
            ],
        )

    selector_old = SnapshotSelector(origin="legacy", snapshot_id="c" * 64)
    selector_new = SnapshotSelector(origin="target", snapshot_id="d" * 64)
    request = CompareRequest(
        project_id="reference-system",
        step_id="step-03",
        old=selector_old,
        new=selector_new,
        scope={"component": "catalog-service"},
    )
    assert request.old.origin == "legacy"

    result = ComparisonResult(
        comparison_id="e" * 64,
        contract_version="1.0.0",
        comparison_policy_version="1.0.0",
        old=selector_old,
        new=selector_new,
        lineage_mode="separate_repositories",
        changes=[],
        coverage={"symbols": "complete"},
        state="ready",
    )
    assert result.state == "ready"


def test_query_result_uses_typed_symbols_and_shared_source_spans():
    span = SourceSpan(
        repo_id="repo",
        path="src/Order.java",
        commit_sha="c" * 40,
        start_line=2,
        end_line=6,
        start_column=0,
        end_column=4,
    )
    result = SymbolQueryResult(
        step_id="step-03",
        component="catalog-service",
        symbols=[
            SymbolQuerySymbol(
                id="symbol-1",
                name="Order",
                observation_id="observation-1",
                kind="class",
                qualified_name="app.Order",
                repo_id="repo",
                source_span=span,
            )
        ],
        total_symbols=1,
    )

    assert result.symbols[0].source_span is span
    assert result.step_id == "step-03"
    assert result.total_symbols == 1
    assert result.model_dump(by_alias=True)["symbols"][0]["sourceSpan"]["startColumn"] == 0
    assert RelationshipType.STATUS_OF in RelationshipType
    assert RelationshipType.SOURCED_FROM in RelationshipType

    with pytest.raises(ValueError, match="total_symbols"):
        SymbolQueryResult(
            step_id="step-03",
            component="catalog-service",
            symbols=[],
            total_symbols=1,
        )


def test_serialized_ingestion_facts_keep_the_shared_source_span_contract():
    span = SourceSpan(
        repo_id="repo",
        path="src/Order.java",
        commit_sha="d" * 40,
        start_line=5,
        end_line=9,
    )
    entity_record = SymbolObservationFact(
        record_id="a" * 64,
        snapshot_id="b" * 64,
        observation_id="observation-1",
        kind="class",
        name="Order",
        qualified_name="app.Order",
        repo_id="repo",
        source_span=span,
    ).to_record_dict()
    relationship_record = RelationshipFact(
        record_id="c" * 64,
        snapshot_id="b" * 64,
        relationship_type=RelationshipType.CALLS,
        source_observation_id="observation-1",
        target_observation_id="observation-2",
        evidence_ids=["evidence-1"],
        source_span=span,
    ).to_record_dict()

    assert entity_record["schemaVersion"] == relationship_record["schemaVersion"]
    assert entity_record["recordType"] == "SymbolObservation"
    assert relationship_record["recordType"] == "Relationship"
    assert entity_record["snapshotId"] == relationship_record["snapshotId"] == "b" * 64
    assert entity_record["payload"]["sourceSpan"] == relationship_record["payload"]["sourceSpan"]
    assert validate_project_contract(entity_record).payload.source_span is not None
    assert validate_project_contract(relationship_record).payload.source_span is not None


def test_source_located_graph_nodes_require_source_span():
    with pytest.raises(ValueError, match="require source_span"):
        GraphNode(id="method-1", label=GraphNodeType.METHOD, properties={})
    GraphNode(id="project-1", label=GraphNodeType.PROJECT, properties={})
    GraphNode(
        id="method-1",
        label=GraphNodeType.METHOD,
        properties={
            "sourceSpan": {
                "repoId": "repo",
                "path": "src/Order.java",
                "commitSha": "c" * 40,
                "startLine": 2,
                "endLine": 6,
            }
        },
    )


def test_checked_in_project_schema_is_generated_from_the_shared_models():
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "project-contract.schema.json"
    assert json.loads(schema_path.read_text(encoding="utf-8")) == project_contract_schema()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "SourceSpan" in schema["$defs"]
    assert "SnapshotIdentity" in schema["$defs"]
    assert "MigrationManifest" in schema["$defs"]
    assert "MigrationStep" in schema["$defs"]
    assert "MigrationMember" in schema["$defs"]
    assert "CompareRequest" in schema["$defs"]
    assert "ComparisonResult" in schema["$defs"]
    assert "GraphNode" in schema["$defs"]
    assert "GraphNodeType" in schema["$defs"]
    assert "SymbolQueryResult" in schema["$defs"]
    assert "VectorDocumentRecord" in schema["$defs"]
    assert "GraphQueryRequest" in schema["$defs"]
    assert "MigrationStatusResult" in schema["$defs"]
    assert "sourceSpan" in schema["$defs"]["SymbolQuerySymbol"]["required"]
    source_node_rule = schema["$defs"]["GraphNode"]["allOf"][0]
    assert "sourceSpan" in source_node_rule["then"]["properties"]["properties"]["required"]
    assert {
        "Class",
        "Interface",
        "Method",
        "Function",
        "CodeEntity",
        "SymbolObservation",
    } <= set(source_node_rule["if"]["properties"]["label"]["enum"])
    assert set(schema["$defs"]["RelationshipType"]["enum"]) == {
        relationship.value for relationship in RelationshipType
    }
    assert {
        "HAS_SNAPSHOT",
        "HAS_FILE",
        "DECLARES_MEMBER",
        "CONTAINS_TYPE",
        "CALLS",
        "SAME_ENTITY_AS",
        "RECORDED_BY",
        "CHANGED",
        "HOSTS",
        "HAS_CHUNK",
        "STATUS_OF",
    } <= {relationship.value for relationship in RelationshipType}
    assert {
        "Project",
        "Snapshot",
        "Component",
        "CodeGraph",
        "Class",
        "Method",
        "Module",
        "SymbolObservation",
        "Commit",
        "DeploymentNode",
        "MessagingRoute",
        "ConfluencePage",
        "DocChunk",
        "MigrationStatus",
        "ExtractionRun",
    } <= set(schema["$defs"]["GraphNodeType"]["enum"])
