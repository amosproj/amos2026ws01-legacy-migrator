"""Compatibility exports for identity helpers; graph records live in shared_contracts."""

from .models import SourceSpan, compute_entity_id, compute_file_id, normalize_path

__all__ = ["SourceSpan", "compute_entity_id", "compute_file_id", "normalize_path"]
