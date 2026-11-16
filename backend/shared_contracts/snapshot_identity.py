"""Canonical source and analysis snapshot IDs from the architecture contract."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from shared_contracts.records import SCHEMA_VERSION, Extractor, SnapshotIdentity, SourceRevision
from shared_contracts.source_span import COMMIT_SHA_PATTERN


def canonical_json(value: Any) -> bytes:
    """Encode identity inputs as canonical UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(canonical_json(value)).hexdigest()


def compute_snapshot_identity(
    source_revisions: dict[str, str],
    extractors: Iterable[dict[str, str]],
    extraction_config: dict[str, Any],
) -> SnapshotIdentity:
    """Apply the project identity formula without timestamps or local paths."""
    if not source_revisions:
        raise ValueError("At least one source repository revision is required")
    source_members = []
    for repo_id, commit_sha in sorted(source_revisions.items()):
        if not repo_id:
            raise ValueError("repo_id must not be empty")
        if not re.fullmatch(COMMIT_SHA_PATTERN, commit_sha):
            raise ValueError(f"A full Git commit SHA is required for {repo_id!r}")
        source_members.append({"repoId": repo_id, "commitSha": commit_sha})
    source_snapshot_id = _digest(source_members)

    extractor_set = sorted({(str(item["name"]), str(item["version"])) for item in extractors})
    if not extractor_set or any(not name or not version for name, version in extractor_set):
        raise ValueError("At least one extractor identity is required")
    extractor_records = [{"name": name, "version": version} for name, version in extractor_set]
    extractor_set_digest = _digest(extractor_records)
    extraction_config_digest = _digest(extraction_config)
    identity_payload = {
        "sourceSnapshotId": source_snapshot_id,
        "schemaVersion": SCHEMA_VERSION,
        "extractorSetDigest": extractor_set_digest,
        "extractionConfigDigest": extraction_config_digest,
    }
    return SnapshotIdentity(
        source_members=[
            SourceRevision(repo_id=item["repoId"], commit_sha=item["commitSha"])
            for item in source_members
        ],
        source_snapshot_id=source_snapshot_id,
        schema_version=SCHEMA_VERSION,
        extractors=[Extractor.model_validate(item) for item in extractor_records],
        extractor_set_digest=extractor_set_digest,
        extraction_config=extraction_config,
        extraction_config_digest=extraction_config_digest,
        snapshot_id=_digest(identity_payload),
    )
