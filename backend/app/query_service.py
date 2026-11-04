"""Query service seam (tickets #24 and #25).

The API endpoint delegates all query answering to a ``QueryService``. The
service streams answer deltas through an ``LlmProvider``; the mock provider
yields a single deterministic delta so development works without a model
endpoint. The knowledge-graph query logic will later be plugged in behind this
same seam.
"""

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from .llm import LlmProvider

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
    LLM implementation. The knowledge-graph context will be added to the prompt
    once the graph query logic exists.
    """

    def __init__(self, provider: LlmProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return f"llm ({self._provider.name})"

    def sources(self) -> list[str]:
        return [f"llm:{self._provider.name}"]

    def stream_answer(
        self, query: str
    ) -> AsyncIterator[tuple[Literal["thinking", "content"], str]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return self._provider.stream_reply(messages)


def create_query_service(provider: LlmProvider) -> QueryService:
    """Factory for the query service."""
    return LlmQueryService(provider)
