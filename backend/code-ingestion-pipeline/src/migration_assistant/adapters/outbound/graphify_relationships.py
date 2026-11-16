"""Normalize Graphify into the canonical records.py fact contract."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.graph_schema.models import compute_entity_id, compute_file_id, normalize_path
from shared_contracts.records import (
    ExternalSymbolObservationFact,
    RelationshipFact,
    RelationshipType,
    SourceSpan,
    SymbolObservationFact,
    UnresolvedSymbolObservationFact,
)


class Observation(Protocol):
    observation_id: str
    snapshot_id: str
    repo_id: str | None
    path: str
    kind: str
    name: str
    qualified_name: str
    source_span: SourceSpan | None


class RelationshipIssue(BaseModel):
    """A raw edge that could not safely become a canonical relationship."""

    edge_id: str
    code: str
    detail: str
    raw_edge: dict[str, Any]


class RelationshipNormalizationResult(BaseModel):
    facts: list[RelationshipFact] = Field(default_factory=list)
    issues: list[RelationshipIssue] = Field(default_factory=list)

    def to_jsonl(self) -> str:
        return "\n".join(fact.to_jsonl() for fact in self.facts)

    def write_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        serialized = self.to_jsonl()
        target.write_text(serialized + ("\n" if serialized else ""), encoding="utf-8")


def write_jsonl_records(records: list[Any], path: str | Path) -> None:
    """Write validated records as JSONL, creating the parent folder."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(record.to_jsonl())
            output.write("\n")


def read_graphify(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError("Graphify graph must be a JSON object")
    return payload


class CanonicalEntityIndex:
    """Resolve Graphify nodes to canonical observation IDs without guessing."""

    def __init__(self, observations: list[Observation]) -> None:
        self._by_id: dict[str, Observation] = {}
        self._by_identity: dict[tuple[str | None, str, str, str], list[str]] = {}
        self._by_path_name: dict[tuple[str | None, str, str], list[str]] = {}
        for observation in observations:
            if observation.observation_id in self._by_id:
                raise ValueError(
                    f"Duplicate canonical observation ID: {observation.observation_id}"
                )
            self._by_id[observation.observation_id] = observation
            identity = (
                observation.repo_id,
                normalize_path(observation.path),
                observation.kind,
                observation.qualified_name,
            )
            self._by_identity.setdefault(identity, []).append(observation.observation_id)
            path_name = (observation.repo_id, normalize_path(observation.path), observation.name)
            self._by_path_name.setdefault(path_name, []).append(observation.observation_id)

    def resolve(self, node: dict[str, Any]) -> tuple[str | None, str | None]:
        observation_id = node.get("observationId", node.get("observation_id"))
        if observation_id is not None:
            if observation_id in self._by_id:
                return str(observation_id), None
            return None, f"Unknown canonical observation ID: {observation_id}"
        identity = (
            node.get("repoId", node.get("repo_id")),
            normalize_path(str(node.get("path", ""))),
            str(node.get("kind", "")),
            str(node.get("qualifiedName", node.get("qualified_name", ""))),
        )
        candidates = self._by_identity.get(identity, [])
        if not candidates:
            path_name = (identity[0], identity[1], str(node.get("name", "")))
            candidates = self._by_path_name.get(path_name, [])
        if len(candidates) == 1:
            return candidates[0], None
        if len(candidates) > 1:
            return None, f"Ambiguous canonical endpoint ({len(candidates)} matches)"
        return None, "No canonical observation matches Graphify node"


def normalize_graphify_facts(
    payload: dict[str, Any],
    *,
    snapshot_id: str,
    source_revisions: dict[str, str],
    source_line_counts: dict[tuple[str, str], int] | None = None,
    default_repo_id: str | None = None,
    extractor_version: str = "unknown",
) -> tuple[
    list[SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact],
    RelationshipNormalizationResult,
]:
    """Build canonical entity and relationship facts from one Graphify graph."""
    nodes = payload.get("nodes")
    edges = payload.get("links", payload.get("edges", []))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Graphify payload must contain list-valued nodes and links")
    graph_meta = payload.get("graph", {})
    if extractor_version == "unknown" and isinstance(graph_meta, dict):
        extractor_version = str(graph_meta.get("graphify_version", extractor_version))

    method_ids = _class_owned_callable_ids(nodes, edges)
    observations: list[_Observation] = []
    facts: list[
        SymbolObservationFact | ExternalSymbolObservationFact | UnresolvedSymbolObservationFact
    ] = []
    node_observation_ids: dict[str, str] = {}

    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("Every Graphify node must be an object with an id")
        raw_id = str(node["id"])
        kind = _node_kind(node, method_ids)
        repo_id, path = _source_reference(node)
        location = _graphify_span(
            node,
            source_revisions,
            source_line_counts=source_line_counts,
            default_repo_id=default_repo_id,
            kind=kind,
        )
        name = str(node.get("label") or node.get("name") or raw_id)
        qualified_name = str(node.get("qualifiedName") or node.get("qualified_name") or name)

        if _is_external_node(node):
            observation_id = _stable_id([snapshot_id, "ExternalSymbolObservation", raw_id])
            node_observation_ids[raw_id] = observation_id
            observations.append(
                _Observation(
                    observation_id, snapshot_id, None, "", "external", name, qualified_name, None
                )
            )
            facts.append(
                ExternalSymbolObservationFact(
                    record_id=_stable_id(
                        [snapshot_id, "ExternalSymbolObservation", observation_id]
                    ),
                    snapshot_id=snapshot_id,
                    observation_id=observation_id,
                    name=name,
                    qualified_name=qualified_name,
                    extractor_version=extractor_version,
                )
            )
            continue

        if location is None:
            repo_id = repo_id or default_repo_id
            observation_id = _stable_id(
                [
                    snapshot_id,
                    "UnresolvedSymbolObservation",
                    repo_id or "",
                    path or "",
                    kind,
                    qualified_name,
                ]
            )
            node_observation_ids[raw_id] = observation_id
            observations.append(
                _Observation(
                    observation_id,
                    snapshot_id,
                    repo_id,
                    path or "",
                    kind,
                    name,
                    qualified_name,
                    None,
                )
            )
            facts.append(
                UnresolvedSymbolObservationFact(
                    record_id=_stable_id(
                        [snapshot_id, "UnresolvedSymbolObservation", observation_id]
                    ),
                    snapshot_id=snapshot_id,
                    observation_id=observation_id,
                    kind=kind,
                    name=name,
                    qualified_name=qualified_name,
                    repo_id=repo_id,
                    source_file=path,
                    extractor_version=extractor_version,
                )
            )
            continue

        repo_id, span = location
        path = span.path
        qualified_name = str(
            node.get("qualifiedName") or node.get("qualified_name") or f"{path}::{name}::{raw_id}"
        )
        observation_id = (
            compute_file_id(snapshot_id, repo_id, path)
            if kind == "file"
            else compute_entity_id(
                snapshot_id,
                repo_id,
                path,
                kind,
                qualified_name,
                signature=str(node["signature"]) if node.get("signature") else None,
            )
        )
        node_observation_ids[raw_id] = observation_id
        observations.append(
            _Observation(
                observation_id, snapshot_id, repo_id, path, kind, name, qualified_name, span
            )
        )
        facts.append(
            SymbolObservationFact(
                record_id=_stable_id([snapshot_id, "SymbolObservation", observation_id]),
                snapshot_id=snapshot_id,
                observation_id=observation_id,
                kind=kind,
                name=name,
                qualified_name=qualified_name,
                repo_id=repo_id,
                source_span=span,
                extractor_version=extractor_version,
            )
        )

    index = CanonicalEntityIndex(observations)
    mapped_nodes = []
    for node in nodes:
        mapped = dict(node)
        if str(node.get("id", "")) in node_observation_ids:
            mapped["observationId"] = node_observation_ids[str(node["id"])]
        mapped_nodes.append(mapped)
    mapped_edges = []
    for position, edge in enumerate(edges):
        if not isinstance(edge, dict):
            mapped_edges.append(edge)
            continue
        mapped = dict(edge)
        mapped["__originalGraphifyEdge"] = dict(edge)
        mapped.setdefault("id", f"edge-{position}")
        if not _edge_has_span(mapped):
            edge_location = _graphify_span(
                mapped,
                source_revisions,
                default_repo_id=default_repo_id,
            )
            if edge_location:
                repo_id, span = edge_location
                lines = _line_range(mapped.get("source_location"))
                if lines:
                    mapped["sourceSpan"] = {
                        "repoId": repo_id,
                        "commitSha": span.commit_sha,
                        "path": span.path,
                        "startLine": lines[0],
                        "endLine": lines[1],
                    }
        mapped_edges.append(mapped)
    result = normalize_graphify(
        {**payload, "nodes": mapped_nodes, "edges": mapped_edges},
        index,
        snapshot_id=snapshot_id,
        extractor_version=extractor_version,
    )
    facts.sort(key=lambda fact: fact.record_id)
    return facts, result


class _Observation:
    def __init__(
        self, observation_id, snapshot_id, repo_id, path, kind, name, qualified_name, source_span
    ):
        self.observation_id = observation_id
        self.snapshot_id = snapshot_id
        self.repo_id = repo_id
        self.path = path
        self.kind = kind
        self.name = name
        self.qualified_name = qualified_name
        self.source_span = source_span


def _graphify_span(
    node: dict[str, Any],
    source_revisions: dict[str, str],
    *,
    source_line_counts: dict[tuple[str, str], int] | None = None,
    default_repo_id: str | None = None,
    kind: str | None = None,
) -> tuple[str, SourceSpan] | None:
    repo_id, path = _source_reference(node)
    repo_id = repo_id or default_repo_id
    if repo_id is None or path is None or repo_id not in source_revisions:
        return None
    lines = None
    if kind == "file":
        count = (source_line_counts or {}).get((repo_id, path))
        if count:
            lines = (1, count)
    if lines is None:
        lines = _line_range(node.get("source_location"))
    if lines is None:
        return None
    return repo_id, SourceSpan(
        repo_id=repo_id,
        commit_sha=source_revisions[repo_id],
        path=path,
        start_line=lines[0],
        end_line=lines[1],
    )


def _source_reference(node: dict[str, Any]) -> tuple[str | None, str | None]:
    raw_path = str(node.get("source_file", "")).replace("\\", "/").strip("/")
    repo_id, separator, path = raw_path.partition("/")
    if separator:
        return repo_id, normalize_path(path)
    repo_id = node.get("repoId", node.get("repo_id"))
    path = node.get("path")
    if repo_id and path:
        return str(repo_id), normalize_path(str(path))
    return None, None


def _line_range(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    try:
        parts = str(value).removeprefix("L").split("-", 1)
        start = int(parts[0])
        end = int(parts[1].removeprefix("L")) if len(parts) > 1 else start
        return (start, end) if start > 0 and end >= start else None
    except ValueError:
        return None


def _node_kind(node: dict[str, Any], method_node_ids: set[str] | None = None) -> str:
    method_node_ids = method_node_ids or set()
    node_id = str(node.get("id", ""))
    node_type = str(node.get("type", "")).casefold()
    if node_type in {"file", "module"} or node.get("_file"):
        return "file"
    if node.get("_callable_class"):
        return "class"
    if node_type in {"class", "method", "interface", "enum", "field", "file", "module"}:
        return node_type
    if node_type in {"function", "procedure", "callable"}:
        return "method" if node_id in method_node_ids else "function"
    if node.get("_callable"):
        return "method" if node_id in method_node_ids else "function"
    return node_type if node_type and node_type != "symbol" else "symbol"


def _class_owned_callable_ids(nodes: list[Any], edges: list[Any]) -> set[str]:
    callable_ids = {
        str(node["id"])
        for node in nodes
        if isinstance(node, dict) and node.get("id") and node.get("_callable")
    }
    class_ids = {
        str(node["id"])
        for node in nodes
        if isinstance(node, dict)
        and node.get("id")
        and (node.get("_callable_class") or str(node.get("type", "")).casefold() == "class")
    }
    return {
        str(edge.get("target", edge.get("to", "")))
        for edge in edges
        if isinstance(edge, dict)
        and str(edge.get("relation", edge.get("type", ""))).casefold()
        in {"contains", "method", "declares_member"}
        and str(edge.get("source", edge.get("from", ""))) in class_ids
        and str(edge.get("target", edge.get("to", ""))) in callable_ids
    }


def _is_external_node(node: dict[str, Any]) -> bool:
    return bool(node.get("external")) or str(node.get("type", "")).casefold() in {
        "external",
        "library",
        "external_symbol",
    }


_TYPE_MAP = {value.value.casefold(): value for value in RelationshipType}
_TYPE_MAP.update(
    {
        "call": RelationshipType.CALLS,
        "callable": RelationshipType.CALLS,
        "inherits": RelationshipType.EXTENDS,
        "inheritance": RelationshipType.EXTENDS,
        "method": RelationshipType.DECLARES_MEMBER,
        "reference": RelationshipType.REFERENCES,
        "import": RelationshipType.IMPORTS,
        "implements": RelationshipType.IMPLEMENTS,
    }
)


def normalize_graphify(
    payload: dict[str, Any],
    entities: CanonicalEntityIndex,
    *,
    snapshot_id: str,
    extractor_version: str = "unknown",
    endpoint_observation_ids: dict[str, str] | None = None,
) -> RelationshipNormalizationResult:
    """Normalize relationship records while retaining raw Graphify provenance."""
    if not snapshot_id:
        raise ValueError("snapshot_id is required for relationship facts")
    nodes = payload.get("nodes")
    edges = payload.get("edges", payload.get("links"))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Graphify payload must contain list-valued nodes and edges")
    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("Every Graphify node must be an object with an id")
        node_id = str(node["id"])
        if node_id in node_by_id:
            raise ValueError(f"Duplicate Graphify node ID: {node_id}")
        node_by_id[node_id] = node

    issues: list[RelationshipIssue] = []
    facts: list[RelationshipFact] = []
    seen: set[str] = set()
    for position, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"Graphify edge at index {position} is not an object")
        edge_id = str(edge.get("id", f"edge-{position}"))
        original_edge = edge.get("__originalGraphifyEdge")
        if not isinstance(original_edge, dict):
            original_edge = edge
        raw_type = str(edge.get("type", edge.get("relation", edge.get("label", "")))).strip()
        source_key = str(edge.get("source", edge.get("from", "")))
        target_key = str(edge.get("target", edge.get("to", "")))
        if not raw_type:
            issues.append(
                _issue(
                    edge_id,
                    "unsupported_type",
                    "Graphify edge has no relationship type",
                    original_edge,
                )
            )
            continue
        relation = _relationship_type(
            raw_type, node_by_id.get(source_key), node_by_id.get(target_key)
        )
        source_id, source_error = _resolve_endpoint(
            source_key, node_by_id, entities, endpoint_observation_ids
        )
        target_id, target_error = _resolve_endpoint(
            target_key, node_by_id, entities, endpoint_observation_ids
        )
        if source_error:
            issues.append(_issue(edge_id, "unresolved_source", source_error, original_edge))
        if target_error:
            issues.append(_issue(edge_id, "unresolved_target", target_error, original_edge))
        if source_id is None or target_id is None:
            continue

        evidence = _evidence(edge)
        if evidence is None:
            issues.append(
                _issue(
                    edge_id,
                    "missing_evidence",
                    "Graphify edge has no usable source path and line evidence",
                    original_edge,
                )
            )
        evidence_id = _evidence_id(evidence) if evidence else None
        relation_value = relation.value if isinstance(relation, RelationshipType) else relation
        record_id = _record_id(
            snapshot_id,
            relation_value,
            source_id,
            target_id,
            evidence_id,
            edge_id if evidence_id is None else None,
        )
        if record_id in seen:
            continue
        seen.add(record_id)
        facts.append(
            RelationshipFact(
                record_id=record_id,
                snapshot_id=snapshot_id,
                relationship_type=relation,
                source_observation_id=source_id,
                target_observation_id=target_id,
                evidence_ids=[evidence_id] if evidence_id else [],
                source_span=evidence,
                source_edge_id=edge_id,
                original_relationship_type=raw_type,
                original_edge=dict(original_edge),
                extractor_version=extractor_version,
            )
        )
    facts.sort(key=lambda fact: fact.record_id)
    return RelationshipNormalizationResult(facts=facts, issues=issues)


def normalize_graphify_file(
    graph_path: str | Path,
    entities: CanonicalEntityIndex,
    *,
    snapshot_id: str,
    extractor_version: str = "unknown",
    endpoint_observation_ids: dict[str, str] | None = None,
) -> RelationshipNormalizationResult:
    return normalize_graphify(
        read_graphify(graph_path),
        entities,
        snapshot_id=snapshot_id,
        extractor_version=extractor_version,
        endpoint_observation_ids=endpoint_observation_ids,
    )


def _resolve_endpoint(key, nodes, entities, explicit):
    if explicit and key in explicit:
        return entities.resolve({"observationId": explicit[key]})
    node = nodes.get(key)
    return (None, f"Unknown Graphify node ID: {key}") if node is None else entities.resolve(node)


def _relationship_type(raw_type, source_node, target_node):
    normalized = raw_type.casefold()
    if normalized == "contains":
        source_kind = _node_kind(source_node or {})
        target_kind = _node_kind(target_node or {})
        if source_kind in {"file", "module"} and target_kind in {
            "class",
            "interface",
            "function",
            "method",
        }:
            return RelationshipType.DECLARES
        if source_kind in {"class", "interface"} and target_kind in {"method", "function", "field"}:
            return RelationshipType.DECLARES_MEMBER
        if source_kind in {"class", "interface"} and target_kind in {"class", "interface"}:
            return RelationshipType.CONTAINS_TYPE
        if source_kind == target_kind == "file":
            return RelationshipType.HAS_FILE
        return raw_type
    return _TYPE_MAP.get(normalized, raw_type)


def _evidence(edge):
    raw = edge.get("sourceSpan", edge.get("source_span", edge.get("evidence")))
    if not isinstance(raw, dict) and edge.get("source_file"):
        repo_id, separator, path = (
            str(edge["source_file"]).replace("\\", "/").strip("/").partition("/")
        )
        lines = _line_range(edge.get("source_location"))
        # sourceSpan is attached by normalize_graphify_facts when commit data is known.
        if separator and lines:
            return None
    if not isinstance(raw, dict):
        return None
    repo_id = raw.get("repoId", raw.get("repo_id"))
    commit_sha = raw.get("commitSha", raw.get("commit_sha"))
    path = raw.get("path")
    start = raw.get("startLine", raw.get("start_line", raw.get("line")))
    end = raw.get("endLine", raw.get("end_line", start))
    if not all((repo_id, commit_sha, path, start)):
        return None
    try:
        return SourceSpan(
            repo_id=str(repo_id),
            path=normalize_path(str(path)),
            commit_sha=str(commit_sha),
            start_line=int(start),
            end_line=int(end),
        )
    except (TypeError, ValueError):
        return None


def _edge_has_span(edge):
    return isinstance(edge.get("sourceSpan", edge.get("source_span", edge.get("evidence"))), dict)


def _issue(edge_id, code, detail, raw_edge):
    return RelationshipIssue(edge_id=edge_id, code=code, detail=detail, raw_edge=dict(raw_edge))


def _record_id(snapshot_id, relation, source, target, evidence_id, source_edge_id=None):
    identity = [snapshot_id, relation, source, target, evidence_id]
    if source_edge_id is not None:
        identity.append(source_edge_id)
    encoded = json.dumps(identity, separators=(",", ":"), ensure_ascii=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _evidence_id(span):
    locator = _evidence_locator(span)
    return "git:" + sha256(locator.encode("utf-8")).hexdigest()


def _evidence_locator(span):
    return f"git:{span.repo_id}@{span.commit_sha}:{span.path}#L{span.start_line}-L{span.end_line}"


def _stable_id(parts):
    return sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
