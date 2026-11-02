"""Request/response models for the query API (ticket #24).

The chat contract mirrors what the frontend expects (see
``frontend/src/lib/chatAdapter.ts`` and ``frontend/src/config/env.ts`` on the
``create-basic-query-interface`` branch): ``POST /api/chat`` receives
``{query, conversation_id?}`` and returns ``{answer, conversation_id?, sources?}``.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

QueryText = Annotated[str, Field(min_length=1, max_length=32_000)]


class ChatRequest(BaseModel):
    """A user query submitted by the frontend."""

    query: QueryText
    conversation_id: Annotated[str | None, Field(max_length=200)] = None


class ChatResponse(BaseModel):
    """Structured answer; ``sources`` carries evidence labels for the reply."""

    answer: str
    conversation_id: str | None = None
    sources: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Service liveness info; any 2xx counts as 'connected' for the frontend."""

    status: str
    service: str
    version: str


class Repository(BaseModel):
    """Repository entry for the frontend repository picker.

    Serialized in camelCase (``fullName``, ``providerLabel``, ...) because the
    frontend ``Repository`` type uses camelCase field names.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    provider: str
    provider_label: str
    full_name: str
    description: str | None = None
    default_branch: str
    is_private: bool
