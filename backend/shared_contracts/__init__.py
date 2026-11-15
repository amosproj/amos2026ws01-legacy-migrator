"""Contracts shared by the ingestion pipeline, graph layer, and backend API."""

from shared_contracts.graph_queries import (
    ComponentMigrationStatus,
    CoupledComponent,
    CouplingResult,
    DecommissionCandidate,
    DecommissionResult,
    GraphQueryRequest,
    MigrationStatusResult,
)
from shared_contracts.graph_schema import CodeEntityNode, GraphNodeModel
from shared_contracts.node_types import GraphNodeType
from shared_contracts.records import (
    CompareRequest,
    ComparisonResult,
    GraphEdge,
    GraphNode,
    MigrationManifest,
    SnapshotIdentity,
    SymbolQueryResult,
    SymbolQuerySymbol,
    VectorDocumentRecord,
)
from shared_contracts.relationship_types import RelationshipType
from shared_contracts.source_span import SourceSpan

__all__ = [
    "CodeEntityNode",
    "CompareRequest",
    "ComparisonResult",
    "ComponentMigrationStatus",
    "CoupledComponent",
    "CouplingResult",
    "DecommissionCandidate",
    "DecommissionResult",
    "GraphEdge",
    "GraphNode",
    "GraphNodeModel",
    "GraphNodeType",
    "GraphQueryRequest",
    "MigrationManifest",
    "MigrationStatusResult",
    "RelationshipType",
    "SnapshotIdentity",
    "SourceSpan",
    "SymbolQueryResult",
    "SymbolQuerySymbol",
    "VectorDocumentRecord",
]
