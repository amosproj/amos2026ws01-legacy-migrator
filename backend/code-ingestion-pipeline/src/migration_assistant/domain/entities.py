"""Domain models for code entities and architecture observations (Issue #19).

Follows Section 3.1 ("Retained architecture vocabulary") and Section 3.2
("JSONL and provenance") of Documentation/architecture/architecture-contract.md.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

CodeEntityKind = Literal[
    "class",
    "interface",
    "enum",
    "record",
    "method",
    "constructor",
    "function",
    "table",
]


class _Model(BaseModel):
    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )


class SourceSpan(_Model):
    """Pinpoints the physical location of an entity in source code."""

    repo_id: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None


def compute_observation_id(
    snapshot_id: str,
    repo_id: str,
    path: str,
    kind: str,
    qualified_name: str,
) -> str:
    """Deterministic snapshot-scoped identifier for a code entity.

    Architecture Contract §3.2: Node identity is snapshot-scoped; use kind,
    normalized repository-relative path and qualified signature where known.
    """
    normalized_path = path.replace("\\", "/").strip("/")
    token = f"{snapshot_id}:{repo_id}:{normalized_path}:{kind}:{qualified_name}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SymbolObservation(_Model):
    """A typed code observation (class, method, table) in the knowledge graph."""

    observation_id: str
    snapshot_id: str
    repo_id: str
    path: str
    kind: CodeEntityKind
    name: str
    qualified_name: str
    source_span: SourceSpan
    parent_qualified_name: str | None = None
    signature: str | None = None
    docstring: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_fact_record(self) -> FactRecord:
        """Serialize as a canonical FactRecord for graph ingestion."""
        return FactRecord(
            schema_version="1.0.0",
            record_type="SymbolObservation",
            record_id=self.observation_id,
            snapshot_id=self.snapshot_id,
            payload={
                "observationId": self.observation_id,
                "snapshotId": self.snapshot_id,
                "repoId": self.repo_id,
                "path": self.path,
                "kind": self.kind,
                "name": self.name,
                "qualifiedName": self.qualified_name,
                "parentQualifiedName": self.parent_qualified_name,
                "sourceSpan": self.source_span.model_dump(by_alias=True),
                "signature": self.signature,
                "docstring": self.docstring,
                "modifiers": list(self.modifiers),
                "metadata": dict(self.metadata),
            },
            evidence_references=[
                f"git:{self.source_span.repo_id}@{self.source_span.commit_sha}:{self.source_span.path}#L{self.source_span.start_line}-L{self.source_span.end_line}"
            ],
        )


class FactRecord(_Model):
    """Canonical JSONL record format conforming to Architecture Contract D2."""

    schema_version: str = "1.0.0"
    record_type: Literal["SymbolObservation", "Module", "File"]
    record_id: str
    snapshot_id: str
    payload: dict[str, Any]
    evidence_references: list[str] = Field(default_factory=list)

    def to_jsonl(self) -> str:
        """Format as a single-line canonical JSON string."""
        return self.model_dump_json(by_alias=True)


class ExtractionSummary(_Model):
    """Aggregation counts for a code entity extraction run."""

    total_entities: int
    counts_by_kind: dict[str, int]
    counts_by_language: dict[str, int]
    files_scanned: int


class EntityExtractionResult(_Model):
    """Complete result of extracting entities from one or more source files."""

    snapshot_id: str
    entities: list[SymbolObservation]
    summary: ExtractionSummary

    def to_jsonl_lines(self) -> list[str]:
        """Convert all extracted entities to canonical JSONL lines."""
        return [entity.to_fact_record().to_jsonl() for entity in self.entities]
