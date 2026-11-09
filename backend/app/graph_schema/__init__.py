"""Initial graph schema v1 (issue #21). See Documentation/graph-schema/initial-graph-schema.md."""

from .models import (
    ALLOWED_EDGES,
    BoundedContextNode,
    ComponentNode,
    FileNode,
    GraphEdge,
    GraphNodeModel,
    SourceSpan,
    SymbolObservationNode,
    compute_observation_id,
)
from .validator import (
    SchemaValidationError,
    SchemaViolation,
    assert_valid_graph,
    validate_graph,
)

__all__ = [
    "ALLOWED_EDGES",
    "BoundedContextNode",
    "ComponentNode",
    "FileNode",
    "GraphEdge",
    "GraphNodeModel",
    "SchemaValidationError",
    "SchemaViolation",
    "SourceSpan",
    "SymbolObservationNode",
    "assert_valid_graph",
    "compute_observation_id",
    "validate_graph",
]
