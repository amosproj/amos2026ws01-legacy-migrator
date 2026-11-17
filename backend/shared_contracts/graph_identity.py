"""Compatibility import for Raihan's graph identity helpers."""

from app.graph_schema.models import compute_entity_id, compute_file_id, normalize_path

__all__ = ["compute_entity_id", "compute_file_id", "normalize_path"]
