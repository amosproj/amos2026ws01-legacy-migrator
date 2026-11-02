"""Query service seam (ticket #24).

The API endpoint delegates all query answering to a ``QueryService``. The mock
implementation returns deterministic canned answers so the endpoint operates
with mocked graph/query results, as required by the ticket's acceptance
criteria. Ticket #25 (LLM provider interface) and the knowledge-graph query
logic will later be plugged in behind this same seam without changing the API
layer.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class QueryResult:
    """Outcome of one query: the answer text plus evidence source labels."""

    answer: str
    sources: Sequence[str] = field(default_factory=list)


class QueryService(Protocol):
    """Answers one migration-status query for the chat endpoint."""

    name: str

    def answer(self, query: str, conversation_id: str | None) -> QueryResult: ...


class MockQueryService:
    """Development stand-in: deterministic answers, no LLM and no graph yet."""

    name = "mock"

    def answer(self, query: str, conversation_id: str | None) -> QueryResult:
        return QueryResult(
            answer=(
                "Mock answer: no knowledge graph or LLM is connected yet. "
                f"Received query: {query[:120]!r}. "
                "This reply comes from the mock query service (ticket #24); "
                "the LLM provider interface (ticket #25) will replace it."
            ),
            sources=["mock:knowledge-graph", "mock:migration-history"],
        )


def create_query_service() -> QueryService:
    """Factory for the query service; swap the implementation here later."""
    return MockQueryService()
