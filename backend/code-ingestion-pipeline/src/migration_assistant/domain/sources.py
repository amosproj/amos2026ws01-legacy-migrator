"""Source files loaded from the checked-out reference source (Issue #17)."""

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from migration_assistant.domain.checkout import (
    COMMIT_SHA_PATTERN,
    CheckoutError,
    CheckoutResult,
)


class SourceLoadError(CheckoutError):
    """The checked-out source cannot be loaded reliably."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)


class SourceFile(_Model):
    """One text file of a component, read at the pinned commit."""

    repo_id: str
    origin: str
    stage: str
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    public_url: str
    path: str
    language: str
    size_bytes: int
    content_sha256: str
    encoding: str
    content: str

    @computed_field
    @property
    def github_url(self) -> str:
        return f"{self.public_url}/blob/{self.commit_sha}/{self.path}"


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
