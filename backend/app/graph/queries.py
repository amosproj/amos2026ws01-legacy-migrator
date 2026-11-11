"""Predefined queries against the migration knowledge graph (Issue #23).

Fulfills acceptance criteria:
- Predefined queries for the vertical slice:
    * migration status (active legacy vs target vs decommissioned)
    * cross-boundary couplings (messaging topic, shared database/schema)
    * decommission candidates (dead code / replaced endpoints)
    * component symbol inventory
- Decoupled from graph database backend via GraphStoreProtocol
- Returns strongly-typed Pydantic result models
- Graceful handling of empty results and unknown steps/components without exceptions
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    ComponentMigrationStatus,
    CoupledComponent,
    CouplingResult,
    DecommissionCandidate,
    DecommissionResult,
    GraphQueryRequest,
    MigrationStatusResult,
    SymbolQueryResult,
)
from .store import GraphStoreProtocol

logger = logging.getLogger(__name__)


def get_migration_status(
    store: GraphStoreProtocol,
    step_id: str,
    component: str | None = None,
) -> MigrationStatusResult:
    """Query component migration status for a given migration step.

    Returns the active legacy components, live target microservices, and
    their associated bounded contexts.
    """
    try:
        props: dict[str, Any] = {"stepId": step_id}
        if component:
            props["name"] = component

        comp_nodes = store.get_nodes(label="Component", properties=props)

        # If component name was given but not matched via property, check node.name directly
        if component and not comp_nodes:
            all_step_nodes = store.get_nodes(label="Component", properties={"stepId": step_id})
            comp_nodes = [n for n in all_step_nodes if n.name.lower() == component.lower()]

        # Collect bounded contexts for each component via IMPLEMENTS edges
        implements_edges = store.get_edges(relationship_type="IMPLEMENTS")
        edge_map: dict[str, list[str]] = {}
        for edge in implements_edges:
            if edge.properties.get("stepId") == step_id or not edge.properties.get("stepId"):
                # Target is bounded context node
                bc_nodes = store.get_nodes(label="BoundedContext")
                bc_name = next((b.name for b in bc_nodes if b.id == edge.target_id), edge.target_id)
                edge_map.setdefault(edge.source_id, []).append(bc_name)

        status_entries: list[ComponentMigrationStatus] = []
        for node in comp_nodes:
            status_entries.append(
                ComponentMigrationStatus(
                    component=node.name,
                    origin=node.properties.get("origin", "legacy"),
                    status=node.properties.get("status", "active_legacy"),
                    bounded_contexts=edge_map.get(node.id, []),
                    description=node.properties.get("description", ""),
                    evidence=node.properties.get("evidence", []),
                )
            )

        # Count decommissioned candidates for this step
        decommissioned_nodes = store.get_nodes(
            properties={"stepId": step_id, "status": "decommissioned"}
        )

        active_legacy = sum(1 for s in status_entries if s.status == "active_legacy")
        live_target = sum(1 for s in status_entries if s.status == "live_target")
        total_decommissioned = len(decommissioned_nodes)

        return MigrationStatusResult(
            step_id=step_id,
            components=status_entries,
            total_active_legacy=active_legacy,
            total_live_target=live_target,
            total_decommissioned=total_decommissioned,
        )
    except Exception as exc:
        logger.warning("Error querying migration status for %s: %s", step_id, exc)
        return MigrationStatusResult(
            step_id=step_id,
            components=[],
            total_active_legacy=0,
            total_live_target=0,
            total_decommissioned=0,
        )


def get_coupled_components(
    store: GraphStoreProtocol,
    step_id: str,
) -> CouplingResult:
    """Query components coupled across migration boundaries for a given step.

    Identifies shared databases, messaging topics (Kafka), and synchronous HTTP
    links between legacy components and extracted target microservices.
    """
    try:
        edges = store.get_edges(relationship_type="COUPLED_VIA")
        couplings: list[CoupledComponent] = []

        all_nodes = {n.id: n for n in store.get_nodes()}

        for edge in edges:
            edge_step = edge.properties.get("stepId")
            if edge_step and edge_step != step_id:
                continue

            source_name = all_nodes.get(edge.source_id, edge.source_id).name if edge.source_id in all_nodes else edge.source_id
            target_name = all_nodes.get(edge.target_id, edge.target_id).name if edge.target_id in all_nodes else edge.target_id

            couplings.append(
                CoupledComponent(
                    source_component=source_name,
                    target_component=target_name,
                    coupling_type=edge.properties.get("couplingType", "messaging_topic"),
                    resource_name=edge.properties.get("resourceName", ""),
                    description=edge.properties.get("description", ""),
                    evidence=edge.properties.get("evidence", []),
                )
            )

        if couplings:
            summary = (
                f"Identified {len(couplings)} active coupling(s) in {step_id}: "
                + ", ".join(f"{c.source_component} <-> {c.target_component} via {c.resource_name}" for c in couplings)
            )
        else:
            summary = f"No cross-component couplings detected for {step_id}."

        return CouplingResult(
            step_id=step_id,
            couplings=couplings,
            summary=summary,
        )
    except Exception as exc:
        logger.warning("Error querying component couplings for %s: %s", step_id, exc)
        return CouplingResult(
            step_id=step_id,
            couplings=[],
            summary=f"Query failed gracefully for {step_id}.",
        )


def get_decommission_candidates(
    store: GraphStoreProtocol,
    step_id: str,
) -> DecommissionResult:
    """Query candidates safe for decommissioning in the given migration step.

    Returns endpoints, classes, or modules that have been replaced in the target
    architecture and remain as dead code in the legacy codebase.
    """
    try:
        nodes = store.get_nodes(properties={"stepId": step_id, "status": "decommissioned"})
        candidates: list[DecommissionCandidate] = []

        for node in nodes:
            candidates.append(
                DecommissionCandidate(
                    name=node.name,
                    kind=node.properties.get("kind", "class"),
                    parent_component=node.properties.get("component", "unknown"),
                    replacement=node.properties.get("replacement", ""),
                    reason=node.properties.get("reason", "Replaced in target service."),
                    risk_level=node.properties.get("risk", "low"),
                    evidence=node.properties.get("evidence", []),
                )
            )

        if candidates:
            summary = (
                f"Found {len(candidates)} decommission candidate(s) in {step_id}. "
                "These elements are superseded by target services and can be removed."
            )
        else:
            summary = f"No decommission candidates identified for {step_id}."

        return DecommissionResult(
            step_id=step_id,
            candidates=candidates,
            summary=summary,
        )
    except Exception as exc:
        logger.warning("Error querying decommission candidates for %s: %s", step_id, exc)
        return DecommissionResult(
            step_id=step_id,
            candidates=[],
            summary=f"Query failed gracefully for {step_id}.",
        )


def get_component_symbols(
    store: GraphStoreProtocol,
    step_id: str,
    component: str,
    kind: str | None = None,
) -> SymbolQueryResult:
    """Query structural symbols observed in a component for a migration step."""
    try:
        props: dict[str, Any] = {"stepId": step_id, "component": component}
        if kind:
            props["kind"] = kind

        symbol_nodes = store.get_nodes(label="SymbolObservation", properties=props)
        symbols = [
            {"id": s.id, "name": s.name, **s.properties}
            for s in symbol_nodes
        ]

        return SymbolQueryResult(
            step_id=step_id,
            component=component,
            symbols=symbols,
            total_symbols=len(symbols),
        )
    except Exception as exc:
        logger.warning("Error querying symbols for %s in %s: %s", component, step_id, exc)
        return SymbolQueryResult(
            step_id=step_id,
            component=component,
            symbols=[],
            total_symbols=0,
        )


def execute_graph_query(
    store: GraphStoreProtocol,
    request: GraphQueryRequest,
) -> MigrationStatusResult | CouplingResult | DecommissionResult | SymbolQueryResult:
    """Dispatch a generic graph query request to the appropriate query function."""
    if request.query_type == "migration_status":
        return get_migration_status(store, request.step_id, request.component)
    if request.query_type == "couplings":
        return get_coupled_components(store, request.step_id)
    if request.query_type == "decommission_candidates":
        return get_decommission_candidates(store, request.step_id)
    if request.query_type == "component_symbols":
        component = request.component or request.parameters.get("component", "monolith")
        kind = request.parameters.get("kind")
        return get_component_symbols(store, request.step_id, component, kind)

    raise ValueError(f"Unknown query_type: {request.query_type}")
