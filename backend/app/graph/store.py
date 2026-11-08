"""Knowledge Graph Store protocol and in-memory implementation (Issue #23).

Pre-seeded with the authoritative step-05 -> step-06 migration baseline defined in
Documentation/migration-verification.md and allows custom fact ingestion.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from .models import GraphEdge, GraphNode

logger = logging.getLogger(__name__)


class GraphStoreProtocol(Protocol):
    """Abstraction for graph storage (mock in-memory or PostgreSQL 17 / Apache AGE)."""

    def get_nodes(
        self, label: str | None = None, properties: dict[str, Any] | None = None
    ) -> list[GraphNode]:
        """Query nodes matching label and optional key/value properties."""
        ...

    def get_edges(
        self,
        relationship_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]:
        """Query edges matching relationship type and endpoint IDs."""
        ...

    def add_node(self, node: GraphNode) -> None:
        """Insert or replace a node in the graph."""
        ...

    def add_edge(self, edge: GraphEdge) -> None:
        """Insert or replace a directed edge in the graph."""
        ...


class InMemoryGraphStore:
    """Deterministic in-memory graph store seeded with the step-05/step-06 baseline."""

    def __init__(self, seed_baseline: bool = True) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        if seed_baseline:
            self._seed_reference_baseline()

    def get_nodes(
        self, label: str | None = None, properties: dict[str, Any] | None = None
    ) -> list[GraphNode]:
        results: list[GraphNode] = []
        for node in self._nodes.values():
            if label and node.label != label:
                continue
            if properties:
                match = True
                for k, v in properties.items():
                    if node.properties.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            results.append(node)
        return results

    def get_edges(
        self,
        relationship_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]:
        results: list[GraphEdge] = []
        for edge in self._edges.values():
            if relationship_type and edge.relationship_type != relationship_type:
                continue
            if source_id and edge.source_id != source_id:
                continue
            if target_id and edge.target_id != target_id:
                continue
            results.append(edge)
        return results

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self._edges[edge.id] = edge

    def _seed_reference_baseline(self) -> None:
        """Seed the verified step-05 and step-06 reference systems."""
        # 1. Bounded Context Nodes
        self.add_node(
            GraphNode(
                id="bc:customer-order",
                label="BoundedContext",
                name="Customer and Order",
                properties={"description": "Customer profiles, orders, and checkout"},
            )
        )
        self.add_node(
            GraphNode(
                id="bc:catalog",
                label="BoundedContext",
                name="Catalog",
                properties={"description": "Products, categories, and item pricing"},
            )
        )

        # 2. Components for step-05
        self.add_node(
            GraphNode(
                id="comp:monolith:step-05",
                label="Component",
                name="monolith",
                properties={
                    "stepId": "step-05",
                    "origin": "legacy",
                    "status": "active_legacy",
                    "description": "Open Liberty Java EE monolith hosting CustomerOrder & Catalog",
                    "port": 9080,
                    "evidence": ["git:monolith@fc150cc:CustomerOrderServices/ejbModule"],
                },
            )
        )
        self.add_node(
            GraphNode(
                id="comp:db2:step-05",
                label="Component",
                name="db2",
                properties={
                    "stepId": "step-05",
                    "origin": "legacy",
                    "status": "active_legacy",
                    "description": "Db2 relational database for monolith",
                    "evidence": ["git:db2@4f4f3d2:createOrderDB.sql"],
                },
            )
        )

        # 3. Components for step-06
        self.add_node(
            GraphNode(
                id="comp:monolith:step-06",
                label="Component",
                name="monolith",
                properties={
                    "stepId": "step-06",
                    "origin": "legacy",
                    "status": "active_legacy",
                    "description": "Cloud-native CDI refactored monolith without catalog endpoints",
                    "port": 9088,
                    "evidence": ["git:monolith@73ab85c:pom.xml"],
                },
            )
        )
        self.add_node(
            GraphNode(
                id="comp:catalog-service:step-06",
                label="Component",
                name="catalog-service",
                properties={
                    "stepId": "step-06",
                    "origin": "target",
                    "status": "live_target",
                    "description": "Quarkus 1.1.1.Final microservice extracted via Strangler Fig",
                    "port": 8082,
                    "evidence": ["git:catalog-service@474422c:src/main/java"],
                },
            )
        )
        self.add_node(
            GraphNode(
                id="comp:proxy:step-06",
                label="Component",
                name="proxy",
                properties={
                    "stepId": "step-06",
                    "origin": "legacy",
                    "status": "active_legacy",
                    "description": "Nginx reverse proxy strangling /Category and /Product routes",
                    "evidence": ["git:proxy@c52d943:nginx-catalog-native.conf"],
                },
            )
        )

        # 4. Decommissioned / Dead Code Nodes in step-06
        self.add_node(
            GraphNode(
                id="symbol:monolith:CategoryResource:step-06",
                label="SymbolObservation",
                name="CategoryResource",
                properties={
                    "stepId": "step-06",
                    "component": "monolith",
                    "kind": "class",
                    "status": "decommissioned",
                    "replacement": "catalog-service:CategoryResource",
                    "reason": "Proxy routes all /Category requests to catalog-service:8082. Monolith code is unreachable dead code.",
                    "risk": "low",
                    "evidence": ["git:proxy@c52d943:nginx-catalog-native.conf#L12-L18"],
                },
            )
        )
        self.add_node(
            GraphNode(
                id="symbol:monolith:ProductResource:step-06",
                label="SymbolObservation",
                name="ProductResource",
                properties={
                    "stepId": "step-06",
                    "component": "monolith",
                    "kind": "class",
                    "status": "decommissioned",
                    "replacement": "catalog-service:ProductResource",
                    "reason": "Proxy routes all /Product requests to catalog-service:8082. Monolith code is unreachable dead code.",
                    "risk": "low",
                    "evidence": ["git:proxy@c52d943:nginx-catalog-native.conf#L20-L26"],
                },
            )
        )

        # 5. Edges: IMPLEMENTS BoundedContext
        self.add_edge(
            GraphEdge(
                id="edge:monolith:implements:co:step-06",
                source_id="comp:monolith:step-06",
                target_id="bc:customer-order",
                relationship_type="IMPLEMENTS",
                properties={"stepId": "step-06"},
            )
        )
        self.add_edge(
            GraphEdge(
                id="edge:catalog:implements:cat:step-06",
                source_id="comp:catalog-service:step-06",
                target_id="bc:catalog",
                relationship_type="IMPLEMENTS",
                properties={"stepId": "step-06"},
            )
        )

        # 6. Edges: Asynchronous Coupling (Kafka topic in step-06)
        self.add_edge(
            GraphEdge(
                id="edge:kafka:price-update:step-06",
                source_id="comp:catalog-service:step-06",
                target_id="comp:monolith:step-06",
                relationship_type="COUPLED_VIA",
                properties={
                    "stepId": "step-06",
                    "couplingType": "messaging_topic",
                    "resourceName": "product-price-updated",
                    "description": "catalog-service publishes price change events; monolith consumes them to update LINE_ITEM.PRICE_CURRENT",
                    "evidence": [
                        "git:catalog-service@474422c:ProductPriceChanged.java",
                        "git:monolith@73ab85c:ProductPriceChanged.java",
                    ],
                },
            )
        )

        # 7. Edges: Database Coupling
        self.add_edge(
            GraphEdge(
                id="edge:db:line-item:step-06",
                source_id="comp:monolith:step-06",
                target_id="comp:catalog-service:step-06",
                relationship_type="COUPLED_VIA",
                properties={
                    "stepId": "step-06",
                    "couplingType": "shared_schema",
                    "resourceName": "LINE_ITEM.PRICE_CURRENT",
                    "description": "Monolith synchronizes line item price from catalog service product prices",
                    "evidence": ["git:db2@129ed26:createOrderDB.sql#L45"],
                },
            )
        )
