"""Typed JSON contracts shared by ingestion, graph queries, and vector indexing."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from shared_contracts.node_types import SOURCE_LOCATED_NODE_TYPES, GraphNodeType
from shared_contracts.relationship_types import RelationshipType
from shared_contracts.source_span import COMMIT_SHA_PATTERN, SourceSpan

SCHEMA_VERSION = "1.0.0"
Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class Extractor(_ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class MigrationMember(_ContractModel):
    """One pinned repository participating in a project milestone."""

    repo_id: str = Field(min_length=1)
    origin: Literal["legacy", "target"]
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    ref: str | None = None
    source_subdirectory: str | None = None


class MigrationStep(_ContractModel):
    """An explicitly ordered migration milestone, independent of commit time."""

    step_id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    members: list[MigrationMember] = Field(min_length=1)


class MigrationManifest(_ContractModel):
    """Project-level input contract from the architecture identity section."""

    project_id: str = Field(min_length=1)
    steps: list[MigrationStep] = Field(min_length=1)

    @model_validator(mode="after")
    def step_ids_and_ordinals_are_unique(self) -> MigrationManifest:
        step_ids = [step.step_id for step in self.steps]
        ordinals = [step.ordinal for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique within a project")
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("step ordinals must be unique within a project")
        return self


class SourceRevision(_ContractModel):
    repo_id: str = Field(min_length=1)
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)


class SnapshotIdentity(_ContractModel):
    """The deterministic analysis ID and the inputs that produced it."""

    source_members: list[SourceRevision] = Field(min_length=1)
    source_snapshot_id: Sha256Digest
    schema_version: Literal[SCHEMA_VERSION]
    extractors: list[Extractor] = Field(min_length=1)
    extractor_set_digest: Sha256Digest
    extraction_config: dict[str, Any]
    extraction_config_digest: Sha256Digest
    snapshot_id: Sha256Digest


class _FactRecord(_ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    record_type: str

    @model_validator(mode="before")
    @classmethod
    def add_envelope_constants(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "schema_version" not in values and "schemaVersion" not in values:
                values["schema_version"] = SCHEMA_VERSION
            if "record_type" not in values and "recordType" not in values:
                record_type_values = get_args(cls.model_fields["record_type"].annotation)
                if not record_type_values:
                    raise ValueError(f"{cls.__name__} must declare a literal record_type")
                values["record_type"] = record_type_values[0]
        return values


class SymbolObservationPayload(_ContractModel):
    observation_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    source_span: SourceSpan
    extractor: Extractor


class SymbolObservationRecord(_FactRecord):
    """Serialized envelope for a source-backed symbol fact."""

    record_type: Literal["SymbolObservation"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    payload: SymbolObservationPayload
    evidence_references: list[str] = Field(min_length=1)


class ExternalSymbolObservationPayload(_ContractModel):
    observation_id: str = Field(min_length=1)
    kind: Literal["external"]
    name: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    extractor: Extractor


class ExternalSymbolObservationRecord(_FactRecord):
    """Serialized envelope for an external graph endpoint."""

    record_type: Literal["ExternalSymbolObservation"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    payload: ExternalSymbolObservationPayload
    evidence_references: list[str]


class RelationshipPayload(_ContractModel):
    relationship_type: RelationshipType
    source_observation_id: str = Field(min_length=1)
    target_observation_id: str = Field(min_length=1)
    evidence_ids: list[str]
    source_span: SourceSpan | None
    extractor: Extractor


class RelationshipRecord(_FactRecord):
    """Serialized envelope for a canonical graph relationship."""

    record_type: Literal["Relationship"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    payload: RelationshipPayload
    evidence_references: list[str]


class RelationshipFact(_FactRecord):
    """Canonical JSONL relationship record consumed by the graph component."""

    record_type: Literal["Relationship"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    relationship_type: RelationshipType
    source_observation_id: str = Field(min_length=1)
    target_observation_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    source_span: SourceSpan | None = None
    extractor_name: str = Field(default="graphify", min_length=1)
    extractor_version: str = Field(default="unknown", min_length=1)

    def to_record_dict(self) -> dict[str, Any]:
        payload = {
            "relationshipType": self.relationship_type.value,
            "sourceObservationId": self.source_observation_id,
            "targetObservationId": self.target_observation_id,
            "evidenceIds": list(self.evidence_ids),
            "sourceSpan": (
                self.source_span.model_dump(by_alias=True, exclude_none=True)
                if self.source_span
                else None
            ),
            "extractor": {"name": self.extractor_name, "version": self.extractor_version},
        }
        record = {
            "schemaVersion": self.schema_version,
            "recordType": self.record_type,
            "recordId": self.record_id,
            "snapshotId": self.snapshot_id,
            "payload": payload,
            "evidenceReferences": (
                [_evidence_locator(self.source_span)] if self.source_span else []
            ),
        }
        RelationshipRecord.model_validate(record)
        return record

    def to_jsonl(self) -> str:
        return json.dumps(self.to_record_dict(), ensure_ascii=False, separators=(",", ":"))


class SymbolObservationFact(_FactRecord):
    """Canonical source-backed symbol record emitted by ingestion."""

    record_type: Literal["SymbolObservation"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    source_span: SourceSpan
    extractor_name: str = Field(default="graphify", min_length=1)
    extractor_version: str = Field(default="unknown", min_length=1)

    def to_record_dict(self) -> dict[str, Any]:
        record = {
            "schemaVersion": self.schema_version,
            "recordType": self.record_type,
            "recordId": self.record_id,
            "snapshotId": self.snapshot_id,
            "payload": {
                "observationId": self.observation_id,
                "kind": self.kind,
                "name": self.name,
                "qualifiedName": self.qualified_name,
                "repoId": self.repo_id,
                "sourceSpan": self.source_span.model_dump(by_alias=True, exclude_none=True),
                "extractor": {"name": self.extractor_name, "version": self.extractor_version},
            },
            "evidenceReferences": [_evidence_locator(self.source_span)],
        }
        SymbolObservationRecord.model_validate(record)
        return record

    def to_jsonl(self) -> str:
        return json.dumps(self.to_record_dict(), ensure_ascii=False, separators=(",", ":"))


class ExternalSymbolObservationFact(_FactRecord):
    """A named external graph endpoint with no source location in this snapshot."""

    record_type: Literal["ExternalSymbolObservation"]
    record_id: Sha256Digest
    snapshot_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    extractor_name: str = Field(default="graphify", min_length=1)
    extractor_version: str = Field(default="unknown", min_length=1)

    def to_record_dict(self) -> dict[str, Any]:
        record = {
            "schemaVersion": self.schema_version,
            "recordType": self.record_type,
            "recordId": self.record_id,
            "snapshotId": self.snapshot_id,
            "payload": {
                "observationId": self.observation_id,
                "kind": "external",
                "name": self.name,
                "qualifiedName": self.qualified_name,
                "extractor": {"name": self.extractor_name, "version": self.extractor_version},
            },
            "evidenceReferences": [],
        }
        ExternalSymbolObservationRecord.model_validate(record)
        return record

    def to_jsonl(self) -> str:
        return json.dumps(self.to_record_dict(), ensure_ascii=False, separators=(",", ":"))


class GraphNode(_ContractModel):
    """Serialized graph node envelope shared by #21 and #23."""

    id: str = Field(min_length=1)
    label: GraphNodeType
    name: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_span_for_source_located_nodes(self) -> GraphNode:
        if self.label in SOURCE_LOCATED_NODE_TYPES:
            raw_span = self.properties.get("sourceSpan", self.properties.get("source_span"))
            if raw_span is None:
                raise ValueError(f"{self.label.value} graph nodes require source_span")
            SourceSpan.model_validate(raw_span)
        return self


class GraphEdge(_ContractModel):
    """Typed edge shape used by graph persistence and query results."""

    id: str = Field(min_length=1)
    relationship_type: RelationshipType
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Serialize an edge using the canonical graph-store field names."""
        return {
            "id": self.id,
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relationshipType": self.relationship_type.value,
            "properties": dict(self.properties),
        }


class SymbolQuerySymbol(_ContractModel):
    """One typed query row retaining the canonical observation's evidence."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    qualified_name: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    source_span: SourceSpan

    @model_validator(mode="after")
    def repository_matches_source_span(self) -> SymbolQuerySymbol:
        if self.repo_id != self.source_span.repo_id:
            raise ValueError("repo_id must match source_span.repo_id")
        return self


class SymbolQueryResult(_ContractModel):
    """Issue #23 query envelope with typed, source-pinned symbol entries."""

    step_id: str = Field(min_length=1)
    component: str = Field(min_length=1)
    symbols: list[SymbolQuerySymbol]
    total_symbols: int = Field(ge=0)

    @model_validator(mode="after")
    def total_matches_symbols(self) -> SymbolQueryResult:
        if self.total_symbols != len(self.symbols):
            raise ValueError("total_symbols must equal the number of symbols")
        return self


class Chunker(_ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class Embedding(_ContractModel):
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)
    dimensions: int = Field(ge=1)
    vector: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def dimensions_match_vector(self) -> Embedding:
        if len(self.vector) != self.dimensions:
            raise ValueError("dimensions must equal the embedding vector length")
        return self


class VectorDocumentPayload(_ContractModel):
    text: str = Field(min_length=1)
    content_hash: Sha256Digest
    source_span: SourceSpan
    language: str | None = None
    symbol_kind: str | None = None
    qualified_name: str | None = None
    chunker: Chunker
    embedding: Embedding | None = None


class VectorDocumentRecord(_FactRecord):
    """Source-grounded chunk to embed or store in a future vector database."""

    record_type: Literal["VectorDocument"]
    record_id: Sha256Digest
    snapshot_id: Sha256Digest
    payload: VectorDocumentPayload
    evidence_references: list[str] = Field(min_length=1)


class SnapshotSelector(_ContractModel):
    """One explicit side of a comparison, scoped to a selected origin."""

    origin: Literal["legacy", "target"]
    snapshot_id: Sha256Digest


class CompareRequest(_ContractModel):
    """Pinned comparison request shape from the architecture's MCP contract."""

    project_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    old: SnapshotSelector
    new: SnapshotSelector
    scope: dict[str, Any]
    accepted_mapping_digest: Sha256Digest | None = None


class ComparisonChange(_ContractModel):
    """One evidence-backed change with optional old/new source locations."""

    change_kind: str = Field(min_length=1)
    old_source_span: SourceSpan | None = None
    new_source_span: SourceSpan | None = None
    symbol_observation_ids: list[str] = Field(default_factory=list)
    diff_evidence: list[str] = Field(default_factory=list)
    relevant_commits: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ComparisonResult(_ContractModel):
    """Ready or pending result for one explicitly selected snapshot pair."""

    comparison_id: Sha256Digest
    contract_version: str = Field(min_length=1)
    comparison_policy_version: str = Field(min_length=1)
    old: SnapshotSelector
    new: SnapshotSelector
    lineage_mode: Literal["ancestor_range", "divergent", "separate_repositories"]
    changes: list[ComparisonChange]
    commit_evidence: list[str] = Field(default_factory=list)
    accepted_mappings: list[str] = Field(default_factory=list)
    coverage: dict[str, Any]
    limitations: list[str] = Field(default_factory=list)
    state: Literal["ready", "queued", "incomplete", "failed"]


def _evidence_locator(span: SourceSpan) -> str:
    return f"git:{span.repo_id}@{span.commit_sha}:{span.path}#L{span.start_line}-L{span.end_line}"
