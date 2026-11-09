"""Tests for the initial graph schema v2 (issue #21, based on Rafael's #77)."""

import hashlib
from typing import get_args

import pytest
from pydantic import ValidationError

from app.graph_schema import (
    ALLOWED_EDGES,
    ClassNode,
    ComponentStateNode,
    GraphEdge,
    MethodNode,
    SchemaValidationError,
    assert_valid_graph,
    compute_entity_id,
    compute_file_id,
    models,
    normalize_path,
    snapshot_of,
    validate_graph,
)
from app.graph_schema import validator as rules
from app.graph_schema.mock_data import (
    CG_05,
    CG_06,
    COMPONENT_ID,
    COMPONENT_KEY,
    CS_05,
    CS_06,
    EXTERNAL_ID,
    IMPL_PATH,
    PROCESS_QNAME,
    STEP_05,
    STEP_06,
    UPDATE_QNAME,
    build_mock_graph,
)


def _rules_found(nodes, edges) -> list[str]:
    return [v.rule for v in validate_graph(nodes, edges)]


def _find(items, item_id):
    return next(i for i in items if i.id == item_id)


def _by_qname(nodes, qualified_name):
    return next(n for n in nodes if getattr(n, "qualified_name", None) == qualified_name)


def _edge(kind: str, source_id: str, target_id: str) -> GraphEdge:
    return GraphEdge(
        id=f"edge:{kind}:{source_id}->{target_id}",
        source_id=source_id,
        target_id=target_id,
        relationship_type=kind,
    )


def _method_in_step_05() -> MethodNode:
    """A method in the OTHER snapshot (same name and path as the step-06 one)."""
    return MethodNode(
        id=compute_entity_id(STEP_05, COMPONENT_KEY, IMPL_PATH, "Method", PROCESS_QNAME),
        name="process",
        snapshot_id=STEP_05,
        owner_component_state_id=CS_05,
        component_key=COMPONENT_KEY,
        path=IMPL_PATH,
        qualified_name=PROCESS_QNAME,
    )


# ------------------------------------------------------------- valid mock


def test_mock_graph_is_valid() -> None:
    nodes, edges = build_mock_graph()

    assert validate_graph(nodes, edges) == []
    assert_valid_graph(nodes, edges)  # must not raise


def test_mock_graph_has_the_expected_shape() -> None:
    nodes, edges = build_mock_graph()

    labels = [n.label for n in nodes]
    assert labels.count("Project") == 1
    assert labels.count("Snapshot") == 2
    assert labels.count("Component") == 1
    assert labels.count("ComponentState") == 2  # one per snapshot
    assert labels.count("CodeGraph") == 2
    assert labels.count("File") == 2
    assert labels.count("Class") == 1
    assert labels.count("Interface") == 1
    assert labels.count("Method") == 2
    assert labels.count("ExternalSymbol") == 1
    assert {n.migration_role for n in nodes if isinstance(n, ComponentStateNode)} == {"legacy"}
    assert [e.relationship_type for e in edges].count("DERIVED_FROM") == 1


def test_to_record_has_the_flat_node_shape() -> None:
    nodes, edges = build_mock_graph()

    record = _find(nodes, CS_06).to_record()
    assert record == {
        "id": CS_06,
        "label": "ComponentState",
        "properties": {
            "snapshotId": STEP_06,
            "commitSha": "73ab85c",
            "migrationRole": "legacy",
        },
    }
    edge_record = edges[0].to_record()
    assert edge_record["relationshipType"] == "HAS_SNAPSHOT"
    assert {"sourceId", "targetId", "properties"} <= edge_record.keys()


def test_every_edge_type_has_allowed_pairs() -> None:
    assert set(ALLOWED_EDGES) == set(get_args(models.EdgeType))
    assert len(ALLOWED_EDGES) == 16
    # several pairs per edge type are supported
    assert ("File", "Class") in ALLOWED_EDGES["DECLARES"]
    assert ("File", "Function") in ALLOWED_EDGES["DECLARES"]
    assert ("Interface", "ExternalSymbol") in ALLOWED_EDGES["EXTENDS"]
    assert ("Class", "Interface") not in ALLOWED_EDGES["EXTENDS"]


# -------------------------------------------------------------- id formulas


def test_file_id_uses_snapshot_component_and_normalized_path() -> None:
    expected = hashlib.sha256(b"step-06:monolith:src/A.java").hexdigest()

    assert compute_file_id("step-06", "monolith", "src/A.java") == expected
    assert compute_file_id("step-06", "monolith", "\\src\\A.java/") == expected
    # same path in another snapshot or another component is another file
    assert compute_file_id("step-05", "monolith", "src/A.java") != expected
    assert compute_file_id("step-06", "catalog", "src/A.java") != expected


def test_entity_id_adds_kind_and_qualified_name() -> None:
    expected = hashlib.sha256(b"step-06:monolith:src/A.java:Class:com.A").hexdigest()

    assert compute_entity_id("step-06", "monolith", "\\src\\A.java", "Class", "com.A") == expected
    assert compute_entity_id("step-06", "monolith", "src/A.java", "Method", "com.A") != expected
    assert normalize_path("\\a\\b/") == "a/b"


def test_readable_ids_for_the_context_nodes() -> None:
    assert CS_06 == "cs:monolith:step-06"
    assert CG_06 == "cg:monolith:step-06"
    assert COMPONENT_ID == "comp:monolith"


# ------------------------------------------------ one failing case per rule


def test_rule_unique_node_ids() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(_find(nodes, CS_06).model_copy())  # same id twice

    assert _rules_found(nodes, edges) == [rules.DUPLICATE_NODE_ID]


def test_rule_unique_edge_ids() -> None:
    nodes, edges = build_mock_graph()
    edges.append(edges[0].model_copy())

    assert _rules_found(nodes, edges) == [rules.DUPLICATE_EDGE_ID]


def test_rule_edge_target_must_exist() -> None:
    nodes, edges = build_mock_graph()
    edges.append(_edge("OF_COMPONENT", CS_06, "comp:does-not-exist"))

    problems = validate_graph(nodes, edges)
    assert [p.rule for p in problems] == [rules.MISSING_ENDPOINT]
    assert "comp:does-not-exist" in problems[0].message


def test_rule_edge_source_must_exist() -> None:
    nodes, edges = build_mock_graph()
    edges.append(_edge("OF_COMPONENT", "cs:ghost", COMPONENT_ID))

    assert _rules_found(nodes, edges) == [rules.MISSING_ENDPOINT]


def test_rule_only_allowed_source_target_pairs() -> None:
    nodes, edges = build_mock_graph()
    process = _by_qname(nodes, PROCESS_QNAME)
    file_ = next(n for n in nodes if n.label == "File")
    # DECLARES allows File -> Class/Interface/Function/CodeEntity, not File -> Method
    edges.append(_edge("DECLARES", file_.id, process.id))

    assert _rules_found(nodes, edges) == [rules.BAD_ENDPOINT_PAIR]


def test_rule_edge_direction_matters() -> None:
    nodes, edges = build_mock_graph()
    edges.append(_edge("OF_COMPONENT", COMPONENT_ID, CS_06))  # wrong way round

    assert rules.BAD_ENDPOINT_PAIR in _rules_found(nodes, edges)


def test_several_allowed_pairs_per_edge_type() -> None:
    nodes, edges = build_mock_graph()
    impl = next(n for n in nodes if n.label == "Class")
    interface = next(n for n in nodes if n.label == "Interface")
    file_ = next(n for n in nodes if n.label == "File")
    edges += [
        _edge("EXTENDS", impl.id, EXTERNAL_ID),  # Class -> ExternalSymbol
        _edge("IMPORTS", file_.id, EXTERNAL_ID),  # File -> ExternalSymbol
        _edge("IMPORTS", file_.id, interface.id),  # File -> Interface
        _edge("CONTAINS_TYPE", impl.id, interface.id),  # Class -> Interface
        _edge("REFERENCES", impl.id, interface.id),
        _edge("SOURCED_FROM", impl.id, file_.id),
    ]

    assert validate_graph(nodes, edges) == []

    edges.append(_edge("EXTENDS", impl.id, interface.id))  # Class EXTENDS Interface: not allowed
    assert _rules_found(nodes, edges) == [rules.BAD_ENDPOINT_PAIR]


def test_rule_file_id_must_match_the_hash_formula() -> None:
    nodes, edges = build_mock_graph()
    file_ = next(n for n in nodes if n.label == "File")
    wrong = file_.model_copy(update={"id": "file:readable-id"})
    nodes[nodes.index(file_)] = wrong
    edges = [
        e.model_copy(update={"target_id": wrong.id}) if e.target_id == file_.id else e
        for e in edges
    ]
    edges = [
        e.model_copy(update={"source_id": wrong.id}) if e.source_id == file_.id else e
        for e in edges
    ]

    problems = validate_graph(nodes, edges)
    assert [p.rule for p in problems] == [rules.BAD_NODE_ID]


def test_rule_entity_id_must_match_the_hash_formula() -> None:
    nodes, edges = build_mock_graph()
    # a method with the right fields but the id of another snapshot
    wrong = _method_in_step_05().model_copy(update={"snapshot_id": STEP_06})
    nodes.append(wrong)

    problems = validate_graph(nodes, edges)
    assert [p.rule for p in problems] == [rules.BAD_NODE_ID]


# ----------------------------------------------------- same-snapshot rule


def test_rule_calls_must_stay_inside_one_snapshot() -> None:
    nodes, edges = build_mock_graph()
    other = _method_in_step_05()
    nodes.append(other)
    process = _by_qname(nodes, PROCESS_QNAME)
    edges.append(_edge("CALLS", process.id, other.id))

    assert _rules_found(nodes, edges) == [rules.CROSS_SNAPSHOT_EDGE]


def test_derived_from_is_the_only_edge_across_snapshots() -> None:
    nodes, edges = build_mock_graph()

    derived = [e for e in edges if e.relationship_type == "DERIVED_FROM"]
    assert snapshot_of(_find(nodes, derived[0].source_id)) == STEP_06
    assert snapshot_of(_find(nodes, derived[0].target_id)) == STEP_05
    assert validate_graph(nodes, edges) == []  # it is in the mock and passes


FILE_06 = compute_file_id(STEP_06, COMPONENT_KEY, IMPL_PATH)


@pytest.mark.parametrize(
    ("kind", "source_id", "target_id"),
    [
        ("HAS_COMPONENT", STEP_05, CS_06),  # step-05 Snapshot -> step-06 ComponentState
        ("HAS_COMPONENT", STEP_06, CS_05),
        ("HAS_CODE_GRAPH", CS_05, CG_06),
        ("HAS_FILE", CG_05, FILE_06),
    ],
)
def test_rule_context_edges_must_stay_inside_one_snapshot(kind, source_id, target_id) -> None:
    nodes, edges = build_mock_graph()
    edges.append(_edge(kind, source_id, target_id))

    assert _rules_found(nodes, edges) == [rules.CROSS_SNAPSHOT_EDGE]


def test_calls_to_external_symbol_skips_the_snapshot_rule() -> None:
    nodes, edges = build_mock_graph()
    process = _by_qname(nodes, PROCESS_QNAME)
    external = _find(nodes, EXTERNAL_ID)

    assert snapshot_of(external) is None
    assert any(
        e.relationship_type == "CALLS" and e.source_id == process.id and e.target_id == EXTERNAL_ID
        for e in edges
    )
    assert validate_graph(nodes, edges) == []

    # also for a method of another snapshot
    other = _method_in_step_05()
    nodes.append(other)
    edges.append(_edge("CALLS", other.id, EXTERNAL_ID))
    assert validate_graph(nodes, edges) == []


def test_assert_valid_graph_reports_every_problem() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(nodes[0].model_copy())  # duplicate id
    edges.append(_edge("OF_COMPONENT", CS_06, "nowhere"))
    edges.append(_edge("HAS_COMPONENT", STEP_05, CS_06))

    with pytest.raises(SchemaValidationError) as info:
        assert_valid_graph(nodes, edges)

    found = {v.rule for v in info.value.violations}
    assert {rules.DUPLICATE_NODE_ID, rules.MISSING_ENDPOINT, rules.CROSS_SNAPSHOT_EDGE} <= found


# ---------------------------------------------- shape checks in the models


def test_unknown_edge_type_is_rejected_by_the_model() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(id="e", source_id="a", target_id="b", relationship_type="LIKES")


def test_removed_v1_edge_types_are_rejected() -> None:
    for old in ("COUPLED_VIA", "CONTAINS"):
        with pytest.raises(ValidationError):
            GraphEdge(id="e", source_id="a", target_id="b", relationship_type=old)


def test_migration_role_must_be_one_of_the_four_values() -> None:
    for role in ("legacy", "target", "transition", "unknown"):
        assert ComponentStateNode(id="cs:x:s", snapshot_id="s", migration_role=role)
    with pytest.raises(ValidationError):
        ComponentStateNode(id="cs:x:s", snapshot_id="s", migration_role="decommissioned")


def test_code_entity_needs_snapshot_and_owner() -> None:
    with pytest.raises(ValidationError):
        ClassNode(id="x", name="A", component_key="m", path="A.java", qualified_name="A")


def test_unknown_fields_are_rejected() -> None:
    nodes, _ = build_mock_graph()
    data = _by_qname(nodes, PROCESS_QNAME).model_dump()
    data["status"] = "decommissioned"  # v1 field, removed

    with pytest.raises(ValidationError):
        MethodNode.model_validate(data)


# ---------------------------------------------------------------- queries


def component_entities(nodes, edges, snapshot_id: str, component_key: str):
    """Snapshot -> ComponentState -> CodeGraph -> File -> DECLARES -> DECLARES_MEMBER."""
    by_id = {n.id: n for n in nodes}

    def follow(source_id: str, relationship: str):
        return [
            by_id[e.target_id]
            for e in edges
            if e.source_id == source_id and e.relationship_type == relationship
        ]

    found = []
    for state in follow(snapshot_id, "HAS_COMPONENT"):
        if not any(c.key == component_key for c in follow(state.id, "OF_COMPONENT")):
            continue
        for code_graph in follow(state.id, "HAS_CODE_GRAPH"):
            for file_ in follow(code_graph.id, "HAS_FILE"):
                for declared in follow(file_.id, "DECLARES"):
                    found.append(declared)
                    found.extend(follow(declared.id, "DECLARES_MEMBER"))
    return found


def callers_of(nodes, edges, method_id: str):
    """Methods that CALL the given method (same snapshot by the schema rule)."""
    by_id = {n.id: n for n in nodes}
    return [
        by_id[e.source_id]
        for e in edges
        if e.relationship_type == "CALLS"
        and e.target_id == method_id
        and by_id[e.source_id].label == "Method"
        and snapshot_of(by_id[e.source_id]) == snapshot_of(by_id[method_id])
    ]


def test_query_all_code_entities_of_component_in_step_06() -> None:
    nodes, edges = build_mock_graph()

    entities = component_entities(nodes, edges, STEP_06, "monolith")

    assert sorted((e.label, e.name) for e in entities) == [
        ("Class", "CustomerOrderServicesImpl"),
        ("Interface", "CustomerOrderServices"),
        ("Method", "process"),
        ("Method", "updateLineItem"),
    ]
    assert {snapshot_of(e) for e in entities} == {STEP_06}


def test_query_component_entities_empty_for_other_snapshot_or_component() -> None:
    nodes, edges = build_mock_graph()

    assert component_entities(nodes, edges, STEP_05, "monolith") == []  # no files at step-05
    assert component_entities(nodes, edges, STEP_06, "nope") == []


def test_query_methods_that_call_a_method_in_one_snapshot() -> None:
    nodes, edges = build_mock_graph()
    update = _by_qname(nodes, UPDATE_QNAME)
    process = _by_qname(nodes, PROCESS_QNAME)

    assert [m.name for m in callers_of(nodes, edges, update.id)] == ["process"]
    assert callers_of(nodes, edges, process.id) == []  # nobody calls process


def test_query_callers_do_not_leak_from_another_snapshot() -> None:
    nodes, edges = build_mock_graph()
    new_process_id = _by_qname(nodes, PROCESS_QNAME).id
    new_update_id = _by_qname(nodes, UPDATE_QNAME).id
    # step-05 also has process() calling its own updateLineItem()
    old_process = _method_in_step_05()
    old_update = old_process.model_copy(
        update={
            "id": compute_entity_id(STEP_05, COMPONENT_KEY, IMPL_PATH, "Method", UPDATE_QNAME),
            "name": "updateLineItem",
            "qualified_name": UPDATE_QNAME,
        }
    )
    nodes += [old_process, old_update]
    edges.append(_edge("CALLS", old_process.id, old_update.id))
    assert validate_graph(nodes, edges) == []

    assert [c.id for c in callers_of(nodes, edges, new_update_id)] == [new_process_id]
    assert [c.id for c in callers_of(nodes, edges, old_update.id)] == [old_process.id]
