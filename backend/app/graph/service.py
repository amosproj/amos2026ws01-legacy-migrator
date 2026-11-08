"""Graph query service application layer (Issue #23).

Coordinates graph queries, formats knowledge context for LLM prompt augmentation,
and manages the underlying graph storage engine.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from .models import (
    CouplingResult,
    DecommissionResult,
    GraphQueryRequest,
    MigrationStatusResult,
    SymbolQueryResult,
)
from .queries import (
    execute_graph_query,
    get_component_symbols,
    get_coupled_components,
    get_decommission_candidates,
    get_migration_status,
)
from .store import GraphStoreProtocol, InMemoryGraphStore

logger = logging.getLogger(__name__)


class GraphQueryService:
    """High-level service interface for executing migration knowledge graph queries."""

    def __init__(self, store: GraphStoreProtocol | None = None) -> None:
        self._store: GraphStoreProtocol = store or InMemoryGraphStore(seed_baseline=True)

    @property
    def store(self) -> GraphStoreProtocol:
        return self._store

    def query_status(
        self,
        step_id: str = "step-06",
        component: str | None = None,
    ) -> MigrationStatusResult:
        """Query migration status of components."""
        return get_migration_status(self._store, step_id=step_id, component=component)

    def query_couplings(self, step_id: str = "step-06") -> CouplingResult:
        """Query cross-boundary coupling between components."""
        return get_coupled_components(self._store, step_id=step_id)

    def query_decommission_candidates(self, step_id: str = "step-06") -> DecommissionResult:
        """Query decommission candidates (dead code / replaced endpoints)."""
        return get_decommission_candidates(self._store, step_id=step_id)

    def query_symbols(
        self,
        step_id: str = "step-06",
        component: str = "monolith",
        kind: str | None = None,
    ) -> SymbolQueryResult:
        """Query symbol inventory for a given component."""
        return get_component_symbols(
            self._store, step_id=step_id, component=component, kind=kind
        )

    def execute_query(
        self,
        request: GraphQueryRequest,
    ) -> MigrationStatusResult | CouplingResult | DecommissionResult | SymbolQueryResult:
        """Dispatch a parameterized graph query request."""
        return execute_graph_query(self._store, request)

    def format_context_for_prompt(self, step_id: str = "step-06") -> str:
        """Format authoritative knowledge graph facts for LLM prompt enrichment.

        Allows SunsetTracker's chat assistant to answer questions with verified
        architecture evidence grounded in the knowledge graph.
        """
        status = self.query_status(step_id=step_id)
        couplings = self.query_couplings(step_id=step_id)
        decomms = self.query_decommission_candidates(step_id=step_id)

        lines: list[str] = [
            f"### Verified Knowledge Graph Facts for Migration Step: {step_id}",
            "Components:",
        ]

        for comp in status.components:
            bc_info = f" (Context: {', '.join(comp.bounded_contexts)})" if comp.bounded_contexts else ""
            lines.append(f"- {comp.component} [{comp.status}, {comp.origin}]{bc_info}: {comp.description}")

        if couplings.couplings:
            lines.append("\nCross-Boundary Couplings:")
            for c in couplings.couplings:
                lines.append(f"- {c.source_component} <-> {c.target_component} [{c.coupling_type}] via '{c.resource_name}': {c.description}")

        if decomms.candidates:
            lines.append("\nDecommission Candidates (Dead Code / Replaced Endpoints):")
            for d in decomms.candidates:
                lines.append(f"- {d.name} in {d.parent_component} (risk: {d.risk_level}): {d.reason} (superseded by {d.replacement})")

        return "\n".join(lines)


def create_graph_service(store: GraphStoreProtocol | None = None) -> GraphQueryService:
    """Factory creating a configured GraphQueryService instance."""
    return GraphQueryService(store=store)
