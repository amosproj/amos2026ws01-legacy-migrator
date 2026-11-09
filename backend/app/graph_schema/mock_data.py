"""Tiny MOCK graph for schema v1: step-05 -> step-06 Strangler Fig (issue #21).

Names and the Kafka topic follow the story in Documentation/migration-verification.md
(as used by the #85 seed data). File paths, line numbers and commit ids are
illustrative mock values, not read from the real reference repositories.
Snapshot ids are readable mock ids ("snap-step-06"), not real SHA-256 hashes.
"""

from __future__ import annotations

from .models import (
    BoundedContextNode,
    ComponentNode,
    FileNode,
    GraphEdge,
    GraphNodeModel,
    SourceSpan,
    SymbolObservationNode,
    compute_observation_id,
)

STEP_05 = "step-05"
STEP_06 = "step-06"
SNAP_06 = "snap-step-06"

MONOLITH_REPO = "monolith"
CATALOG_REPO = "catalog-service"

MONOLITH_FILE_PATH = "CustomerOrderServices/src/main/java/org/acme/CategoryResource.java"
CATALOG_FILE_PATH = "src/main/java/org/acme/catalog/CategoryResource.java"


def _symbol(
    *,
    repo_id: str,
    commit_sha: str,
    path: str,
    kind: str,
    name: str,
    qualified_name: str,
    start_line: int,
    end_line: int,
    parent: str | None = None,
    **extra,
) -> SymbolObservationNode:
    return SymbolObservationNode(
        id=compute_observation_id(SNAP_06, repo_id, path, kind, qualified_name),
        name=name,
        step_id=STEP_06,
        snapshot_id=SNAP_06,
        repo_id=repo_id,
        path=path,
        kind=kind,
        qualified_name=qualified_name,
        parent_qualified_name=parent,
        source_span=SourceSpan(
            repo_id=repo_id,
            commit_sha=commit_sha,
            path=path,
            start_line=start_line,
            end_line=end_line,
        ),
        evidence=[f"git:{repo_id}@{commit_sha}:{path}#L{start_line}-L{end_line}"],
        **extra,
    )


def build_mock_graph() -> tuple[list[GraphNodeModel], list[GraphEdge]]:
    """Return (nodes, edges). Fresh objects on every call."""
    # --- system level: one Component node per step (as in #85) ---------------
    monolith_05 = ComponentNode(
        id="comp:monolith:step-05",
        name="monolith",
        step_id=STEP_05,
        origin="legacy",
        status="active_legacy",
        description="Java EE monolith hosting Customer/Order and Catalog",
    )
    monolith_06 = ComponentNode(
        id="comp:monolith:step-06",
        name="monolith",
        step_id=STEP_06,
        origin="legacy",
        status="active_legacy",
        description="Monolith without catalog endpoints",
    )
    catalog_06 = ComponentNode(
        id="comp:catalog-service:step-06",
        name="catalog-service",
        step_id=STEP_06,
        origin="target",
        status="live_target",
        description="Microservice extracted via Strangler Fig",
        port=8082,
    )
    # The bounded context is also one node per step (same reason).
    bc_05 = BoundedContextNode(id="bc:catalog:step-05", name="Catalog", step_id=STEP_05)
    bc_06 = BoundedContextNode(id="bc:catalog:step-06", name="Catalog", step_id=STEP_06)

    # --- code level: files and symbols carry BOTH snapshotId and stepId ------
    file_monolith = FileNode(
        id="file:monolith:CategoryResource.java:step-06",
        name="CategoryResource.java",
        step_id=STEP_06,
        snapshot_id=SNAP_06,
        repo_id=MONOLITH_REPO,
        path=MONOLITH_FILE_PATH,
    )
    file_catalog = FileNode(
        id="file:catalog-service:CategoryResource.java:step-06",
        name="CategoryResource.java",
        step_id=STEP_06,
        snapshot_id=SNAP_06,
        repo_id=CATALOG_REPO,
        path=CATALOG_FILE_PATH,
    )

    monolith_class = _symbol(
        repo_id=MONOLITH_REPO,
        commit_sha="73ab85c",
        path=MONOLITH_FILE_PATH,
        kind="class",
        name="CategoryResource",
        qualified_name="org.acme.CategoryResource",
        start_line=10,
        end_line=60,
        status="decommissioned",
        replacement="catalog-service:CategoryResource",
        reason="Proxy sends all /Category requests to catalog-service; this code is unreachable.",
        risk="low",
    )
    monolith_method = _symbol(
        repo_id=MONOLITH_REPO,
        commit_sha="73ab85c",
        path=MONOLITH_FILE_PATH,
        kind="method",
        name="getCategories",
        qualified_name="org.acme.CategoryResource.getCategories",
        start_line=20,
        end_line=30,
        parent="org.acme.CategoryResource",
    )
    catalog_class = _symbol(
        repo_id=CATALOG_REPO,
        commit_sha="474422c",
        path=CATALOG_FILE_PATH,
        kind="class",
        name="CategoryResource",
        qualified_name="org.acme.catalog.CategoryResource",
        start_line=8,
        end_line=55,
    )
    catalog_method = _symbol(
        repo_id=CATALOG_REPO,
        commit_sha="474422c",
        path=CATALOG_FILE_PATH,
        kind="method",
        name="getCategories",
        qualified_name="org.acme.catalog.CategoryResource.getCategories",
        start_line=18,
        end_line=28,
        parent="org.acme.catalog.CategoryResource",
    )

    nodes: list[GraphNodeModel] = [
        monolith_05,
        monolith_06,
        catalog_06,
        bc_05,
        bc_06,
        file_monolith,
        file_catalog,
        monolith_class,
        monolith_method,
        catalog_class,
        catalog_method,
    ]

    def edge(kind: str, src: GraphNodeModel, dst: GraphNodeModel, **kw) -> GraphEdge:
        return GraphEdge(
            id=f"edge:{kind}:{src.id}->{dst.id}",
            source_id=src.id,
            target_id=dst.id,
            relationship_type=kind,
            **kw,
        )

    edges: list[GraphEdge] = [
        edge("IMPLEMENTS", monolith_05, bc_05, step_id=STEP_05),
        edge("IMPLEMENTS", catalog_06, bc_06, step_id=STEP_06),
        edge("CONTAINS", monolith_06, file_monolith, step_id=STEP_06),
        edge("CONTAINS", catalog_06, file_catalog, step_id=STEP_06),
        edge("DECLARES", file_monolith, monolith_class, snapshot_id=SNAP_06),
        edge("DECLARES", file_monolith, monolith_method, snapshot_id=SNAP_06),
        edge("DECLARES", file_catalog, catalog_class, snapshot_id=SNAP_06),
        edge("DECLARES", file_catalog, catalog_method, snapshot_id=SNAP_06),
        # Kafka topic: catalog-service publishes, monolith consumes (as in #85).
        edge(
            "COUPLED_VIA",
            catalog_06,
            monolith_06,
            step_id=STEP_06,
            properties={
                "couplingType": "messaging_topic",
                "resourceName": "product-price-updated",
                "description": "catalog-service publishes price changes; "
                "monolith consumes them to update LINE_ITEM.PRICE_CURRENT",
            },
            evidence=["git:catalog-service@474422c:ProductPriceChanged.java"],
        ),
    ]
    return nodes, edges
