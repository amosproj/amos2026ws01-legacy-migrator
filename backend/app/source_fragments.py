"""Source fragment lookup (Issue #67).

Bridges the code graph and the source text: given the position metadata of a
graph node (repository, path, lines, commit), returns the concrete source
fragment from the reference checkout loaded by the #17 loader. This is a pure
lookup — there is deliberately no full-text/vector index over the source code
(#67 scope revision after the industry-partner alignment).

The fetching seam (``FragmentFetcher``) keeps this module independent of how a
checkout is loaded; the #17-backed adapter lives in ``main.py`` wiring.
"""

import hashlib
import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

COMMIT_SHA_PATTERN = r"^[0-9a-f]{40}([0-9a-f]{24})?$"

# 上选择浏览 Mirrors migration_assistant.domain.checkout; duplicated as a literal
# because app must not import the pipeline package (comes via the wiring only).
_SHA_RE = re.compile(COMMIT_SHA_PATTERN)


class SourceFragmentError(Exception):
    """A source fragment could not be resolved."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FragmentPosition(BaseModel):
    """Where a fragment lives, as carried by graph nodes (#19 SourceSpan).

    ``commit_sha`` is the pinning revision of the snapshot the node belongs to,
    matching ``SourceFile.commit_sha`` of the #17 loader.
    """

    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )

    repo_id: str
    stage: str
    path: str
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @field_validator("end_line")
    @classmethod
    def _end_after_start(cls, end: int, info) -> int:
        # Field validation order is declaration order, so start_line is present
        # under its attribute name regardless of the alias used for input.
        start = info.data.get("start_line")
        if start is not None and end < start:
            raise ValueError("end_line must be >= start_line")
        return end


class SourceFragment(BaseModel):
    """The resolved fragment plus everything needed for verifiable evidence."""

    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )

    position: FragmentPosition
    language: str
    fragment: str
    fragment_sha256: str
    total_lines: int
    github_url: str


FetcherKind = Literal["local_checkout"]


class FragmentFetcher(Protocol):
    """Reads one file's text at a pinned revision (implemented by #17 wiring)."""

    def fetch(
        self, position: FragmentPosition
    ) -> tuple[str, str, str, int]:
        """Return (content, language, public_url, total_lines) for the position.

        Raises ``SourceFragmentError`` with a stable code when the position
        cannot be resolved.
        """
        ...


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
        github_url=f"{public_url}/blob/{position.commit_sha}/{position.path}"
        f"#L{position.start_line}-L{position.end_line}",
    )


def resolve_fragment(
    position: FragmentPosition,
    fetcher: FragmentFetcher,
) -> SourceFragment:
    """Resolve one position through the fetcher seam."""
    content, language, public_url, _total = fetcher.fetch(position)
    return extract_fragment(position, content, language, public_url)
