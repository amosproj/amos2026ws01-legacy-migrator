"""Request/response models for the query API (ticket #24).

``POST /api/chat`` receives ``{query, conversation_id?}`` and answers with a
newline-delimited JSON stream (see ``main.py``): a ``sources`` event first,
then ``content`` text deltas, or an ``error`` event on failure.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

QueryText = Annotated[str, Field(min_length=1, max_length=32_000)]


class ChatRequest(BaseModel):
    """A user query submitted by the frontend."""

    query: QueryText
    conversation_id: Annotated[str | None, Field(max_length=200)] = None


class HealthResponse(BaseModel):
    """Service liveness info; any 2xx counts as 'connected' for the frontend."""

    status: str
    service: str
    version: str
    model: str


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
