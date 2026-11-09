"""Whole-graph rule checker for the initial graph schema v1 (issue #21).

`validate_graph` collects ALL problems (it does not stop at the first one) so
a loader can report everything in one go.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from .models import (
    ALLOWED_EDGES,
    CODE_LABELS,
    GraphEdge,
    GraphNodeModel,
    SymbolObservationNode,
    compute_observation_id,
)

# Rule names (stable strings, easy to assert in tests).
DUPLICATE_NODE_ID = "duplicate-node-id"
DUPLICATE_EDGE_ID = "duplicate-edge-id"
MISSING_ENDPOINT = "missing-endpoint"
BAD_ENDPOINT_PAIR = "bad-endpoint-pair"
MISSING_SCOPE = "missing-scope"
MISSING_SNAPSHOT = "code-node-needs-snapshot-id"
SCOPE_MISMATCH = "scope-mismatch"
SCOPE_UNVERIFIABLE = "scope-unverifiable"
BAD_OBSERVATION_ID = "bad-observation-id"


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

    # Node rules: scope and (for symbols) the id formula.
    for node in nodes:
        if not (node.step_id or node.snapshot_id):
            problems.append(SchemaViolation(MISSING_SCOPE, node.id, "needs stepId or snapshotId"))
        if node.label in CODE_LABELS and not node.snapshot_id:
            problems.append(
                SchemaViolation(MISSING_SNAPSHOT, node.id, f"{node.label} needs a snapshotId")
            )
        if isinstance(node, SymbolObservationNode) and node.snapshot_id:
            expected = compute_observation_id(
                node.snapshot_id,
                node.repo_id,
                node.path,
                node.kind,
                node.qualified_name,
            )
            if node.id != expected:
                problems.append(
                    SchemaViolation(
                        BAD_OBSERVATION_ID,
                        node.id,
                        "id must be sha256(snapshotId:repoId:path:kind:qualifiedName); "
                        f"expected {expected}",
                    )
                )

    # Edge rules.
    for edge in edges:
        if not (edge.step_id or edge.snapshot_id):
            problems.append(SchemaViolation(MISSING_SCOPE, edge.id, "needs stepId or snapshotId"))

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

        allowed_source, allowed_target = ALLOWED_EDGES[edge.relationship_type]
        if (source.label, target.label) != (allowed_source, allowed_target):
            problems.append(
                SchemaViolation(
                    BAD_ENDPOINT_PAIR,
                    edge.id,
                    f"{edge.relationship_type} must go {allowed_source} -> "
                    f"{allowed_target}, got {source.label} -> {target.label}",
                )
            )

        problems.extend(_check_scope(edge, source, target))

    return problems


def _check_scope(
    edge: GraphEdge, source: GraphNodeModel, target: GraphNodeModel
) -> list[SchemaViolation]:
    """Both ends (and the edge) must live in the same step / snapshot.

    Compare stepId only where both sides have one, snapshotId likewise. If the
    two ends share NO comparable key (for example a Component with only a
    stepId and a File with only a snapshotId) the link cannot be checked, and
    that is reported instead of silently passing.
    """
    found: list[SchemaViolation] = []

    pairs = [
        ("source node", source),
        ("target node", target),
    ]
    for key in ("step_id", "snapshot_id"):
        edge_value = getattr(edge, key)
        for who, node in pairs:
            node_value = getattr(node, key)
            if edge_value and node_value and edge_value != node_value:
                found.append(
                    SchemaViolation(
                        SCOPE_MISMATCH,
                        edge.id,
                        f"edge {key}={edge_value!r} but {who} {node.id!r} has {node_value!r}",
                    )
                )
        source_value, target_value = getattr(source, key), getattr(target, key)
        if source_value and target_value and source_value != target_value:
            found.append(
                SchemaViolation(
                    SCOPE_MISMATCH,
                    edge.id,
                    f"{key} differs: {source.id!r} has {source_value!r}, "
                    f"{target.id!r} has {target_value!r}",
                )
            )

    comparable = (source.step_id and target.step_id) or (source.snapshot_id and target.snapshot_id)
    if not comparable:
        found.append(
            SchemaViolation(
                SCOPE_UNVERIFIABLE,
                edge.id,
                f"{source.id!r} and {target.id!r} share no stepId or snapshotId, "
                "so the same-scope rule cannot be checked (give code nodes both ids)",
            )
        )
    return found


def assert_valid_graph(nodes: Iterable[GraphNodeModel], edges: Iterable[GraphEdge]) -> None:
    """Raise SchemaValidationError (with all problems) if the graph is invalid."""
    problems = validate_graph(nodes, edges)
    if problems:
        raise SchemaValidationError(problems)


__all__ = [
    "SchemaValidationError",
    "SchemaViolation",
    "assert_valid_graph",
    "validate_graph",
]
