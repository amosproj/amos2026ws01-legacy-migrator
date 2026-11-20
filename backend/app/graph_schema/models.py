"""Raihan's stable graph identity helpers retained from issue #21.

The canonical graph data contract lives in ``shared_contracts.records``.
"""

from __future__ import annotations

import hashlib

from shared_contracts.source_span import SourceSpan


def normalize_path(path: str) -> str:
    """Return a repository-relative path with forward slashes."""
    return path.replace("\\", "/").strip("/")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_file_id(snapshot_id: str, component_key: str, path: str) -> str:
    """Hash snapshot, repository/component key, and normalized file path."""
    return _sha256(f"{snapshot_id}:{component_key}:{normalize_path(path)}")


def compute_entity_id(
    snapshot_id: str,
    component_key: str,
    path: str,
    kind: str,
    qualified_name: str,
    signature: str | None = None,
) -> str:
    """Hash a source entity, keeping overloaded signatures distinct."""
    token = f"{snapshot_id}:{component_key}:{normalize_path(path)}:{kind}:{qualified_name}"
    if signature is not None:
        token += f":{signature}"
    return _sha256(token)


__all__ = ["SourceSpan", "compute_entity_id", "compute_file_id", "normalize_path"]
