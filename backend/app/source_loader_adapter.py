"""Read source files from an offline ingestion export."""

from collections.abc import Iterable
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ValidationError

from shared_contracts.source_file import SourceFile

from .source_fragments import FragmentPosition, SourceFragmentError


class _LegacyLoadResult(BaseModel):
    files: list[SourceFile]


class LoaderFragmentFetcher:
    """Look up files by stage, repository and path and check the pinned commit."""

    def __init__(self, files: Iterable[SourceFile]) -> None:
        self._files: dict[tuple[str, str, str], SourceFile] = {}
        self._revisions: dict[tuple[str, str], str] = {}
        for file in files:
            key = (file.stage, file.repo_id, file.path)
            if key in self._files:
                raise ValueError(
                    f"duplicate source file in {file.stage}: {file.repo_id}/{file.path}"
                )
            revision = self._revisions.setdefault((file.stage, file.repo_id), file.commit_sha)
            if revision != file.commit_sha:
                raise ValueError(f"multiple revisions for {file.repo_id} in {file.stage}")
            self._files[key] = file
        if not self._files:
            raise ValueError("source export contains no files")

    @classmethod
    def from_export(cls, path: Path) -> Self:
        with path.open(encoding="utf-8") as source:
            if path.suffix.lower() != ".jsonl":
                try:
                    return cls(_LegacyLoadResult.model_validate_json(source.read()).files)
                except ValidationError as exc:
                    raise ValueError(f"invalid loader export in {path}") from exc

            files = []
            for line_number, line in enumerate(source, start=1):
                try:
                    files.append(SourceFile.model_validate_json(line))
                except ValidationError as exc:
                    raise ValueError(f"invalid source record at {path}:{line_number}") from exc
        return cls(files)

    def revisions_for_stage(self, stage: str) -> dict[str, str]:
        """Return the pinned revisions represented in the requested stage."""
        return {
            repo_id: commit
            for (file_stage, repo_id), commit in self._revisions.items()
            if file_stage == stage
        }

    def fetch(self, position: FragmentPosition) -> SourceFile:
        file = self._files.get((position.stage, position.repo_id, position.path))
        if file is None:
            raise SourceFragmentError(
                "path_not_loaded",
                f"file '{position.path}' was not loaded for "
                f"'{position.repo_id}' (stage {position.stage})",
            )
        if file.commit_sha != position.commit_sha:
            raise SourceFragmentError(
                "commit_sha_mismatch",
                f"file '{position.path}' is pinned at commit {file.commit_sha}, "
                f"but the position references {position.commit_sha}",
            )
        return file
