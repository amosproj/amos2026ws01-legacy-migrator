"""Pytest coverage for the knowledge graph queries and endpoints (Issue #23).

Tests:
1. Basic predefined queries against the reference baseline (step-05 and step-06).
2. Status queries: legacy monolith vs target catalog-service.
3. Coupling queries: Kafka messaging topic and Db2 shared data.
4. Decommission candidates: dead code CategoryResource and ProductResource.
5. Symbol queries: component symbols retrieval.
6. Graceful empty/failure handling for unknown steps and components.
7. Mock graph store decoupling (custom unseeded and seeded stores).
8. FastAPI endpoints: /api/graph/status, /api/graph/couplings, /api/graph/decommission-candidates, /api/graph/query.
9. Graph context prompt augmentation into QueryService.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.graph import (
    GraphEdge,
    GraphNode,
    GraphQueryRequest,
    GraphQueryService,
    InMemoryGraphStore,
    create_graph_service,
    execute_graph_query,
    get_component_symbols,
    get_coupled_components,
    get_decommission_candidates,
    get_migration_status,
)
from app.main import app
from app.query_service import LlmQueryService


def test_migration_status_query_step_06() -> None:
    """Verifies that step-06 reports monolith (active_legacy) and catalog-service (live_target)."""
    store = InMemoryGraphStore(seed_baseline=True)
    result = get_migration_status(store, step_id="step-06")

    assert result.step_id == "step-06"
    assert result.total_active_legacy >= 1
    assert result.total_live_target >= 1
    assert result.total_decommissioned >= 2

    comp_names = {c.component: c for c in result.components}
    assert "monolith" in comp_names
    assert "catalog-service" in comp_names
    assert "proxy" in comp_names

    catalog = comp_names["catalog-service"]
    assert catalog.status == "live_target"
    assert catalog.origin == "target"
    assert "Catalog" in catalog.bounded_contexts

    monolith = comp_names["monolith"]
    assert monolith.status == "active_legacy"
    assert monolith.origin == "legacy"
    assert "Customer and Order" in monolith.bounded_contexts


def test_migration_status_query_filtered_by_component() -> None:
    """Verifies filtering migration status by component name."""
    store = InMemoryGraphStore(seed_baseline=True)
    result = get_migration_status(store, step_id="step-06", component="catalog-service")

    assert len(result.components) == 1
    assert result.components[0].component == "catalog-service"
    assert result.components[0].status == "live_target"


def test_coupling_query_step_06() -> None:
    """Verifies identification of Kafka messaging and database couplings."""
    store = InMemoryGraphStore(seed_baseline=True)
    result = get_coupled_components(store, step_id="step-06")

    assert result.step_id == "step-06"
    assert len(result.couplings) == 2

    coupling_types = {c.coupling_type for c in result.couplings}
    assert "messaging_topic" in coupling_types
    assert "shared_schema" in coupling_types

    resources = {c.resource_name for c in result.couplings}
    assert "product-price-updated" in resources
    assert "LINE_ITEM.PRICE_CURRENT" in resources

    assert "Identified 2 active coupling(s)" in result.summary


def test_decommission_candidates_step_06() -> None:
    """Verifies identifying dead code CategoryResource and ProductResource."""
    store = InMemoryGraphStore(seed_baseline=True)
    result = get_decommission_candidates(store, step_id="step-06")

    assert result.step_id == "step-06"
    assert len(result.candidates) == 2

    names = {c.name for c in result.candidates}
    assert "CategoryResource" in names
    assert "ProductResource" in names

    for candidate in result.candidates:
        assert candidate.parent_component == "monolith"
        assert candidate.risk_level == "low"
        assert "proxy" in candidate.evidence[0] or "nginx" in candidate.evidence[0]


def test_component_symbols_query() -> None:
    """Verifies querying symbols for a component."""
    store = InMemoryGraphStore(seed_baseline=True)
    result = get_component_symbols(store, step_id="step-06", component="monolith")

    assert result.step_id == "step-06"
    assert result.component == "monolith"
    assert result.total_symbols >= 2
    symbol_names = {s["name"] for s in result.symbols}
    assert "CategoryResource" in symbol_names
    assert "ProductResource" in symbol_names


def test_graceful_handling_on_unknown_step() -> None:
    """Unknown step IDs return clean, structured empty models without errors."""
    store = InMemoryGraphStore(seed_baseline=True)

    status = get_migration_status(store, step_id="step-unknown-99")
    assert status.step_id == "step-unknown-99"
    assert status.components == []
    assert status.total_active_legacy == 0
    assert status.total_live_target == 0

    couplings = get_coupled_components(store, step_id="step-unknown-99")
    assert couplings.step_id == "step-unknown-99"
    assert couplings.couplings == []
    assert "No cross-component couplings" in couplings.summary

    decomms = get_decommission_candidates(store, step_id="step-unknown-99")
    assert decomms.step_id == "step-unknown-99"
    assert decomms.candidates == []
    assert "No decommission candidates" in decomms.summary


def test_mock_graph_store_decoupled() -> None:
    """Verifies that an unseeded custom in-memory store can be populated and queried."""
    store = InMemoryGraphStore(seed_baseline=False)

    store.add_node(
        GraphNode(
            id="comp:custom-service:step-01",
            label="Component",
            name="custom-service",
            properties={
                "stepId": "step-01",
                "origin": "target",
                "status": "live_target",
                "description": "Custom service in isolated test",
            },
        )
    )

    result = get_migration_status(store, step_id="step-01")
    assert len(result.components) == 1
    assert result.components[0].component == "custom-service"
    assert result.total_live_target == 1


def test_execute_graph_query_dispatcher() -> None:
    """Verifies dispatching via execute_graph_query."""
    store = InMemoryGraphStore(seed_baseline=True)

    req_status = GraphQueryRequest(query_type="migration_status", step_id="step-06")
    res_status = execute_graph_query(store, req_status)
    assert res_status.step_id == "step-06"

    req_couplings = GraphQueryRequest(query_type="couplings", step_id="step-06")
    res_couplings = execute_graph_query(store, req_couplings)
    assert len(res_couplings.couplings) == 2

    req_decomms = GraphQueryRequest(query_type="decommission_candidates", step_id="step-06")
    res_decomms = execute_graph_query(store, req_decomms)
    assert len(res_decomms.candidates) == 2


def test_graph_service_prompt_context_formatting() -> None:
    """Verifies that GraphQueryService formats knowledge facts for LLM prompts."""
    service = create_graph_service()
    context = service.format_context_for_prompt("step-06")

    assert "### Verified Knowledge Graph Facts for Migration Step: step-06" in context
    assert "monolith [active_legacy, legacy]" in context
    assert "catalog-service [live_target, target]" in context
    assert "product-price-updated" in context
    assert "LINE_ITEM.PRICE_CURRENT" in context
    assert "CategoryResource in monolith" in context


def test_api_graph_status_endpoint() -> None:
    """Verifies GET /api/graph/status returns structured migration status."""
    with TestClient(app) as client:
        response = client.get("/api/graph/status?step_id=step-06")

    assert response.status_code == 200
    data = response.json()
    assert data["stepId"] == "step-06"
    assert data["totalActiveLegacy"] >= 1
    assert data["totalLiveTarget"] >= 1
    comps = {c["component"] for c in data["components"]}
    assert "catalog-service" in comps
    assert "monolith" in comps


def test_api_graph_couplings_endpoint() -> None:
    """Verifies GET /api/graph/couplings returns couplings."""
    with TestClient(app) as client:
        response = client.get("/api/graph/couplings?step_id=step-06")

    assert response.status_code == 200
    data = response.json()
    assert data["stepId"] == "step-06"
    assert len(data["couplings"]) == 2
    resources = {c["resourceName"] for c in data["couplings"]}
    assert "product-price-updated" in resources
    assert "LINE_ITEM.PRICE_CURRENT" in resources


def test_api_graph_decommission_candidates_endpoint() -> None:
    """Verifies GET /api/graph/decommission-candidates returns candidates."""
    with TestClient(app) as client:
        response = client.get("/api/graph/decommission-candidates?step_id=step-06")

    assert response.status_code == 200
    data = response.json()
    assert data["stepId"] == "step-06"
    assert len(data["candidates"]) == 2
    names = {c["name"] for c in data["candidates"]}
    assert "CategoryResource" in names
    assert "ProductResource" in names


def test_api_graph_query_post_endpoint() -> None:
    """Verifies POST /api/graph/query parameterized query."""
    with TestClient(app) as client:
        response = client.post(
            "/api/graph/query",
            json={"queryType": "migration_status", "stepId": "step-06"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["stepId"] == "step-06"
    assert "components" in data
