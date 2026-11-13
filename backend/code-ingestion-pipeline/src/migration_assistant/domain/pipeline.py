"""Results and expected failures of a complete ingestion run."""

from dataclasses import dataclass
from pathlib import Path

from migration_assistant.domain.sources import LoadResult


class PipelineError(Exception):
    """An ingestion stage could not produce its required outputs."""


@dataclass(frozen=True)
class PipelineResult:
    load_result: LoadResult
    run_directory: Path
    graph_paths: dict[str, Path]
    entity_count: int
    relationship_count: int
