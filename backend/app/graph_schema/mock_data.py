"""Tiny MOCK graph for schema v2: snapshots step-05 and step-06 (issue #21).

Shape follows the example in Rafael's schema (issue #77, section 2.5).
Names, paths and commit ids are illustrative mock values, not read from the
real reference repositories.
"""

from __future__ import annotations

from .models import (
    ClassNode,
    CodeGraphNode,
    ComponentNode,
    ComponentStateNode,
    ExternalSymbolNode,
    FileNode,
    GraphEdge,
    GraphNodeModel,
    InterfaceNode,
    MethodNode,
    ProjectNode,
    SnapshotNode,
    SourceSpan,
    compute_entity_id,
    compute_file_id,
)

STEP_05 = "step-05"
STEP_06 = "step-06"
COMPONENT_KEY = "monolith"
REPO_ID = "legacy-example-monolith"
COMMIT_05 = "a1b2c3d"
COMMIT_06 = "73ab85c"
COMMITS = {"step-05": COMMIT_05, "step-06": COMMIT_06}

PROJECT_ID = "project:ibm-legacy-example"
COMPONENT_ID = "comp:monolith"
CS_05 = "cs:monolith:step-05"
CS_06 = "cs:monolith:step-06"
CG_05 = "cg:monolith:step-05"
CG_06 = "cg:monolith:step-06"
EXTERNAL_ID = "ext:javax.persistence.EntityManager.persist"

INTERFACE_PATH = "CustomerOrderServices/src/main/java/org/acme/CustomerOrderServices.java"
IMPL_PATH = "CustomerOrderServices/src/main/java/org/acme/CustomerOrderServicesImpl.java"

INTERFACE_QNAME = "org.acme.CustomerOrderServices"
CLASS_QNAME = "org.acme.CustomerOrderServicesImpl"
PROCESS_QNAME = "org.acme.CustomerOrderServicesImpl.process"
UPDATE_QNAME = "org.acme.CustomerOrderServicesImpl.updateLineItem"
PROCESS_SIGNATURE = "process(PriceChange)"
UPDATE_SIGNATURE = "updateLineItem(LineItem,int)"


def _file(path: str, snapshot_id: str = STEP_06) -> FileNode:
    return FileNode(
        id=compute_file_id(snapshot_id, COMPONENT_KEY, path),
        snapshot_id=snapshot_id,
        component_key=COMPONENT_KEY,
        path=path,
        content_hash="mock-" + path.rsplit("/", 1)[-1],
    )


def _entity(
    model,
    *,
    name: str,
    qualified_name: str,
    path: str,
    start_line: int,
    end_line: int,
    snapshot_id: str = STEP_06,
    signature: str | None = None,
):
    """Build a Class / Interface / Method node with the hash id of the schema.

    Pass `signature` for a Method only. The span uses the commit of the snapshot.
    """
    label = model.model_fields["label"].default
    extra = {"signature": signature} if signature is not None else {}
    return model(
        id=compute_entity_id(snapshot_id, COMPONENT_KEY, path, label, qualified_name, signature),
        **extra,
        name=name,
        snapshot_id=snapshot_id,
        owner_component_state_id=f"cs:{COMPONENT_KEY}:{snapshot_id}",
        component_key=COMPONENT_KEY,
        path=path,
        qualified_name=qualified_name,
        source_span=SourceSpan(
            repo_id=REPO_ID,
            path=path,
            commit_sha=COMMITS[snapshot_id],
            start_line=start_line,
            end_line=end_line,
        ),
        evidence=[f"git:{REPO_ID}@{COMMITS[snapshot_id]}:{path}#L{start_line}-L{end_line}"],
    )


def build_mock_graph() -> tuple[list[GraphNodeModel], list[GraphEdge]]:
    """Return (nodes, edges). Fresh objects on every call."""
    project = ProjectNode(id=PROJECT_ID, name="IBM legacy example")
    snap_05 = SnapshotNode(id=STEP_05, title="step-05", commit_sha=COMMIT_05)
    snap_06 = SnapshotNode(id=STEP_06, title="step-06", commit_sha=COMMIT_06)
    monolith = ComponentNode(id=COMPONENT_ID, key=COMPONENT_KEY, repo=REPO_ID)
    cs_05 = ComponentStateNode(
        id=CS_05, snapshot_id=STEP_05, commit_sha=COMMIT_05, migration_role="legacy"
    )
    cs_06 = ComponentStateNode(
        id=CS_06, snapshot_id=STEP_06, commit_sha=COMMIT_06, migration_role="legacy"
    )
    cg_05 = CodeGraphNode(
        id=CG_05, snapshot_id=STEP_05, run_id="run-mock-05", graphify_version="0.9.100"
    )
    cg_06 = CodeGraphNode(
        id=CG_06, snapshot_id=STEP_06, run_id="run-mock-06", graphify_version="0.9.100"
    )

    file_interface = _file(INTERFACE_PATH)
    file_impl = _file(IMPL_PATH)

    interface = _entity(
        InterfaceNode,
        name="CustomerOrderServices",
        qualified_name=INTERFACE_QNAME,
        path=INTERFACE_PATH,
        start_line=12,
        end_line=34,
    )
    impl = _entity(
        ClassNode,
        name="CustomerOrderServicesImpl",
        qualified_name=CLASS_QNAME,
        path=IMPL_PATH,
        start_line=18,
        end_line=142,
    )
    process = _entity(
        MethodNode,
        name="process",
        qualified_name=PROCESS_QNAME,
        path=IMPL_PATH,
        start_line=47,
        end_line=63,
        signature=PROCESS_SIGNATURE,
    )
    update = _entity(
        MethodNode,
        name="updateLineItem",
        qualified_name=UPDATE_QNAME,
        path=IMPL_PATH,
        start_line=71,
        end_line=98,
        signature=UPDATE_SIGNATURE,
    )
    external = ExternalSymbolNode(id=EXTERNAL_ID, name="javax.persistence.EntityManager.persist")

    nodes: list[GraphNodeModel] = [
        project,
        snap_05,
        snap_06,
        monolith,
        cs_05,
        cs_06,
        cg_05,
        cg_06,
        file_interface,
        file_impl,
        interface,
        impl,
        process,
        update,
        external,
    ]

    def edge(kind: str, src: GraphNodeModel, dst: GraphNodeModel) -> GraphEdge:
        return GraphEdge(
            id=f"edge:{kind}:{src.id}->{dst.id}",
            source_id=src.id,
            target_id=dst.id,
            relationship_type=kind,
        )

    edges: list[GraphEdge] = [
        edge("HAS_SNAPSHOT", project, snap_05),
        edge("HAS_SNAPSHOT", project, snap_06),
        edge("HAS_BASELINE", project, snap_05),
        edge("DERIVED_FROM", snap_06, snap_05),  # the only edge across snapshots
        edge("HAS_COMPONENT", snap_05, cs_05),
        edge("HAS_COMPONENT", snap_06, cs_06),
        edge("OF_COMPONENT", cs_05, monolith),
        edge("OF_COMPONENT", cs_06, monolith),
        edge("HAS_CODE_GRAPH", cs_05, cg_05),
        edge("HAS_CODE_GRAPH", cs_06, cg_06),
        edge("HAS_FILE", cg_06, file_interface),
        edge("HAS_FILE", cg_06, file_impl),
        edge("DECLARES", file_interface, interface),
        edge("DECLARES", file_impl, impl),
        edge("DECLARES_MEMBER", impl, process),
        edge("DECLARES_MEMBER", impl, update),
        edge("IMPLEMENTS", impl, interface),
        edge("CALLS", process, update),
        edge("CALLS", process, external),
    ]
    return nodes, edges
