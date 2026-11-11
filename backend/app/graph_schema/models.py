"""Initial graph schema v2 (issue #21): node and edge models.

Base: Rafael's schema from issue #77 (sections 2.1 - 2.4). Target store: Neo4j
(SBOM Vision B). Nothing is imported from PR #84 or PR #85 (not merged).

The models only check the *shape* of one node or one edge. The rules that need
the whole graph (unique ids, endpoints exist, allowed pairs, same snapshot)
live in validator.py.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------- vocabulary

PROJECT = "Project"
SNAPSHOT = "Snapshot"
COMPONENT = "Component"
COMPONENT_STATE = "ComponentState"
CODE_GRAPH = "CodeGraph"
FILE = "File"
CLASS = "Class"
INTERFACE = "Interface"
METHOD = "Method"
FUNCTION = "Function"
CODE_ENTITY = "CodeEntity"
EXTERNAL_SYMBOL = "ExternalSymbol"

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

HAS_SNAPSHOT = "HAS_SNAPSHOT"
HAS_BASELINE = "HAS_BASELINE"
HAS_COMPONENT = "HAS_COMPONENT"
OF_COMPONENT = "OF_COMPONENT"
HAS_CODE_GRAPH = "HAS_CODE_GRAPH"
HAS_FILE = "HAS_FILE"
DECLARES = "DECLARES"
DECLARES_MEMBER = "DECLARES_MEMBER"
CONTAINS_TYPE = "CONTAINS_TYPE"
CALLS = "CALLS"
EXTENDS = "EXTENDS"
IMPLEMENTS = "IMPLEMENTS"
REFERENCES = "REFERENCES"
IMPORTS = "IMPORTS"
DERIVED_FROM = "DERIVED_FROM"
SOURCED_FROM = "SOURCED_FROM"

EdgeType = Literal[
    "HAS_SNAPSHOT",
    "HAS_BASELINE",
    "HAS_COMPONENT",
    "OF_COMPONENT",
    "HAS_CODE_GRAPH",
    "HAS_FILE",
    "DECLARES",
    "DECLARES_MEMBER",
    "CONTAINS_TYPE",
    "CALLS",
    "EXTENDS",
    "IMPLEMENTS",
    "REFERENCES",
    "IMPORTS",
    "DERIVED_FROM",
    "SOURCED_FROM",
]

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


class SourceSpan(_Model):
    """Where a code entity lives in the source.

    Same five fields and camelCase names as the span model of PR #88
    (`RelationshipEvidence`): repoId, commitSha, path, startLine, endLine.
    Stricter than #88: `startLine` must not be greater than `endLine`.
    """

    repo_id: str
    path: str
    commit_sha: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _start_before_end(self) -> SourceSpan:
        if self.start_line > self.end_line:
            raise ValueError(
                f"start_line ({self.start_line}) must not be greater than "
                f"end_line ({self.end_line})"
            )
        return self


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


class GraphEdge(_Model):
    """A directed relationship. Allowed source/target labels: see ALLOWED_EDGES.

    An edge has no snapshot of its own; the validator takes it from its end nodes.
    """

    id: str
    source_id: str
    target_id: str
    relationship_type: EdgeType
    properties: dict[str, Any] = {}

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relationshipType": self.relationship_type,
            "properties": dict(self.properties),
        }
