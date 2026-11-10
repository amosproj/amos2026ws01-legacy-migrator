"""Normalize Graphify edges into canonical relationship fact records."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class Observation(Protocol):
    observation_id: str
    snapshot_id: str
    repo_id: str
    path: str
    kind: str
    name: str
    qualified_name: str
    source_span: Any


class RelationshipEvidence(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)

    repo_id: str
    commit_sha: str
    path: str
    start_line: int = Field(gt=0)
    end_line: int = Field(gt=0)


class RelationshipFact(BaseModel):
    """Canonical JSONL relationship record consumed by the graph component."""

    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)

    schema_version: str = "1.0.0"
    record_type: str = "Relationship"
    record_id: str
    snapshot_id: str
    relationship_type: str
    source_observation_id: str
    target_observation_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    source_span: RelationshipEvidence | None = None
    extractor_name: str = "graphify"
    extractor_version: str = "unknown"

    def to_record_dict(self) -> dict[str, Any]:
        payload = {
            "relationshipType": self.relationship_type,
            "sourceObservationId": self.source_observation_id,
            "targetObservationId": self.target_observation_id,
            "evidenceIds": list(self.evidence_ids),
            "sourceSpan": self.source_span.model_dump(by_alias=True) if self.source_span else None,
            "extractor": {
                "name": self.extractor_name,
                "version": self.extractor_version,
            },
        }
        return {
            "schemaVersion": self.schema_version,
            "recordType": self.record_type,
            "recordId": self.record_id,
            "snapshotId": self.snapshot_id,
            "payload": payload,
            "evidenceReferences": [
                _evidence_locator(self.source_span)
            ] if self.source_span else [],
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_record_dict(), ensure_ascii=False, separators=(",", ":"))


class SymbolObservationFact(BaseModel):
    """Canonical symbol record emitted alongside relationships for graph loading."""

    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)

    schema_version: str = "1.0.0"
    record_type: str = "SymbolObservation"
    record_id: str
    snapshot_id: str
    observation_id: str
    kind: str
    name: str
    qualified_name: str
    repo_id: str
    source_span: RelationshipEvidence
    extractor_name: str = "graphify"
    extractor_version: str = "unknown"

    def to_record_dict(self) -> dict[str, Any]:
        span = self.source_span.model_dump(by_alias=True)
        return {
            "schemaVersion": self.schema_version,
            "recordType": self.record_type,
            "recordId": self.record_id,
            "snapshotId": self.snapshot_id,
            "payload": {
                "observationId": self.observation_id,
                "kind": self.kind,
                "name": self.name,
                "qualifiedName": self.qualified_name,
                "repoId": self.repo_id,
                "sourceSpan": span,
                "extractor": {"name": self.extractor_name, "version": self.extractor_version},
            },
            "evidenceReferences": [_evidence_locator(self.source_span)],
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_record_dict(), ensure_ascii=False, separators=(",", ":"))


class RelationshipIssue(BaseModel):
    """A raw edge that could not safely become a canonical relationship."""

    edge_id: str
    code: str
    detail: str


class RelationshipNormalizationResult(BaseModel):
    facts: list[RelationshipFact] = Field(default_factory=list)
    issues: list[RelationshipIssue] = Field(default_factory=list)

    def to_jsonl(self) -> str:
        return "\n".join(fact.to_jsonl() for fact in self.facts)

    def write_jsonl(self, path: str | Path) -> None:
        """Publish validated facts for a graph loader or fact store."""
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            serialized = self.to_jsonl()
            if serialized:
                output.write(serialized)
                output.write("\n")


def write_jsonl_records(records: list[Any], path: str | Path) -> None:
    """Write any canonical fact records as JSONL, creating the parent folder."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(record.to_jsonl())
            output.write("\n")


def read_graphify(path: str | Path) -> dict[str, Any]:
    """Read one Graphify JSON graph without coupling callers to its file format."""
    with open(path, encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError("Graphify graph must be a JSON object")
    return payload


class CanonicalEntityIndex:
    """Resolve Graphify nodes to issue #19 observation IDs without guessing."""

    def __init__(self, observations: list[Observation]) -> None:
        self._by_id = {}
        self._by_identity: dict[tuple[str, str, str, str], list[str]] = {}
        self._by_path_name: dict[tuple[str, str, str], list[str]] = {}
        for observation in observations:
            if observation.observation_id in self._by_id:
                raise ValueError(
                    f"Duplicate canonical observation ID: {observation.observation_id}"
                )
            self._by_id[observation.observation_id] = observation
            identity = (
                observation.repo_id,
                _path(observation.path),
                observation.kind,
                observation.qualified_name,
            )
            self._by_identity.setdefault(identity, []).append(observation.observation_id)
            path_name = (observation.repo_id, _path(observation.path), observation.name)
            self._by_path_name.setdefault(path_name, []).append(observation.observation_id)

    def resolve(self, node: dict[str, Any]) -> tuple[str | None, str | None]:
        observation_id = node.get("observationId", node.get("observation_id"))
        if observation_id is not None:
            if observation_id in self._by_id:
                return observation_id, None
            return None, f"Unknown canonical observation ID: {observation_id}"

        identity = (
            str(node.get("repoId", node.get("repo_id", ""))),
            _path(str(node.get("path", ""))),
            str(node.get("kind", "")),
            str(node.get("qualifiedName", node.get("qualified_name", ""))),
        )
        candidates = self._by_identity.get(identity, [])
        if not candidates:
            path_name = (
                identity[0],
                identity[1],
                str(node.get("name", "")),
            )
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
    extractor_version: str = "unknown",
) -> tuple[list[SymbolObservationFact], RelationshipNormalizationResult]:
    """Build snapshot-scoped entity records and relationships from Graphify's graph.

    Graphify's current schema uses ``links`` and node IDs that are not canonical
    entity IDs. This seam resolves source nodes to deterministic observation IDs,
    emits those entities, and only publishes links whose two endpoints resolved.
    """
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Graphify payload must contain list-valued nodes and links")
    graph_metadata = payload.get("graph", {})
    if extractor_version == "unknown" and isinstance(graph_metadata, dict):
        extractor_version = str(graph_metadata.get("graphify_version", extractor_version))

    observations: list[Any] = []
    entity_facts: list[SymbolObservationFact] = []
    node_to_observation: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("Every Graphify node must be an object with an id")
        location = _graphify_span(node, source_revisions)
        if location is None:
            continue
        repo_id, span = location
        node_id = str(node["id"])
        kind = _node_kind(node)
        name = str(node.get("label") or node.get("name") or node_id)
        qualified_name = f"{span.path}::{name}::{node_id}"
        observation_id = _stable_id([snapshot_id, repo_id, span.path, kind, qualified_name])
        node_to_observation[node_id] = observation_id
        observations.append(_Observation(
            observation_id=observation_id,
            snapshot_id=snapshot_id,
            repo_id=repo_id,
            path=span.path,
            kind=kind,
            name=name,
            qualified_name=qualified_name,
            source_span=span,
        ))
        entity_facts.append(SymbolObservationFact(
            record_id=_stable_id([snapshot_id, "SymbolObservation", observation_id]),
            snapshot_id=snapshot_id,
            observation_id=observation_id,
            kind=kind,
            name=name,
            qualified_name=qualified_name,
            repo_id=repo_id,
            source_span=span,
            extractor_version=extractor_version,
        ))

    index = CanonicalEntityIndex(observations)
    # Graphify names its endpoint list `links`; preserve the input and attach the
    # canonical IDs computed above so resolution is exact, not label-based.
    graph_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        mapped = dict(node)
        if str(node.get("id", "")) in node_to_observation:
            mapped["observationId"] = node_to_observation[str(node["id"])]
        graph_nodes.append(mapped)
    raw_edges = payload.get("links", payload.get("edges", []))
    edges = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            edges.append(edge)
            continue
        mapped = dict(edge)
        evidence_location = _graphify_span(edge, source_revisions)
        if evidence_location is not None and "sourceSpan" not in mapped and "source_span" not in mapped:
            repo_id, span = evidence_location
            line_start, line_end = _line_range(edge.get("source_location"))
            mapped["sourceSpan"] = {
                "repoId": repo_id,
                "commitSha": span.commit_sha,
                "path": span.path,
                "startLine": line_start,
                "endLine": line_end,
            }
        edges.append(mapped)
    normalized = normalize_graphify(
        {**payload, "nodes": graph_nodes, "edges": edges},
        index,
        snapshot_id=snapshot_id,
        extractor_version=extractor_version,
    )
    entity_facts.sort(key=lambda fact: fact.record_id)
    return entity_facts, normalized


class _Observation:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)


def _graphify_span(
    node: dict[str, Any], source_revisions: dict[str, str]
) -> tuple[str, RelationshipEvidence] | None:
    raw_path = str(node.get("source_file", "")).replace("\\", "/").strip("/")
    repo_id, separator, path = raw_path.partition("/")
    if not separator or repo_id not in source_revisions:
        return None
    start_line, end_line = _line_range(node.get("source_location"))
    return repo_id, RelationshipEvidence(
        repo_id=repo_id,
        commit_sha=source_revisions[repo_id],
        path=path,
        start_line=start_line,
        end_line=end_line,
    )


def _line_range(value: Any) -> tuple[int, int]:
    text = str(value or "L1").removeprefix("L")
    try:
        parts = text.split("-", 1)
        start = int(parts[0])
        end = int(parts[1].removeprefix("L")) if len(parts) > 1 else start
        if start > 0 and end >= start:
            return start, end
    except ValueError:
        pass
    return 1, 1


def _node_kind(node: dict[str, Any]) -> str:
    node_type = str(node.get("type", "")).casefold()
    if node_type in {"class", "method", "function", "field", "interface", "enum"}:
        return "method" if node_type == "function" else node_type
    if node.get("_callable_class"):
        return "class"
    if node.get("_callable"):
        return "method"
    return "symbol"


def _stable_id(value: list[str]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


_TYPE_MAP = {
    "call": "CALLS",
    "calls": "CALLS",
    "callable": "CALLS",
    "extends": "INHERITS",
    "inherits": "INHERITS",
    "inheritance": "INHERITS",
    "reference": "REFERENCES",
    "references": "REFERENCES",
    "import": "REFERENCES",
    "imports": "REFERENCES",
    "implements": "INHERITS",
    "depends_on": "REFERENCES",
}


def normalize_graphify(
    payload: dict[str, Any],
    entities: CanonicalEntityIndex,
    *,
    snapshot_id: str,
    extractor_version: str = "unknown",
    endpoint_observation_ids: dict[str, str] | None = None,
) -> RelationshipNormalizationResult:
    """Convert Graphify's structured graph output into validated canonical facts."""
    if not snapshot_id:
        raise ValueError("snapshot_id is required for relationship facts")
    nodes = payload.get("nodes")
    edges = payload.get("edges", payload.get("links"))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Graphify payload must contain list-valued nodes and edges")

    node_by_id: dict[str, dict[str, Any]] = {}
    issues: list[RelationshipIssue] = []
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("Every Graphify node must be an object with an id")
        node_id = str(node["id"])
        if node_id in node_by_id:
            raise ValueError(f"Duplicate Graphify node ID: {node_id}")
        node_by_id[node_id] = node

    facts: list[RelationshipFact] = []
    seen_ids: set[str] = set()
    for position, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"Graphify edge at index {position} is not an object")
        edge_id = str(edge.get("id", f"edge-{position}"))
        raw_type = str(edge.get("type", edge.get("relation", edge.get("label", "")))).casefold()
        relationship_type = _TYPE_MAP.get(raw_type)
        if relationship_type is None:
            issues.append(RelationshipIssue(
                edge_id=edge_id,
                code="unsupported_type",
                detail=f"Unsupported Graphify relationship type: {raw_type}",
            ))
            continue
        source_key = str(edge.get("source", edge.get("from", "")))
        target_key = str(edge.get("target", edge.get("to", "")))
        source_id, source_error = _resolve_endpoint(source_key, node_by_id, entities,
                                                     endpoint_observation_ids)
        target_id, target_error = _resolve_endpoint(target_key, node_by_id, entities,
                                                     endpoint_observation_ids)
        if source_error:
            issues.append(RelationshipIssue(edge_id=edge_id, code="unresolved_source",
                                            detail=source_error))
        if target_error:
            issues.append(RelationshipIssue(edge_id=edge_id, code="unresolved_target",
                                            detail=target_error))
        if source_id is None or target_id is None:
            continue

        evidence = _evidence(edge)
        if evidence is None:
            issues.append(RelationshipIssue(
                edge_id=edge_id,
                code="missing_evidence",
                detail="Graphify edge has no usable source path and line evidence",
            ))
            continue
        evidence_id = _evidence_id(evidence)
        record_id = _record_id(snapshot_id, relationship_type, source_id, target_id,
                               evidence_id)
        if record_id in seen_ids:
            continue
        seen_ids.add(record_id)
        facts.append(RelationshipFact(
            record_id=record_id,
            snapshot_id=snapshot_id,
            relationship_type=relationship_type,
            source_observation_id=source_id,
            target_observation_id=target_id,
            evidence_ids=[evidence_id] if evidence_id else [],
            source_span=evidence,
            extractor_version=extractor_version,
        ))

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
    """Read Graphify's output and normalize it for the canonical fact writer."""
    return normalize_graphify(
        read_graphify(graph_path),
        entities,
        snapshot_id=snapshot_id,
        extractor_version=extractor_version,
        endpoint_observation_ids=endpoint_observation_ids,
    )


def _resolve_endpoint(
    key: str,
    nodes: dict[str, dict[str, Any]],
    entities: CanonicalEntityIndex,
    explicit: dict[str, str] | None,
) -> tuple[str | None, str | None]:
    if explicit and key in explicit:
        try:
            resolved, error = entities.resolve({"observationId": explicit[key]})
        except ValueError as error:
            return None, str(error)
        return resolved, error
    node = nodes.get(key)
    if node is None:
        return None, f"Unknown Graphify node ID: {key}"
    return entities.resolve(node)


def _evidence(edge: dict[str, Any]) -> RelationshipEvidence | None:
    raw = edge.get("sourceSpan", edge.get("source_span", edge.get("evidence")))
    if not isinstance(raw, dict) and edge.get("source_file"):
        # Graphify stores repository-relative paths as <repoId>/<path>.
        raw_path = str(edge["source_file"]).replace("\\", "/").strip("/")
        repo_id, separator, path = raw_path.partition("/")
        location = str(edge.get("source_location", ""))
        line_text = location.removeprefix("L").split("-", 1)[0]
        if separator and line_text.isdigit():
            raw = {
                "repoId": repo_id,
                "path": path,
                "startLine": int(line_text),
                "endLine": int(line_text),
            }
    if not isinstance(raw, dict):
        return None
    path = raw.get("path")
    line = raw.get("startLine", raw.get("line"))
    if not path or not line:
        return None
    return RelationshipEvidence(
        repo_id=str(raw.get("repoId", raw.get("repo_id", ""))),
        commit_sha=str(raw.get("commitSha", raw.get("commit_sha", ""))),
        path=str(path),
        start_line=int(line),
        end_line=int(raw.get("endLine", raw.get("end_line", line))),
    )


def _record_id(snapshot_id: str, relationship_type: str, source: str, target: str,
               evidence_id: str | None) -> str:
    value = json.dumps(
        [snapshot_id, relationship_type, source, target, evidence_id],
        separators=(",", ":"), ensure_ascii=False,
    )
    return sha256(value.encode("utf-8")).hexdigest()


def _evidence_id(evidence: RelationshipEvidence) -> str:
    value = json.dumps(
        evidence.model_dump(by_alias=True, exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"git:{sha256(value.encode('utf-8')).hexdigest()}"


def _evidence_locator(evidence: RelationshipEvidence) -> str:
    return (
        f"git:{evidence.repo_id}@{evidence.commit_sha}:{evidence.path}"
        f"#L{evidence.start_line}-L{evidence.end_line}"
    )


def _path(value: str) -> str:
    return value.replace("\\", "/").strip("/")
