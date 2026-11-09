"""Whole-graph rule checker for the initial graph schema v2 (issue #21).

`validate_graph` collects ALL problems (it does not stop at the first one) so
a loader can report everything in one go.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from .models import (
    ALLOWED_EDGES,
    DERIVED_FROM,
    CodeEntityBase,
    CodeEntityNode,
    FileNode,
    GraphEdge,
    GraphNodeModel,
    SnapshotNode,
    compute_entity_id,
    compute_file_id,
)

# Rule names (stable strings, easy to assert in tests).
DUPLICATE_NODE_ID = "duplicate-node-id"
DUPLICATE_EDGE_ID = "duplicate-edge-id"
MISSING_ENDPOINT = "missing-endpoint"
BAD_ENDPOINT_PAIR = "bad-endpoint-pair"
CROSS_SNAPSHOT_EDGE = "cross-snapshot-edge"
BAD_NODE_ID = "bad-node-id"


@dataclass(frozen=True)
class SchemaViolation:
    rule: str
    item_id: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.item_id}: {self.message}"


class SchemaValidationError(ValueError):
    """Raised by assert_valid_graph. `.violations` has every problem found."""

    def __init__(self, violations: list[SchemaViolation]) -> None:
        self.violations = violations
        super().__init__(
            f"{len(violations)} schema violation(s):\n" + "\n".join(f"  - {v}" for v in violations)
        )


def snapshot_of(node: GraphNodeModel) -> str | None:
    """The snapshot a node belongs to. A Snapshot is its own snapshot.

    Project, Component and ExternalSymbol belong to no snapshot (None).
    """
    if isinstance(node, SnapshotNode):
        return node.id
    return getattr(node, "snapshot_id", None)


def _expected_id(node: GraphNodeModel) -> str | None:
    """Hash id that File and code entities must have. None = readable id, not checked."""
    if isinstance(node, FileNode):
        return compute_file_id(node.snapshot_id, node.component_key, node.path)
    if isinstance(node, CodeEntityBase):
        kind = node.kind if isinstance(node, CodeEntityNode) else node.label
        return compute_entity_id(
            node.snapshot_id, node.component_key, node.path, kind, node.qualified_name
        )
    return None


def validate_graph(
    nodes: Iterable[GraphNodeModel], edges: Iterable[GraphEdge]
) -> list[SchemaViolation]:
    """Return all rule violations (empty list = graph is valid)."""
    nodes = list(nodes)
    edges = list(edges)
    problems: list[SchemaViolation] = []

    # Rule 1: unique node ids and unique edge ids.
    for node_id, count in Counter(n.id for n in nodes).items():
        if count > 1:
            problems.append(SchemaViolation(DUPLICATE_NODE_ID, node_id, f"used by {count} nodes"))
    for edge_id, count in Counter(e.id for e in edges).items():
        if count > 1:
            problems.append(SchemaViolation(DUPLICATE_EDGE_ID, edge_id, f"used by {count} edges"))

    by_id: dict[str, GraphNodeModel] = {}
    for node in nodes:
        by_id.setdefault(node.id, node)  # first one wins; duplicates already reported

    # Rule 5: File and code entity ids are the hash of snapshot + component + path (+ name).
    for node in nodes:
        expected = _expected_id(node)
        if expected is not None and node.id != expected:
            problems.append(
                SchemaViolation(
                    BAD_NODE_ID,
                    node.id,
                    f"{node.label} id must be the sha256 id formula; expected {expected}",
                )
            )

    for edge in edges:
        # Rule 2: both ends exist.
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None:
            problems.append(
                SchemaViolation(
                    MISSING_ENDPOINT, edge.id, f"sourceId {edge.source_id!r} does not exist"
                )
            )
        if target is None:
            problems.append(
                SchemaViolation(
                    MISSING_ENDPOINT, edge.id, f"targetId {edge.target_id!r} does not exist"
                )
            )
        if source is None or target is None:
            continue  # the other checks need both ends

        # Rule 3: the (source label, target label) pair must be allowed for this edge type.
        allowed = ALLOWED_EDGES[edge.relationship_type]
        if (source.label, target.label) not in allowed:
            wanted = ", ".join(f"{s} -> {t}" for s, t in sorted(allowed))
            problems.append(
                SchemaViolation(
                    BAD_ENDPOINT_PAIR,
                    edge.id,
                    f"{edge.relationship_type} allows {wanted}; "
                    f"got {source.label} -> {target.label}",
                )
            )

        # Rule 4: same snapshot. DERIVED_FROM is the only edge that may cross snapshots.
        # A node without a snapshot (Project, Component, ExternalSymbol) is skipped.
        if edge.relationship_type == DERIVED_FROM:
            continue
        source_snapshot, target_snapshot = snapshot_of(source), snapshot_of(target)
        if source_snapshot and target_snapshot and source_snapshot != target_snapshot:
            problems.append(
                SchemaViolation(
                    CROSS_SNAPSHOT_EDGE,
                    edge.id,
                    f"{edge.relationship_type} connects snapshot {source_snapshot!r} "
                    f"with snapshot {target_snapshot!r}",
                )
            )

    return problems


def assert_valid_graph(nodes: Iterable[GraphNodeModel], edges: Iterable[GraphEdge]) -> None:
    """Raise SchemaValidationError (with all problems) if the graph is invalid."""
    problems = validate_graph(nodes, edges)
    if problems:
        raise SchemaValidationError(problems)


__all__ = [
    "SchemaValidationError",
    "SchemaViolation",
    "assert_valid_graph",
    "snapshot_of",
    "validate_graph",
]
