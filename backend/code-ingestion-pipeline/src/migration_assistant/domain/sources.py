"""Source files loaded from the checked-out reference source (Issue #17)."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from migration_assistant.domain.checkout import CheckoutError, CheckoutResult
from shared_contracts.source_file import SourceFile as SourceFile


class SourceLoadError(CheckoutError):
    """The checked-out source cannot be loaded reliably."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)


class SkippedFile(_Model):
    """A file that was seen but not loaded, with the reason."""

    repo_id: str
    path: str
    reason: str
    detail: str | None = None


class LoadCounts(_Model):
    loaded: int
    skipped: int
    loaded_by_language: dict[str, int]
    skipped_by_reason: dict[str, int]


class LoadResult(_Model):
    checkout: CheckoutResult
    files: list[SourceFile]
    skipped: list[SkippedFile]
    counts: LoadCounts
