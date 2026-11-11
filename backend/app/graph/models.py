"""Pydantic data models for knowledge graph queries and responses (Issue #23).

Conforms to Architecture Contract §3 ("Canonical graph and fact contract").
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MigrationStatusKind = Literal[
    "active_legacy",
    "in_development",
    "live_target",
    "decommissioned",
]

CouplingKind = Literal[
    "shared_database",
    "messaging_topic",
    "direct_http",
    "shared_schema",
]


class _Model(BaseModel):
    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )


class GraphNode(_Model):
    """A node entity in the knowledge graph."""

    id: str
    label: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(_Model):
    """A directed relationship in the knowledge graph."""

    id: str
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class ComponentMigrationStatus(_Model):
    """Migration status entry for a system component."""

    component: str
    origin: Literal["legacy", "target"]
    status: MigrationStatusKind
    bounded_contexts: list[str] = Field(default_factory=list)
    description: str
    evidence: list[str] = Field(default_factory=list)


class MigrationStatusResult(_Model):
    """Structured response for 'What parts are legacy/target/switched off?'."""

    step_id: str
    components: list[ComponentMigrationStatus]
    total_active_legacy: int
    total_live_target: int
    total_decommissioned: int


class CoupledComponent(_Model):
    """Coupling relationship between two components across migration boundaries."""

    source_component: str
    target_component: str
    coupling_type: CouplingKind
    resource_name: str
    description: str
    evidence: list[str] = Field(default_factory=list)


class CouplingResult(_Model):
    """Structured response for 'What is still coupled to what?'."""

    step_id: str
    couplings: list[CoupledComponent]
    summary: str


class DecommissionCandidate(_Model):
    """Candidate entity or module safe for decommissioning."""

    name: str
    kind: Literal["component", "class", "endpoint", "database_table"]
    parent_component: str
    replacement: str
    reason: str
    risk_level: Literal["low", "medium", "high"]
    evidence: list[str] = Field(default_factory=list)


class DecommissionResult(_Model):
    """Structured response for 'What can reasonably be decommissioned next?'."""

    step_id: str
    candidates: list[DecommissionCandidate]
    summary: str


class SymbolQueryResult(_Model):
    """Query result for structural symbol observations in a component."""

    step_id: str
    component: str
    symbols: list[dict[str, Any]]
    total_symbols: int


class GraphQueryRequest(_Model):
    """Request model for parameterized graph queries."""

    query_type: Literal[
        "migration_status",
        "couplings",
        "decommission_candidates",
        "component_symbols",
    ]
    step_id: str = "step-06"
    component: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
