"""Query service seam (tickets #24, #25, and #23).

The API endpoint delegates all query answering to a ``QueryService``. The
service streams answer deltas through an ``LlmProvider``; the mock provider
yields a single deterministic delta so development works without a model
endpoint. Knowledge graph facts are injected into the prompt context to ground
answers in verified architecture evidence.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Literal, Protocol

from .llm import LlmProvider

if TYPE_CHECKING:
    from .graph.service import GraphQueryService

SYSTEM_PROMPT = (
    "You are SunsetTracker, an assistant that answers questions about the "
    "migration status of legacy systems. Answer concisely and factually."
)


class QueryService(Protocol):
    """Answers one migration-status query for the chat endpoint."""

    name: str

    def sources(self) -> list[str]:
        """Evidence source labels attached to every answer."""
        ...

    def stream_answer(
        self, query: str
    ) -> AsyncIterator[tuple[Literal["thinking", "content"], str]]:
        """Yield ``(kind, text)`` deltas for one query: thinking and content."""
        ...


class LlmQueryService:
    """Answers queries through an ``LlmProvider`` (ticket #25).

    The provider is injected, so this service never depends on one specific
    LLM implementation. The knowledge-graph context grounds the LLM in
    verified migration facts (Issue #23).
    """

    def __init__(
        self,
        provider: LlmProvider,
        graph_service: GraphQueryService | None = None,
    ) -> None:
        self._provider = provider
        self._graph_service = graph_service

    @property
    def name(self) -> str:
        return f"llm ({self._provider.name})"

    def sources(self) -> list[str]:
        return [f"llm:{self._provider.name}"]

    def stream_answer(
        self, query: str
    ) -> AsyncIterator[tuple[Literal["thinking", "content"], str]]:
        system_content = SYSTEM_PROMPT
        if self._graph_service is not None:
            context = self._graph_service.format_context_for_prompt()
            system_content = f"{SYSTEM_PROMPT}\n\n{context}"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]
        return self._provider.stream_reply(messages)


def create_query_service(
    provider: LlmProvider,
    graph_service: GraphQueryService | None = None,
) -> QueryService:
    """Factory for the query service."""
    return LlmQueryService(provider, graph_service=graph_service)
