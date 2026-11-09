"""Tests for the initial graph schema v1 (issue #21)."""

import hashlib

import pytest
from pydantic import ValidationError

from app.graph_schema import (
    ComponentNode,
    FileNode,
    GraphEdge,
    SchemaValidationError,
    SymbolObservationNode,
    assert_valid_graph,
    compute_observation_id,
    validate_graph,
)
from app.graph_schema import validator as rules
from app.graph_schema.mock_data import SNAP_06, STEP_06, build_mock_graph


def _rules_found(nodes, edges) -> set[str]:
    return {v.rule for v in validate_graph(nodes, edges)}


def _find(items, item_id):
    return next(i for i in items if i.id == item_id)


MONOLITH = "comp:monolith:step-06"
CATALOG = "comp:catalog-service:step-06"
FILE_M = "file:monolith:CategoryResource.java:step-06"
BC_05 = "bc:catalog:step-05"


# ------------------------------------------------------------- valid mock


def test_mock_graph_is_valid() -> None:
    nodes, edges = build_mock_graph()

    assert validate_graph(nodes, edges) == []
    assert_valid_graph(nodes, edges)  # must not raise


def test_mock_graph_has_the_expected_shape() -> None:
    nodes, edges = build_mock_graph()

    labels = sorted(n.label for n in nodes)
    assert labels.count("Component") == 3
    assert labels.count("BoundedContext") == 2  # one per step
    assert labels.count("File") == 2
    assert labels.count("SymbolObservation") == 4
    kafka = [e for e in edges if e.relationship_type == "COUPLED_VIA"]
    assert len(kafka) == 1
    assert kafka[0].properties["resourceName"] == "product-price-updated"


def test_to_record_has_the_flat_graph_node_shape() -> None:
    nodes, edges = build_mock_graph()

    record = _find(nodes, MONOLITH).to_record()
    assert record["label"] == "Component"
    assert record["properties"]["stepId"] == STEP_06
    assert record["properties"]["origin"] == "legacy"

    edge_record = next(e for e in edges if e.relationship_type == "COUPLED_VIA").to_record()
    assert edge_record["sourceId"] == CATALOG
    assert edge_record["properties"]["couplingType"] == "messaging_topic"
    assert edge_record["properties"]["stepId"] == STEP_06


# -------------------------------------------------------- id formula


def test_observation_id_uses_the_84_formula() -> None:
    expected = hashlib.sha256(b"snap:repo:src/A.java:class:com.A").hexdigest()

    assert compute_observation_id("snap", "repo", "src/A.java", "class", "com.A") == expected
    # path is normalised like in #84
    assert compute_observation_id("snap", "repo", "\\src\\A.java", "class", "com.A") == expected


# ------------------------------------------------ one failing case per rule


def test_rule_unique_node_ids() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(_find(nodes, MONOLITH).model_copy())  # same id twice

    assert rules.DUPLICATE_NODE_ID in _rules_found(nodes, edges)


def test_rule_unique_edge_ids() -> None:
    nodes, edges = build_mock_graph()
    edges.append(edges[0].model_copy())

    assert rules.DUPLICATE_EDGE_ID in _rules_found(nodes, edges)


def test_rule_edge_target_must_exist() -> None:
    nodes, edges = build_mock_graph()
    edges.append(
        GraphEdge(
            id="e-bad",
            source_id=MONOLITH,
            target_id="bc:does-not-exist",
            relationship_type="IMPLEMENTS",
            step_id=STEP_06,
        )
    )

    problems = validate_graph(nodes, edges)
    assert [p.rule for p in problems] == [rules.MISSING_ENDPOINT]
    assert "bc:does-not-exist" in problems[0].message


def test_rule_edge_source_must_exist() -> None:
    nodes, edges = build_mock_graph()
    edges.append(
        GraphEdge(
            id="e-bad",
            source_id="comp:ghost",
            target_id="bc:catalog:step-06",
            relationship_type="IMPLEMENTS",
            step_id=STEP_06,
        )
    )

    assert rules.MISSING_ENDPOINT in _rules_found(nodes, edges)


def test_rule_only_allowed_source_target_pairs() -> None:
    nodes, edges = build_mock_graph()
    # CONTAINS must be Component -> File, not Component -> SymbolObservation
    symbol = next(n for n in nodes if n.label == "SymbolObservation")
    edges.append(
        GraphEdge(
            id="e-bad",
            source_id=MONOLITH,
            target_id=symbol.id,
            relationship_type="CONTAINS",
            step_id=STEP_06,
        )
    )

    assert rules.BAD_ENDPOINT_PAIR in _rules_found(nodes, edges)


def test_rule_edge_direction_matters() -> None:
    nodes, edges = build_mock_graph()
    edges.append(  # BoundedContext -> Component is the wrong way round
        GraphEdge(
            id="e-bad",
            source_id="bc:catalog:step-06",
            target_id=CATALOG,
            relationship_type="IMPLEMENTS",
            step_id=STEP_06,
        )
    )

    assert rules.BAD_ENDPOINT_PAIR in _rules_found(nodes, edges)


def test_rule_node_needs_step_or_snapshot() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(
        ComponentNode(id="comp:lost", name="lost", origin="legacy", status="active_legacy")
    )

    problems = validate_graph(nodes, edges)
    assert [(p.rule, p.item_id) for p in problems] == [(rules.MISSING_SCOPE, "comp:lost")]


def test_rule_edge_needs_step_or_snapshot() -> None:
    nodes, edges = build_mock_graph()
    edges.append(
        GraphEdge(
            id="e-noscope",
            source_id=MONOLITH,
            target_id="bc:catalog:step-06",
            relationship_type="IMPLEMENTS",
        )
    )

    problems = validate_graph(nodes, edges)
    assert (rules.MISSING_SCOPE, "e-noscope") in [(p.rule, p.item_id) for p in problems]


def test_rule_code_nodes_need_a_snapshot_id() -> None:
    nodes, edges = build_mock_graph()
    index = nodes.index(_find(nodes, FILE_M))
    nodes[index] = nodes[index].model_copy(update={"snapshot_id": None})

    assert rules.MISSING_SNAPSHOT in _rules_found(nodes, edges)


def test_rule_symbol_id_must_match_the_hash_formula() -> None:
    nodes, edges = build_mock_graph()
    symbol = next(n for n in nodes if n.label == "SymbolObservation")
    wrong = symbol.model_copy(update={"id": "symbol:readable-id"})
    nodes[nodes.index(symbol)] = wrong
    edges = [
        e.model_copy(update={"target_id": wrong.id}) if e.target_id == symbol.id else e
        for e in edges
    ]

    problems = validate_graph(nodes, edges)
    assert [p.rule for p in problems] == [rules.BAD_OBSERVATION_ID]


def test_rule_edge_must_stay_inside_one_step() -> None:
    nodes, edges = build_mock_graph()
    edges.append(  # step-06 component -> step-05 bounded context
        GraphEdge(
            id="e-cross",
            source_id=MONOLITH,
            target_id=BC_05,
            relationship_type="IMPLEMENTS",
            step_id=STEP_06,
        )
    )

    assert rules.SCOPE_MISMATCH in _rules_found(nodes, edges)


def test_rule_edge_must_stay_inside_one_snapshot() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(
        FileNode(
            id="file:other-snapshot",
            name="X.java",
            step_id=STEP_06,
            snapshot_id="snap-other",
            repo_id="monolith",
            path="X.java",
        )
    )
    symbol = next(n for n in nodes if n.label == "SymbolObservation")
    edges.append(
        GraphEdge(
            id="e-snap",
            source_id="file:other-snapshot",
            target_id=symbol.id,
            relationship_type="DECLARES",
            snapshot_id=SNAP_06,
        )
    )

    assert rules.SCOPE_MISMATCH in _rules_found(nodes, edges)


def test_component_to_file_link_needs_a_shared_scope_key() -> None:
    """Component has only stepId, File only snapshotId: cannot be compared."""
    nodes, edges = build_mock_graph()
    index = nodes.index(_find(nodes, FILE_M))
    nodes[index] = nodes[index].model_copy(update={"step_id": None})

    problems = validate_graph(nodes, edges)
    assert rules.SCOPE_UNVERIFIABLE in {p.rule for p in problems}
    unverifiable = [p for p in problems if p.rule == rules.SCOPE_UNVERIFIABLE]
    assert unverifiable[0].item_id.startswith("edge:CONTAINS:")


def test_assert_valid_graph_reports_every_problem() -> None:
    nodes, edges = build_mock_graph()
    nodes.append(nodes[0].model_copy())  # duplicate id
    edges.append(
        GraphEdge(
            id="e-bad",
            source_id=MONOLITH,
            target_id="nowhere",
            relationship_type="IMPLEMENTS",
            step_id=STEP_06,
        )
    )

    with pytest.raises(SchemaValidationError) as info:
        assert_valid_graph(nodes, edges)

    found = {v.rule for v in info.value.violations}
    assert {rules.DUPLICATE_NODE_ID, rules.MISSING_ENDPOINT} <= found


# ---------------------------------------------- shape checks in the models


def test_unknown_edge_type_is_rejected_by_the_model() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(id="e", source_id="a", target_id="b", relationship_type="LIKES", step_id="s")


def test_coupled_via_needs_coupling_type_and_resource() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(
            id="e", source_id="a", target_id="b", relationship_type="COUPLED_VIA", step_id="s"
        )


def test_unknown_symbol_kind_is_rejected() -> None:
    nodes, _ = build_mock_graph()
    symbol = next(n for n in nodes if isinstance(n, SymbolObservationNode))
    data = symbol.model_dump()
    data["kind"] = "field"

    with pytest.raises(ValidationError):
        SymbolObservationNode.model_validate(data)


# --------------------------- query: "component symbols" by following edges


def component_symbols(nodes, edges, step_id: str, component: str, kind: str | None = None):
    """Component -CONTAINS-> File -DECLARES-> SymbolObservation (graph walk)."""
    by_id = {n.id: n for n in nodes}
    result = []
    for comp in (n for n in nodes if n.label == "Component"):
        if comp.name != component or comp.step_id != step_id:
            continue
        for contains in (e for e in edges if e.relationship_type == "CONTAINS"):
            if contains.source_id != comp.id:
                continue
            for declares in (e for e in edges if e.relationship_type == "DECLARES"):
                if declares.source_id != contains.target_id:
                    continue
                symbol = by_id[declares.target_id]
                if kind is None or symbol.kind == kind:
                    result.append(symbol)
    return result


def test_component_symbols_by_following_contains_then_declares() -> None:
    nodes, edges = build_mock_graph()

    symbols = component_symbols(nodes, edges, "step-06", "monolith")

    assert sorted(s.qualified_name for s in symbols) == [
        "org.acme.CategoryResource",
        "org.acme.CategoryResource.getCategories",
    ]
    catalog = component_symbols(nodes, edges, "step-06", "catalog-service")
    assert {s.repo_id for s in catalog} == {"catalog-service"}


def test_component_symbols_can_filter_by_kind_and_find_decommissioned() -> None:
    nodes, edges = build_mock_graph()

    classes = component_symbols(nodes, edges, "step-06", "monolith", kind="class")

    assert [c.name for c in classes] == ["CategoryResource"]
    assert classes[0].status == "decommissioned"
    assert classes[0].replacement == "catalog-service:CategoryResource"


def test_component_symbols_empty_for_unknown_or_other_step() -> None:
    nodes, edges = build_mock_graph()

    assert component_symbols(nodes, edges, "step-06", "nope") == []
    assert component_symbols(nodes, edges, "step-05", "monolith") == []  # no files at step-05
