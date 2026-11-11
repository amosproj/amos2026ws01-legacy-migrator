"""Port definition for code entity extractors (Issue #19)."""

from typing import Any, Protocol

from migration_assistant.domain.entities import EntityExtractionResult
from migration_assistant.domain.sources import SourceFile


class EntityExtractorProtocol(Protocol):
    """Extraction seam allowing real parsers and mock implementations."""

    def extract_from_sources(
        self, sources: list[SourceFile], snapshot_id: str
    ) -> EntityExtractionResult:
        """Extract code entities from loaded source files."""
        ...

    def extract_from_mock(
        self, mock_records: list[dict[str, Any]], snapshot_id: str
    ) -> EntityExtractionResult:
        """Extract code entities from predefined or mock parser records."""
        ...
