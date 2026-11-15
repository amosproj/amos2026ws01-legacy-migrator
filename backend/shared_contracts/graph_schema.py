"""Typed graph nodes and endpoint rules from issue #21, using shared contracts.

These models keep the useful typed-node validation from the graph-schema work
while using the single project SourceSpan and RelationshipType models.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from shared_contracts.node_types import GraphNodeType
from shared_contracts.records import GraphEdge as GraphEdge
from shared_contracts.relationship_types import RelationshipType
from shared_contracts.source_span import SourceSpan

__all__ = [
    "ALLOWED_EDGES",
    "CALLS",
    "CLASS",
    "CODE_ENTITY_LABELS",
    "CODE_GRAPH",
    "COMPONENT",
    "COMPONENT_STATE",
    "CONTAINS_TYPE",
    "DECLARES",
    "DECLARES_MEMBER",
    "DERIVED_FROM",
    "EXTENDS",
    "EXTERNAL_SYMBOL",
    "FILE",
    "FUNCTION",
    "HAS_BASELINE",
    "HAS_CODE_GRAPH",
    "HAS_COMPONENT",
    "HAS_FILE",
    "HAS_SNAPSHOT",
    "IMPLEMENTS",
    "IMPORTS",
    "INTERFACE",
    "METHOD",
    "NODE_LABELS",
    "OF_COMPONENT",
    "PROJECT",
    "REFERENCES",
    "SNAPSHOT",
    "SOURCED_FROM",
    "ClassNode",
    "CodeEntityBase",
    "CodeEntityNode",
    "CodeGraphNode",
    "ComponentNode",
    "ComponentStateNode",
    "EdgeType",
    "ExternalSymbolNode",
    "FileNode",
    "FunctionNode",
    "GraphEdge",
    "GraphNodeModel",
    "InterfaceNode",
    "MethodNode",
    "MigrationRole",
    "NodeBase",
    "ProjectNode",
    "SnapshotNode",
    "SourceSpan",
    "compute_entity_id",
    "compute_file_id",
    "normalize_path",
]

# ---------------------------------------------------------------- vocabulary

PROJECT = GraphNodeType.PROJECT.value
SNAPSHOT = GraphNodeType.SNAPSHOT.value
COMPONENT = GraphNodeType.COMPONENT.value
COMPONENT_STATE = GraphNodeType.COMPONENT_STATE.value
CODE_GRAPH = GraphNodeType.CODE_GRAPH.value
FILE = GraphNodeType.FILE.value
CLASS = GraphNodeType.CLASS.value
INTERFACE = GraphNodeType.INTERFACE.value
METHOD = GraphNodeType.METHOD.value
FUNCTION = GraphNodeType.FUNCTION.value
CODE_ENTITY = GraphNodeType.CODE_ENTITY.value
EXTERNAL_SYMBOL = GraphNodeType.EXTERNAL_SYMBOL.value

NODE_LABELS = (
    PROJECT,
    SNAPSHOT,
    COMPONENT,
    COMPONENT_STATE,
    CODE_GRAPH,
    FILE,
    CLASS,
    INTERFACE,
    METHOD,
    FUNCTION,
    CODE_ENTITY,
    EXTERNAL_SYMBOL,
)
# Entities extracted from source code ("any code-entity kind" in Rafael's 2.2).
CODE_ENTITY_LABELS = (CLASS, INTERFACE, METHOD, FUNCTION, CODE_ENTITY)

HAS_SNAPSHOT = RelationshipType.HAS_SNAPSHOT.value
HAS_BASELINE = RelationshipType.HAS_BASELINE.value
HAS_COMPONENT = RelationshipType.HAS_COMPONENT.value
OF_COMPONENT = RelationshipType.OF_COMPONENT.value
HAS_CODE_GRAPH = RelationshipType.HAS_CODE_GRAPH.value
HAS_FILE = RelationshipType.HAS_FILE.value
DECLARES = RelationshipType.DECLARES.value
DECLARES_MEMBER = RelationshipType.DECLARES_MEMBER.value
CONTAINS_TYPE = RelationshipType.CONTAINS_TYPE.value
CALLS = RelationshipType.CALLS.value
EXTENDS = RelationshipType.EXTENDS.value
IMPLEMENTS = RelationshipType.IMPLEMENTS.value
REFERENCES = RelationshipType.REFERENCES.value
IMPORTS = RelationshipType.IMPORTS.value
DERIVED_FROM = RelationshipType.DERIVED_FROM.value
SOURCED_FROM = RelationshipType.SOURCED_FROM.value

EdgeType = RelationshipType

MigrationRole = Literal["legacy", "target", "transition", "unknown"]


def _pairs(sources: tuple[str, ...], targets: tuple[str, ...]) -> frozenset[tuple[str, str]]:
    return frozenset((s, t) for s in sources for t in targets)


_TYPES = (CLASS, INTERFACE)

# edge type -> set of allowed (source label, target label) pairs (Rafael's 2.2).
ALLOWED_EDGES: dict[str, frozenset[tuple[str, str]]] = {
    HAS_SNAPSHOT: _pairs((PROJECT,), (SNAPSHOT,)),
    HAS_BASELINE: _pairs((PROJECT,), (SNAPSHOT,)),
    HAS_COMPONENT: _pairs((SNAPSHOT,), (COMPONENT_STATE,)),
    OF_COMPONENT: _pairs((COMPONENT_STATE,), (COMPONENT,)),
    HAS_CODE_GRAPH: _pairs((COMPONENT_STATE,), (CODE_GRAPH,)),
    HAS_FILE: _pairs((CODE_GRAPH,), (FILE,)),
    DECLARES: _pairs((FILE,), (CLASS, INTERFACE, FUNCTION, CODE_ENTITY)),
    DECLARES_MEMBER: _pairs(_TYPES, (METHOD,)),
    CONTAINS_TYPE: _pairs(_TYPES, _TYPES),
    CALLS: _pairs(
        (FILE, CLASS, METHOD, FUNCTION, CODE_ENTITY),
        (METHOD, FUNCTION, CLASS, CODE_ENTITY, EXTERNAL_SYMBOL),
    ),
    # Only the pair rule is checked, not whether a "Class" is really a class
    # (that is Rafael's open question 5.3).
    EXTENDS: _pairs((CLASS,), (CLASS, EXTERNAL_SYMBOL))
    | _pairs((INTERFACE,), (INTERFACE, EXTERNAL_SYMBOL)),
    IMPLEMENTS: _pairs((CLASS,), (INTERFACE, EXTERNAL_SYMBOL)),
    REFERENCES: _pairs(CODE_ENTITY_LABELS, (*CODE_ENTITY_LABELS, EXTERNAL_SYMBOL)),
    IMPORTS: _pairs((FILE,), (FILE, CLASS, INTERFACE, FUNCTION, CODE_ENTITY, EXTERNAL_SYMBOL)),
    DERIVED_FROM: _pairs((SNAPSHOT,), (SNAPSHOT,)),
    SOURCED_FROM: _pairs(CODE_ENTITY_LABELS, (FILE,)),
}


class _Model(BaseModel):
    """Frozen, camelCase in JSON, unknown fields are errors."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


# ------------------------------------------------------------------- ids
#
# Project, Snapshot, Component, ComponentState and CodeGraph use readable ids
# (they are few and stable), for example "cs:monolith:step-06".
# File and code entities use a sha256 hash, scoped by snapshot + component +
# normalized path (+ kind and qualified name for code entities). Rafael's 2.3 / 2.4.


def normalize_path(path: str) -> str:
    """Forward slashes, no leading or trailing slash."""
    return path.replace("\\", "/").strip("/")


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compute_file_id(snapshot_id: str, component_key: str, path: str) -> str:
    """sha256(snapshotId:componentKey:normalizedPath)."""
    return _sha256(f"{snapshot_id}:{component_key}:{normalize_path(path)}")


def compute_entity_id(
    snapshot_id: str,
    component_key: str,
    path: str,
    kind: str,
    qualified_name: str,
    signature: str | None = None,
) -> str:
    """sha256(snapshotId:componentKey:normalizedPath:kind:qualifiedName[:signature]).

    The signature (e.g. "save(Order,User)") is only used for methods, so that
    overloads get different ids.
    """
    token = f"{snapshot_id}:{component_key}:{normalize_path(path)}:{kind}:{qualified_name}"
    if signature is not None:
        token += f":{signature}"
    return _sha256(token)


# --------------------------------------------------------------------- nodes


class NodeBase(_Model):
    """Fields every node has. `label` is fixed by each subclass."""

    id: str
    label: str

    def to_record(self) -> dict[str, Any]:
        """Flat shape `{id, label, properties}`: one Neo4j label plus a property map."""
        properties = self.model_dump(by_alias=True, exclude={"id", "label"}, exclude_none=True)
        return {"id": self.id, "label": self.label, "properties": properties}


class ProjectNode(NodeBase):
    label: Literal["Project"] = "Project"
    name: str


class SnapshotNode(NodeBase):
    """A selected state of the whole system. Its `id` is its snapshotId (e.g. "step-06").

    Rafael calls the display text `label`; here it is `title`, because `label`
    already means the node type.
    """

    label: Literal["Snapshot"] = "Snapshot"
    title: str
    commit_sha: str | None = None


class ComponentNode(NodeBase):
    """Stable component identity across snapshots, e.g. "monolith"."""

    label: Literal["Component"] = "Component"
    key: str
    repo: str


class ComponentStateNode(NodeBase):
    """The component inside one snapshot."""

    label: Literal["ComponentState"] = "ComponentState"
    snapshot_id: str
    commit_sha: str | None = None
    migration_role: MigrationRole


class CodeGraphNode(NodeBase):
    """Attachment point for the extraction result of one component state."""

    label: Literal["CodeGraph"] = "CodeGraph"
    snapshot_id: str
    run_id: str
    graphify_version: str


class FileNode(NodeBase):
    label: Literal["File"] = "File"
    snapshot_id: str
    component_key: str
    path: str
    content_hash: str | None = None


class CodeEntityBase(NodeBase):
    name: str
    snapshot_id: str
    owner_component_state_id: str
    component_key: str  # used for the id hash
    path: str  # file the entity was found in, used for the id hash
    qualified_name: str
    source_span: SourceSpan
    evidence: list[str] = Field(default_factory=list)


class ClassNode(CodeEntityBase):
    label: Literal["Class"] = "Class"


class InterfaceNode(CodeEntityBase):
    label: Literal["Interface"] = "Interface"


class MethodNode(CodeEntityBase):
    label: Literal["Method"] = "Method"
    # Parameter signature, e.g. "save(Order,User)". Part of the id (overloads).
    signature: str


class FunctionNode(CodeEntityBase):
    label: Literal["Function"] = "Function"


class CodeEntityNode(CodeEntityBase):
    """Fallback when the precise kind is not known."""

    label: Literal["CodeEntity"] = "CodeEntity"
    kind: str


class ExternalSymbolNode(NodeBase):
    """A symbol outside our code. No snapshotId: it may be shared."""

    label: Literal["ExternalSymbol"] = "ExternalSymbol"
    name: str


GraphNodeModel = (
    ProjectNode
    | SnapshotNode
    | ComponentNode
    | ComponentStateNode
    | CodeGraphNode
    | FileNode
    | ClassNode
    | InterfaceNode
    | MethodNode
    | FunctionNode
    | CodeEntityNode
    | ExternalSymbolNode
)


# --------------------------------------------------------------------- edges
