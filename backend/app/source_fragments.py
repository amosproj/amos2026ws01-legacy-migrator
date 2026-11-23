"""Revision-pinned lookup of source fragments for graph positions."""

import hashlib
from typing import Protocol
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from shared_contracts.source_file import SourceFile
from shared_contracts.source_span import SourceSpan


class SourceFragmentError(Exception):
    """A source fragment could not be resolved."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FragmentPosition(SourceSpan):
    """A shared source span and the migration stage that selected it."""

    stage: str = Field(min_length=1)


class SourceFragment(BaseModel):
    """The resolved fragment plus everything needed for verifiable evidence."""

    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)

    position: FragmentPosition
    language: str
    fragment: str
    fragment_sha256: str
    total_lines: int
    github_url: str


class FragmentFetcher(Protocol):
    """Reads one file's text at a pinned revision."""

    def fetch(self, position: FragmentPosition) -> SourceFile: ...


def extract_fragment(
    position: FragmentPosition,
    content: str,
    language: str,
    public_url: str,
) -> SourceFragment:
    """Build the fragment from full file content; raises on a bad line range."""
    lines = content.splitlines()
    if position.end_line > len(lines):
        raise SourceFragmentError(
            "line_range_out_of_bounds",
            f"line range {position.start_line}-{position.end_line} beyond end of "
            f"{position.path} ({len(lines)} lines)",
        )
    fragment = "\n".join(lines[position.start_line - 1 : position.end_line])
    return SourceFragment(
        position=position,
        language=language,
        fragment=fragment,
        fragment_sha256=hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
        total_lines=len(lines),
        github_url=f"{public_url.rstrip('/')}/blob/{position.commit_sha}/{quote(position.path)}"
        f"#L{position.start_line}-L{position.end_line}",
    )


def resolve_fragment(
    position: FragmentPosition,
    fetcher: FragmentFetcher,
) -> SourceFragment:
    """Resolve one position through the fetcher seam."""
    file = fetcher.fetch(position)
    return extract_fragment(position, file.content, file.language, file.public_url)
