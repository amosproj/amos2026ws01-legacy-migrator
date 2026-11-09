"""Initial graph schema v1 (issue #21): node and edge models.

Base: Documentation/architecture/architecture-contract.md section 3.
Written to stay compatible with PR #84 (code facts) and PR #85 (graph queries)
WITHOUT importing from either of them (neither is merged yet).

The models only check the *shape* of one node or one edge. The rules that need
the whole graph (unique ids, edges point to existing nodes, allowed pairs,
same scope) live in validator.py.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------- vocabulary

COMPONENT = "Component"
BOUNDED_CONTEXT = "BoundedContext"
FILE = "File"
SYMBOL_OBSERVATION = "SymbolObservation"

NODE_LABELS = (COMPONENT, BOUNDED_CONTEXT, FILE, SYMBOL_OBSERVATION)
# Nodes that come from parsing source code. They must carry a snapshotId.
CODE_LABELS = (FILE, SYMBOL_OBSERVATION)

IMPLEMENTS = "IMPLEMENTS"
COUPLED_VIA = "COUPLED_VIA"
CONTAINS = "CONTAINS"
DECLARES = "DECLARES"
CALLS = "CALLS"  # reserved for issue #20, no mock data uses it yet

EdgeType = Literal["IMPLEMENTS", "COUPLED_VIA", "CONTAINS", "DECLARES", "CALLS"]

# edge type -> (allowed source label, allowed target label)
ALLOWED_EDGES: dict[str, tuple[str, str]] = {
    IMPLEMENTS: (COMPONENT, BOUNDED_CONTEXT),
    COUPLED_VIA: (COMPONENT, COMPONENT),
    CONTAINS: (COMPONENT, FILE),
    DECLARES: (FILE, SYMBOL_OBSERVATION),
    CALLS: (SYMBOL_OBSERVATION, SYMBOL_OBSERVATION),
}

# Same values as PR #84 (CodeEntityKind) minus "function", see open question 9.
SymbolKind = Literal["class", "interface", "record", "enum", "method", "constructor", "table"]
# Same values as PR #85.
Origin = Literal["legacy", "target"]
MigrationStatusValue = Literal["active_legacy", "in_development", "live_target", "decommissioned"]
RiskLevel = Literal["low", "medium", "high"]
CouplingType = Literal["shared_database", "messaging_topic", "direct_http", "shared_schema"]


class _Model(BaseModel):
    """Frozen, camelCase in JSON (like #84 and #85), unknown fields are errors."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


# ------------------------------------------------------------------- helpers


def compute_observation_id(
    snapshot_id: str, repo_id: str, path: str, kind: str, qualified_name: str
) -> str:
    """sha256(snapshotId:repoId:path:kind:qualifiedName).

    Same formula as #84 and Architecture Contract section 3.2. The path is
    normalised (forward slashes, no leading/trailing slash).
    """
    normalized_path = path.replace("\\", "/").strip("/")
    token = f"{snapshot_id}:{repo_id}:{normalized_path}:{kind}:{qualified_name}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SourceSpan(_Model):
    """Where a symbol lives in the source (same fields as #84)."""

    repo_id: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int


# --------------------------------------------------------------------- nodes


class NodeBase(_Model):
    """Fields every node has. `label` is fixed by each subclass."""

    id: str
    label: str
    name: str
    # Scope: system nodes use step_id, code nodes use snapshot_id.
    # At least one is needed (validator rule). Code nodes linked to a
    # Component carry both, so the link is explicit.
    step_id: str | None = None
    snapshot_id: str | None = None
    evidence: list[str] = Field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        """Flat shape `{id, label, name, properties}` (like #85 GraphNode).

        This is also the shape a loader needs for Apache AGE: one vertex label
        plus one property map.
        """
        properties = self.model_dump(
            by_alias=True, exclude={"id", "label", "name"}, exclude_none=True
        )
        return {
            "id": self.id,
            "label": self.label,
            "name": self.name,
            "properties": properties,
        }


class ComponentNode(NodeBase):
    """A deployable part of the system at one step (one node per step, as in #85)."""

    label: Literal["Component"] = "Component"
    origin: Origin
    status: MigrationStatusValue
    description: str = ""
    port: int | None = None


class BoundedContextNode(NodeBase):
    label: Literal["BoundedContext"] = "BoundedContext"
    description: str = ""


class FileNode(NodeBase):
    label: Literal["File"] = "File"
    repo_id: str
    path: str


class SymbolObservationNode(NodeBase):
    """Class, method, table ... in ONE label, told apart by `kind` (contract 3.1)."""

    label: Literal["SymbolObservation"] = "SymbolObservation"
    repo_id: str
    path: str
    kind: SymbolKind
    qualified_name: str
    source_span: SourceSpan
    parent_qualified_name: str | None = None
    signature: str | None = None
    docstring: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Decommission info stays on the node for v1 (decision; see doc, open question 3).
    status: MigrationStatusValue | None = None
    replacement: str | None = None
    reason: str | None = None
    risk: RiskLevel | None = None


GraphNodeModel = ComponentNode | BoundedContextNode | FileNode | SymbolObservationNode


# --------------------------------------------------------------------- edges


class GraphEdge(_Model):
    """A directed relationship. Allowed source/target labels: see ALLOWED_EDGES."""

    id: str
    source_id: str
    target_id: str
    relationship_type: EdgeType
    step_id: str | None = None
    snapshot_id: str | None = None
    evidence: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coupled_via_needs_details(self) -> GraphEdge:
        """COUPLED_VIA must say what couples the two components (as in #85)."""
        if self.relationship_type == COUPLED_VIA:
            coupling = self.properties.get("couplingType")
            if coupling not in CouplingType.__args__:
                raise ValueError(
                    "COUPLED_VIA needs properties.couplingType, one of "
                    f"{CouplingType.__args__}; got {coupling!r}"
                )
            if not self.properties.get("resourceName"):
                raise ValueError("COUPLED_VIA needs properties.resourceName")
        return self

    def to_record(self) -> dict[str, Any]:
        """Flat shape like #85 GraphEdge, scope fields go into `properties`."""
        properties = dict(self.properties)
        if self.step_id:
            properties["stepId"] = self.step_id
        if self.snapshot_id:
            properties["snapshotId"] = self.snapshot_id
        if self.evidence:
            properties["evidence"] = list(self.evidence)
        return {
            "id": self.id,
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relationshipType": self.relationship_type,
            "properties": properties,
        }
