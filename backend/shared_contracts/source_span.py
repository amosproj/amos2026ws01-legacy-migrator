"""The revision-pinned position of source evidence."""

from __future__ import annotations

from pathlib import PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

COMMIT_SHA_PATTERN = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"


class SourceSpan(BaseModel):
    """A repository-relative, commit-pinned source range.

    Python callers use snake_case. JSON keeps the established camelCase keys.
    Lines are one-based and inclusive; optional columns are zero-based offsets.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
        extra="forbid",
    )

    repo_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_column: int | None = Field(default=None, ge=0)
    end_column: int | None = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def require_normalized_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if (
            normalized.startswith("/")
            or PureWindowsPath(value).drive
            or any(part in ("", ".", "..") for part in normalized.split("/"))
        ):
            raise ValueError("path must be a normalized repository-relative path")
        return normalized

    @model_validator(mode="after")
    def validate_range(self) -> SourceSpan:
        if self.end_line < self.start_line:
            raise ValueError("end_line must not precede start_line")
        if (
            self.start_line == self.end_line
            and self.start_column is not None
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError("end_column must not precede start_column on the same line")
        return self
