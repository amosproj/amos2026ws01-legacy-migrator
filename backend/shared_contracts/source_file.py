"""A text file exported by the reference source loader."""

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from .source_span import COMMIT_SHA_PATTERN


def source_lines(content: str) -> list[str]:
    """Split Git source lines, accepting LF and CRLF file endings."""
    return content.replace("\r\n", "\n").removesuffix("\n").split("\n") if content else []


class SourceFile(BaseModel):
    """One text file of a component, read at the pinned commit."""

    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)

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
