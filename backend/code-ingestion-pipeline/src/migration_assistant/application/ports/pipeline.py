"""Boundaries for source loading, extraction, and local pipeline artifacts."""

from pathlib import Path
from typing import Protocol

from migration_assistant.domain.checkout import CheckoutResult, ComponentCheckout
from migration_assistant.domain.pipeline import RelationshipHandoffResult
from migration_assistant.domain.reference_source import ReferenceSourceConfig
from migration_assistant.domain.sources import LoadResult, SourceFile


class SourceLoader(Protocol):
    def __call__(self, config: ReferenceSourceConfig, checkout: CheckoutResult) -> LoadResult: ...


class GraphBuilder(Protocol):
    def build(
        self, member: ComponentCheckout, files: list[SourceFile], root: Path, output: Path
    ) -> Path: ...


class HandoffWriter(Protocol):
    def __call__(
        self,
        graph_paths: list[Path],
        sources_jsonl: Path,
        run: Path,
        *,
        graph_mode: str = "combined",
    ) -> RelationshipHandoffResult: ...


class PipelineStorage(Protocol):
    def create_run(self, output: Path) -> Path: ...

    def write_sources(self, out: Path, files: list[SourceFile]) -> None: ...

class PersistenceWriter(Protocol):
    def persist_handoff(self, handoff: RelationshipHandoffResult) -> None: ...