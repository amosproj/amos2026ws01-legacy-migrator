"""Compare two persisted ingestion runs, for example ``step-05`` against ``step-06``.

Every run folder must contain ``snapshot-identity.json``, ``sources.jsonl``,
``entities.jsonl`` and ``relationships.jsonl``. All components, files, symbols
and relationships are discovered from that data; nothing is specific to a stage.

Matching keys:

* component: ``repoId`` from ``snapshot-identity.json`` ``sourceMembers``
* file: ``(repoId, path)``; modified when ``contentSha256`` differs
* symbol: ``(repoId, qualifiedName)``; external symbols have no ``repoId`` and
  use ``(None, qualifiedName)``. Unresolved symbols can repeat a key (for example
  several ``Override`` annotations); they carry no other stable field, so the
  repeats are merged into one symbol that keeps all observation IDs.
* relationship: ``(relationshipType, sourceKey, targetKey)``, compared as a
  multiset because one file can declare the same edge several times.

Moves, inside one component, among the files only in one stage:

1. same ``contentSha256`` (unique on both sides) -> ``moved``; its symbols are
   paired by ``(kind, name, startLine)``.
2. then same file name (basename, unique among the remaining removed and added
   files) -> ``moved_modified``; its symbols are paired by ``(kind, name)``.

Paired symbols get the file's status; unpaired ones stay added / removed.
Relationship endpoints are renamed to their paired keys before comparing, so a
relationship that only moved counts as unchanged.

Every changed file gets a ``FileCategory`` from ``CATEGORY_RULES``.

A run with missing or inconsistent data yields ``state="insufficient_data"``
with the problems listed instead of a partial answer.

Usage::

    uv run python -m app.stage_compare <earlier_run_dir> <later_run_dir> [--md out.md]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from shared_contracts.records import (
    ExternalSymbolObservationRecord,
    RelationshipRecord,
    SnapshotIdentity,
    SymbolObservationRecord,
    UnresolvedSymbolObservationRecord,
)

SNAPSHOT_IDENTITY_FILE = "snapshot-identity.json"
SOURCES_FILE = "sources.jsonl"
ENTITIES_FILE = "entities.jsonl"
RELATIONSHIPS_FILE = "relationships.jsonl"
REQUIRED_FILES = (SNAPSHOT_IDENTITY_FILE, SOURCES_FILE, ENTITIES_FILE, RELATIONSHIPS_FILE)

type SymbolKey = tuple[str | None, str]
type RelationshipKey = tuple[str, SymbolKey, SymbolKey]
type EntityRecord = (
    SymbolObservationRecord | ExternalSymbolObservationRecord | UnresolvedSymbolObservationRecord
)

ENTITY_RECORD_TYPES: dict[str, type[EntityRecord]] = {
    "SymbolObservation": SymbolObservationRecord,
    "ExternalSymbolObservation": ExternalSymbolObservationRecord,
    "UnresolvedSymbolObservation": UnresolvedSymbolObservationRecord,
}


class StageDataError(Exception):
    """A run folder is missing data or its files contradict each other."""

    def __init__(self, run_dir: Path, problems: list[str]) -> None:
        super().__init__(f"{run_dir}: " + "; ".join(problems))
        self.run_dir = run_dir
        self.problems = problems


class ChangeStatus(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    MOVED_MODIFIED = "moved_modified"
    UNCHANGED = "unchanged"


class FileCategory(StrEnum):
    DEPLOYMENT = "deployment"
    DB_ACCESS = "db_access"
    CONFIG = "config"
    CODE = "code"


# First matching rule wins; anything unmatched is ``code``. Patterns are matched
# case-insensitively against the repository-relative path.
CATEGORY_RULES: tuple[tuple[FileCategory, str], ...] = (
    (FileCategory.DEPLOYMENT, r"(^|/)dockerfile[^/]*$"),
    (FileCategory.DEPLOYMENT, r"(^|/)docker-compose[^/]*\.ya?ml$"),
    (FileCategory.DEPLOYMENT, r"(^|/)nginx[^/]*\.conf$"),
    (FileCategory.DEPLOYMENT, r"(^|/)[^/]*(deploy|ocp)[^/]*/.*\.ya?ml$"),
    (FileCategory.DB_ACCESS, r"\.sql$"),
    (FileCategory.DB_ACCESS, r"(^|/)(persistence|orm)\.xml$"),
    (FileCategory.DB_ACCESS, r"repository|dao"),
    (FileCategory.CONFIG, r"\.(xml|properties|ya?ml|conf)$"),
)
_COMPILED_CATEGORY_RULES = tuple(
    (category, re.compile(pattern, re.IGNORECASE)) for category, pattern in CATEGORY_RULES
)


def categorize_file(path: str) -> FileCategory:
    """Return the change category of one repository-relative file path."""
    for category, pattern in _COMPILED_CATEGORY_RULES:
        if pattern.search(path):
            return category
    return FileCategory.CODE


class _CompareModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SymbolRef(_CompareModel):
    repo_id: str | None
    qualified_name: str = Field(min_length=1)


class ChangeCounts(_CompareModel):
    added: int = 0
    removed: int = 0
    modified: int = 0
    moved: int = 0
    moved_modified: int = 0
    unchanged: int = 0

    def add(self, status: ChangeStatus) -> None:
        setattr(self, status.value, getattr(self, status.value) + 1)

    @property
    def changed(self) -> int:
        return self.added + self.removed + self.modified + self.moved + self.moved_modified


class FileChange(_CompareModel):
    repo_id: str
    path: str
    previous_path: str | None = None
    status: ChangeStatus
    category: FileCategory
    earlier_content_sha256: str | None = None
    later_content_sha256: str | None = None
    earlier_evidence: str | None = None
    later_evidence: str | None = None


class SymbolChange(_CompareModel):
    repo_id: str | None
    qualified_name: str
    previous_qualified_name: str | None = None
    record_type: str
    kind: str
    path: str | None
    previous_path: str | None = None
    status: ChangeStatus
    earlier_observation_ids: list[str] = Field(default_factory=list)
    later_observation_ids: list[str] = Field(default_factory=list)
    earlier_evidence: list[str] = Field(default_factory=list)
    later_evidence: list[str] = Field(default_factory=list)


class RelationshipChange(_CompareModel):
    relationship_type: str
    source: SymbolRef
    target: SymbolRef
    status: Literal[ChangeStatus.ADDED, ChangeStatus.REMOVED]
    earlier_count: int = Field(ge=0)
    later_count: int = Field(ge=0)
    earlier_evidence: list[str] = Field(default_factory=list)
    later_evidence: list[str] = Field(default_factory=list)


class ComponentSummary(_CompareModel):
    repo_id: str
    status: ChangeStatus
    earlier_commit_sha: str | None
    later_commit_sha: str | None
    files: ChangeCounts = Field(default_factory=ChangeCounts)
    symbols: ChangeCounts = Field(default_factory=ChangeCounts)
    relationships: ChangeCounts = Field(default_factory=ChangeCounts)
    changed_files_by_category: dict[FileCategory, ChangeCounts] = Field(default_factory=dict)


class StageRef(_CompareModel):
    run_dir: str
    stage: str | None = None
    snapshot_id: str | None = None


class StageComparison(_CompareModel):
    """Typed result of comparing an earlier run against a later one.

    The change lists hold only added, removed and modified items; unchanged
    items appear as counts in the component summaries.
    """

    state: Literal["ready", "insufficient_data"]
    earlier: StageRef
    later: StageRef
    problems: list[str] = Field(default_factory=list)
    components: list[ComponentSummary] = Field(default_factory=list)
    unattributed_symbols: ChangeCounts = Field(default_factory=ChangeCounts)
    unattributed_relationships: ChangeCounts = Field(default_factory=ChangeCounts)
    files: list[FileChange] = Field(default_factory=list)
    symbols: list[SymbolChange] = Field(default_factory=list)
    relationships: list[RelationshipChange] = Field(default_factory=list)
    earlier_unmapped_relationships: int = 0
    later_unmapped_relationships: int = 0


@dataclass(frozen=True)
class SourceInfo:
    """The parts of one ``sources.jsonl`` row needed for comparison (no content)."""

    commit_sha: str
    content_sha256: str

    def evidence(self, repo_id: str, path: str) -> str:
        return f"git:{repo_id}@{self.commit_sha}:{path}"


@dataclass
class SymbolInfo:
    record_type: str
    kind: str
    name: str
    path: str | None
    start_line: int | None
    observation_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class StageData:
    run_dir: Path
    stage: str | None
    snapshot_id: str
    members: dict[str, str]
    files: dict[tuple[str, str], SourceInfo]
    symbols: dict[SymbolKey, SymbolInfo]
    relationships: Counter[RelationshipKey]
    relationship_evidence: dict[RelationshipKey, list[str]]
    unmapped_relationships: int


def _jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                yield line_number, json.loads(line)


def _load_files(
    path: Path, members: dict[str, str], problems: list[str]
) -> tuple[dict[tuple[str, str], SourceInfo], str | None]:
    files: dict[tuple[str, str], SourceInfo] = {}
    stages: set[str] = set()
    for line_number, raw in _jsonl(path):
        raw.pop("content", None)  # file bodies are not needed; drop them right away
        try:
            repo_id, file_path = raw["repoId"], raw["path"]
            info = SourceInfo(commit_sha=raw["commitSha"], content_sha256=raw["contentSha256"])
        except KeyError as error:
            problems.append(f"{path.name}:{line_number} is missing field {error}")
            continue
        if repo_id not in members:
            problems.append(f"{path.name}:{line_number} names unknown component {repo_id}")
        elif members[repo_id] != info.commit_sha:
            problems.append(
                f"{path.name}:{line_number} {repo_id} commit {info.commit_sha} does not match "
                f"{SNAPSHOT_IDENTITY_FILE} commit {members[repo_id]}"
            )
        if (repo_id, file_path) in files:
            problems.append(f"{path.name}:{line_number} repeats file {repo_id}:{file_path}")
        files[(repo_id, file_path)] = info
        if stage := raw.get("stage"):
            stages.add(stage)
    for repo_id in sorted(set(members) - {repo_id for repo_id, _ in files}):
        problems.append(f"{SOURCES_FILE} has no files for component {repo_id}")
    if len(stages) > 1:
        problems.append(f"{SOURCES_FILE} mixes stages {sorted(stages)}")
    return files, next(iter(stages)) if len(stages) == 1 else None


def _load_symbols(
    path: Path,
    members: dict[str, str],
    files: dict[tuple[str, str], SourceInfo],
    problems: list[str],
) -> tuple[dict[SymbolKey, SymbolInfo], dict[str, SymbolKey]]:
    symbols: dict[SymbolKey, SymbolInfo] = {}
    keys_by_observation: dict[str, SymbolKey] = {}
    for line_number, raw in _jsonl(path):
        model = ENTITY_RECORD_TYPES.get(raw.get("recordType", ""))
        if model is None:
            continue
        try:
            record = model.model_validate(raw)
        except ValidationError as error:
            problems.append(f"{path.name}:{line_number} is not a valid {model.__name__}: {error}")
            continue
        payload = record.payload
        start_line: int | None = None
        if isinstance(record, SymbolObservationRecord):
            repo_id, file_path = record.payload.repo_id, record.payload.source_span.path
            start_line = record.payload.source_span.start_line
            if (repo_id, file_path) not in files:
                problems.append(
                    f"{path.name}:{line_number} symbol file {repo_id}:{file_path} "
                    f"is not in {SOURCES_FILE}"
                )
        elif isinstance(record, UnresolvedSymbolObservationRecord):
            repo_id, file_path = record.payload.repo_id, record.payload.source_file
        else:
            repo_id, file_path = None, None
        if repo_id is not None and repo_id not in members:
            problems.append(f"{path.name}:{line_number} names unknown component {repo_id}")
        key: SymbolKey = (repo_id, payload.qualified_name)
        info = symbols.get(key)
        if info is None:
            info = symbols[key] = SymbolInfo(
                record.record_type, payload.kind, payload.name, file_path, start_line
            )
        elif info.record_type != record.record_type or info.path != file_path:
            problems.append(
                f"{path.name}:{line_number} symbol {key} is observed as both "
                f"{info.record_type}@{info.path} and {record.record_type}@{file_path}"
            )
        info.observation_ids.append(payload.observation_id)
        info.evidence.extend(record.evidence_references)
        keys_by_observation[payload.observation_id] = key
    return symbols, keys_by_observation


def _load_relationships(
    path: Path, keys_by_observation: dict[str, SymbolKey], problems: list[str]
) -> tuple[Counter[RelationshipKey], dict[RelationshipKey, list[str]], int]:
    counts: Counter[RelationshipKey] = Counter()
    evidence: dict[RelationshipKey, list[str]] = {}
    unmapped = 0
    for line_number, raw in _jsonl(path):
        try:
            record = RelationshipRecord.model_validate(raw)
        except ValidationError as error:
            problems.append(f"{path.name}:{line_number} is not a valid Relationship: {error}")
            continue
        payload = record.payload
        source = keys_by_observation.get(payload.source_observation_id)
        target = keys_by_observation.get(payload.target_observation_id)
        if source is None or target is None:
            unmapped += 1
            continue
        key: RelationshipKey = (str(payload.relationship_type), source, target)
        counts[key] += 1
        evidence.setdefault(key, []).extend(record.evidence_references)
    return counts, evidence, unmapped


def load_stage(run_dir: Path) -> StageData:
    """Load one run folder, raising ``StageDataError`` for missing or bad data."""
    if not run_dir.is_dir():
        raise StageDataError(run_dir, ["run folder does not exist"])
    missing = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
    if missing:
        raise StageDataError(run_dir, [f"missing {name}" for name in missing])

    problems: list[str] = []
    try:
        identity = SnapshotIdentity.model_validate_json(
            (run_dir / SNAPSHOT_IDENTITY_FILE).read_text(encoding="utf-8")
        )
        members = {member.repo_id: member.commit_sha for member in identity.source_members}
        if len(members) != len(identity.source_members):
            problems.append(f"{SNAPSHOT_IDENTITY_FILE} lists a component twice")
        files, stage = _load_files(run_dir / SOURCES_FILE, members, problems)
        symbols, keys_by_observation = _load_symbols(
            run_dir / ENTITIES_FILE, members, files, problems
        )
        relationships, evidence, unmapped = _load_relationships(
            run_dir / RELATIONSHIPS_FILE, keys_by_observation, problems
        )
    except (OSError, ValueError) as error:  # ValidationError and JSONDecodeError are ValueErrors
        raise StageDataError(run_dir, [f"unreadable data: {error}"]) from error
    if problems:
        raise StageDataError(run_dir, problems)
    return StageData(
        run_dir=run_dir,
        stage=stage,
        snapshot_id=identity.snapshot_id,
        members=members,
        files=files,
        symbols=symbols,
        relationships=relationships,
        relationship_evidence=evidence,
        unmapped_relationships=unmapped,
    )


def _status(in_earlier: bool, in_later: bool, modified: bool) -> ChangeStatus:
    if not in_earlier:
        return ChangeStatus.ADDED
    if not in_later:
        return ChangeStatus.REMOVED
    return ChangeStatus.MODIFIED if modified else ChangeStatus.UNCHANGED


def _stage_ref(data: StageData) -> StageRef:
    return StageRef(run_dir=str(data.run_dir), stage=data.stage, snapshot_id=data.snapshot_id)


@dataclass(frozen=True)
class FileMove:
    new_path: str
    status: Literal[ChangeStatus.MOVED, ChangeStatus.MOVED_MODIFIED]


def _unique_pairs(
    removed: dict[tuple[str, str], list[str]], added: dict[tuple[str, str], list[str]]
) -> dict[tuple[str, str], str]:
    """Pair ``(repoId, oldPath)`` with a new path where a match key is one-to-one."""
    return {
        (repo_id, old_paths[0]): added[(repo_id, match)][0]
        for (repo_id, match), old_paths in removed.items()
        if len(old_paths) == 1 and len(added.get((repo_id, match), [])) == 1
    }


def _match_file_moves(earlier: StageData, later: StageData) -> dict[tuple[str, str], FileMove]:
    """Map ``(repoId, oldPath)`` of each moved file to its new path and status.

    Pass 1 pairs byte-identical files (``moved``), pass 2 pairs the remaining
    ones by file name (``moved_modified``, or ``moved`` if the content is still
    identical). A match key shared by several removed or added files of a
    component pairs none of them.
    """
    removed = {
        key: info
        for key, info in earlier.files.items()
        if key[0] in later.members and key not in later.files
    }
    added = {
        key: info
        for key, info in later.files.items()
        if key[0] in earlier.members and key not in earlier.files
    }
    moves: dict[tuple[str, str], FileMove] = {}
    for status, match_key in (
        (ChangeStatus.MOVED, lambda path, info: info.content_sha256),
        (ChangeStatus.MOVED_MODIFIED, lambda path, info: path.rsplit("/", 1)[-1]),
    ):
        removed_by: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
        added_by: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
        for (repo_id, path), info in removed.items():
            removed_by[(repo_id, match_key(path, info))].append(path)
        for (repo_id, path), info in added.items():
            added_by[(repo_id, match_key(path, info))].append(path)
        for (repo_id, old_path), new_path in _unique_pairs(removed_by, added_by).items():
            old_info = removed.pop((repo_id, old_path))
            new_info = added.pop((repo_id, new_path))
            # A name match can still be byte-identical (its hash was shared by several files).
            identical = old_info.content_sha256 == new_info.content_sha256
            moves[(repo_id, old_path)] = FileMove(
                new_path, ChangeStatus.MOVED if identical else status
            )
    return moves


def _match_symbol_moves(
    earlier: StageData, later: StageData, file_moves: dict[tuple[str, str], FileMove]
) -> dict[SymbolKey, tuple[SymbolKey, ChangeStatus]]:
    """Pair source-backed symbols of moved files and give them the file's status.

    Symbols of byte-identical files are matched by ``(kind, name, startLine)``;
    symbols of edited files by ``(kind, name)``, because their lines may shift.
    A signature that repeats within a file is left unpaired.
    """
    type Signature = tuple[str, str, str, str, int | None]

    def index(data: StageData, paths: dict[tuple[str, str], bool]) -> dict[Signature, SymbolKey]:
        found: dict[Signature, SymbolKey] = {}
        repeated: set[Signature] = set()
        for key, symbol in data.symbols.items():
            repo_id = key[0]
            if repo_id is None or symbol.path is None or symbol.start_line is None:
                continue
            exact = paths.get((repo_id, symbol.path))
            if exact is None:
                continue
            line = symbol.start_line if exact else None
            signature = (repo_id, symbol.path, symbol.kind, symbol.name, line)
            if signature in found:
                repeated.add(signature)
            found[signature] = key
        return {signature: key for signature, key in found.items() if signature not in repeated}

    old_symbols = index(
        earlier, {key: move.status is ChangeStatus.MOVED for key, move in file_moves.items()}
    )
    new_symbols = index(
        later,
        {
            (repo_id, move.new_path): move.status is ChangeStatus.MOVED
            for (repo_id, _), move in file_moves.items()
        },
    )
    pairs: dict[SymbolKey, tuple[SymbolKey, ChangeStatus]] = {}
    for (repo_id, old_path, kind, name, line), old_key in old_symbols.items():
        move = file_moves[(repo_id, old_path)]
        new_key = new_symbols.get((repo_id, move.new_path, kind, name, line))
        if new_key is not None and new_key != old_key and old_key not in later.symbols:
            pairs[old_key] = (new_key, move.status)
    return pairs


def compare_stage_data(earlier: StageData, later: StageData) -> StageComparison:
    """Compare two loaded runs; ``earlier`` is the base, ``later`` the new state."""
    components = {
        repo_id: ComponentSummary(
            repo_id=repo_id,
            status=_status(repo_id in earlier.members, repo_id in later.members, False),
            earlier_commit_sha=earlier.members.get(repo_id),
            later_commit_sha=later.members.get(repo_id),
        )
        for repo_id in sorted(earlier.members.keys() | later.members.keys())
    }
    result = StageComparison(
        state="ready",
        earlier=_stage_ref(earlier),
        later=_stage_ref(later),
        earlier_unmapped_relationships=earlier.unmapped_relationships,
        later_unmapped_relationships=later.unmapped_relationships,
    )

    file_moves = _match_file_moves(earlier, later)
    move_sources = {
        (repo_id, move.new_path): (old_path, move.status)
        for (repo_id, old_path), move in file_moves.items()
    }
    modified_files: set[tuple[str, str]] = set()
    for repo_id, path in sorted(earlier.files.keys() | later.files.keys()):
        if (repo_id, path) in file_moves:
            continue  # reported once, under its new path
        previous_path, move_status = move_sources.get((repo_id, path), (None, None))
        old = earlier.files.get((repo_id, previous_path or path))
        new = later.files.get((repo_id, path))
        changed = old is not None and new is not None and old.content_sha256 != new.content_sha256
        status = move_status or _status(old is not None, new is not None, changed)
        summary = components[repo_id]
        summary.files.add(status)
        if changed and move_status is None:
            modified_files.add((repo_id, path))
        if status is not ChangeStatus.UNCHANGED:
            category = categorize_file(path)
            summary.changed_files_by_category.setdefault(category, ChangeCounts()).add(status)
            result.files.append(
                FileChange(
                    repo_id=repo_id,
                    path=path,
                    previous_path=previous_path,
                    status=status,
                    category=category,
                    earlier_content_sha256=old.content_sha256 if old else None,
                    later_content_sha256=new.content_sha256 if new else None,
                    earlier_evidence=old.evidence(repo_id, previous_path or path) if old else None,
                    later_evidence=new.evidence(repo_id, path) if new else None,
                )
            )

    symbol_moves = _match_symbol_moves(earlier, later, file_moves)
    moved_symbols = {old: new for old, (new, _) in symbol_moves.items()}
    symbol_sources = {new: (old, status) for old, (new, status) in symbol_moves.items()}
    for key in sorted(earlier.symbols.keys() | later.symbols.keys(), key=_sort_key):
        if key in symbol_moves:
            continue  # reported once, under its new key
        repo_id, qualified_name = key
        previous_key, move_status = symbol_sources.get(key, (None, None))
        old_symbol = earlier.symbols.get(previous_key or key)
        new_symbol = later.symbols.get(key)
        symbol = new_symbol or old_symbol
        assert symbol is not None
        if move_status is not None:
            status = move_status
        else:
            changed = (
                symbol.path is not None
                and repo_id is not None
                and (repo_id, symbol.path) in modified_files
            )
            status = _status(old_symbol is not None, new_symbol is not None, changed)
        counts = components[repo_id].symbols if repo_id else result.unattributed_symbols
        counts.add(status)
        if status is not ChangeStatus.UNCHANGED:
            result.symbols.append(
                SymbolChange(
                    repo_id=repo_id,
                    qualified_name=qualified_name,
                    previous_qualified_name=previous_key[1] if previous_key else None,
                    record_type=symbol.record_type,
                    kind=symbol.kind,
                    path=symbol.path,
                    previous_path=old_symbol.path if previous_key and old_symbol else None,
                    status=status,
                    earlier_observation_ids=old_symbol.observation_ids if old_symbol else [],
                    later_observation_ids=new_symbol.observation_ids if new_symbol else [],
                    earlier_evidence=old_symbol.evidence if old_symbol else [],
                    later_evidence=new_symbol.evidence if new_symbol else [],
                )
            )

    # Rewrite earlier endpoints to their paired keys so a move alone is not a change.
    earlier_relationships: Counter[RelationshipKey] = Counter()
    earlier_evidence: dict[RelationshipKey, list[str]] = {}
    for (relationship_type, source, target), count in earlier.relationships.items():
        key = (
            relationship_type,
            moved_symbols.get(source, source),
            moved_symbols.get(target, target),
        )
        earlier_relationships[key] += count
        earlier_evidence.setdefault(key, []).extend(
            earlier.relationship_evidence.get((relationship_type, source, target), [])
        )

    all_relationships = earlier_relationships.keys() | later.relationships.keys()
    for key in sorted(all_relationships, key=_relationship_sort_key):
        relationship_type, source, target = key
        old_count, new_count = earlier_relationships[key], later.relationships[key]
        repo_id = source[0] or target[0]
        counts = components[repo_id].relationships if repo_id else result.unattributed_relationships
        if old_count == new_count:
            counts.add(ChangeStatus.UNCHANGED)
            continue
        status = ChangeStatus.ADDED if new_count > old_count else ChangeStatus.REMOVED
        counts.add(status)
        result.relationships.append(
            RelationshipChange(
                relationship_type=relationship_type,
                source=SymbolRef(repo_id=source[0], qualified_name=source[1]),
                target=SymbolRef(repo_id=target[0], qualified_name=target[1]),
                status=status,
                earlier_count=old_count,
                later_count=new_count,
                earlier_evidence=earlier_evidence.get(key, []),
                later_evidence=later.relationship_evidence.get(key, []),
            )
        )

    for summary in components.values():
        if summary.status is ChangeStatus.UNCHANGED and (
            summary.files.changed or summary.symbols.changed
        ):
            summary.status = ChangeStatus.MODIFIED
    result.components = list(components.values())
    return result


def compare_stages(earlier_run_dir: Path, later_run_dir: Path) -> StageComparison:
    """Load and compare two run folders.

    Missing or inconsistent data never produces a guessed comparison: the result
    then has ``state="insufficient_data"`` and lists every problem found.
    """
    loaded: list[StageData] = []
    problems: list[str] = []
    for run_dir in (earlier_run_dir, later_run_dir):
        try:
            loaded.append(load_stage(run_dir))
        except StageDataError as error:
            problems.extend(f"{run_dir}: {problem}" for problem in error.problems)
    if problems:
        return StageComparison(
            state="insufficient_data",
            earlier=StageRef(run_dir=str(earlier_run_dir)),
            later=StageRef(run_dir=str(later_run_dir)),
            problems=problems,
        )
    return compare_stage_data(*loaded)


def _sort_key(key: SymbolKey) -> tuple[str, str]:
    return (key[0] or "", key[1])


def _relationship_sort_key(key: RelationshipKey) -> tuple[str, tuple[str, str], tuple[str, str]]:
    return (key[0], _sort_key(key[1]), _sort_key(key[2]))


def _counts_cell(counts: ChangeCounts, with_modified: bool = True) -> str:
    cell = f"+{counts.added} / -{counts.removed}"
    if with_modified:
        cell += f" / ~{counts.modified} / >{counts.moved} / >~{counts.moved_modified}"
    return f"{cell} / ={counts.unchanged}"


def _category_cell(summary: ComponentSummary) -> str:
    return ", ".join(
        f"{category.value} {counts.changed}"
        for category in FileCategory
        if (counts := summary.changed_files_by_category.get(category))
    )


def _file_label(change: FileChange) -> str:
    if change.previous_path:
        return f"{change.status.value}: `{change.repo_id}:{change.previous_path}` → `{change.path}`"
    return f"{change.status.value}: `{change.repo_id}:{change.path}`"


def _symbol_label(ref: SymbolRef | SymbolChange) -> str:
    return f"{ref.repo_id or 'external'}:{ref.qualified_name}"


def render_markdown(comparison: StageComparison, max_items: int = 15) -> str:
    """Render a short Markdown report; long change lists are truncated."""
    earlier = comparison.earlier.stage or comparison.earlier.run_dir
    later = comparison.later.stage or comparison.later.run_dir
    lines = [f"# Stage comparison: {earlier} → {later}", ""]
    if comparison.state == "insufficient_data":
        lines += ["**Insufficient data** — no comparison was made.", ""]
        lines += [f"- {problem}" for problem in comparison.problems]
        return "\n".join(lines) + "\n"

    lines += [
        f"- earlier: `{comparison.earlier.run_dir}` (snapshot `{comparison.earlier.snapshot_id}`)",
        f"- later: `{comparison.later.run_dir}` (snapshot `{comparison.later.snapshot_id}`)",
        "- counts are `+added / -removed / ~modified / >moved / >~moved_modified / =unchanged`;"
        " a symbol is modified when it exists in both stages and its file content changed",
        "",
        "| Component | Status | Commit | Files | Changed files by category | Symbols "
        "| Relationships |",
        "|---|---|---|---|---|---|---|",
    ]
    for summary in comparison.components:
        commits = " → ".join(
            sha[:8] for sha in (summary.earlier_commit_sha, summary.later_commit_sha) if sha
        )
        lines.append(
            f"| {summary.repo_id} | {summary.status.value} | {commits} "
            f"| {_counts_cell(summary.files)} | {_category_cell(summary)} "
            f"| {_counts_cell(summary.symbols)} "
            f"| {_counts_cell(summary.relationships, with_modified=False)} |"
        )
    lines.append(
        f"| _external (no component)_ | | | | | {_counts_cell(comparison.unattributed_symbols)} "
        f"| {_counts_cell(comparison.unattributed_relationships, with_modified=False)} |"
    )
    lines += [
        "",
        f"Unmapped relationships (endpoint not in entities): "
        f"earlier {comparison.earlier_unmapped_relationships}, "
        f"later {comparison.later_unmapped_relationships}.",
    ]

    def section(title: str, items: list[str]) -> None:
        lines.extend(["", f"## {title} ({len(items)})", ""])
        lines.extend(f"- {item}" for item in items[:max_items])
        if len(items) > max_items:
            lines.append(f"- … {len(items) - max_items} more")

    infrastructure = (FileCategory.DEPLOYMENT, FileCategory.DB_ACCESS)
    lines.extend(["", "## Deployment & DB-access changes"])
    for category in infrastructure:
        items = [_file_label(change) for change in comparison.files if change.category is category]
        lines.extend(["", f"**{category.value}** ({len(items)})", ""])
        lines.extend(f"- {item}" for item in items or ["none"])
    section("Changed files", [_file_label(change) for change in comparison.files])
    section(
        "Changed symbols",
        [
            f"{change.status.value}: `{_symbol_label(change)}` ({change.kind})"
            for change in comparison.symbols
        ],
    )
    section(
        "Changed relationships",
        [
            f"{change.status.value} ({change.earlier_count} → {change.later_count}): "
            f"`{_symbol_label(change.source)}` -{change.relationship_type}-> "
            f"`{_symbol_label(change.target)}`"
            for change in comparison.relationships
        ],
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two persisted ingestion runs.")
    parser.add_argument("earlier_run_dir", type=Path)
    parser.add_argument("later_run_dir", type=Path)
    parser.add_argument("--md", type=Path, help="also write the Markdown report to this file")
    args = parser.parse_args(argv)

    comparison = compare_stages(args.earlier_run_dir, args.later_run_dir)
    report = render_markdown(comparison)
    if args.md:
        args.md.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0 if comparison.state == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
