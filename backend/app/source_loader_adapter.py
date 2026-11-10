"""#17-backed fetcher for the source fragment service (Issue #67).

Maps fragment positions onto the files the reference loader (#17) produces.
The loader writes its results as canonical JSON (see the reference-loader
usage guide), so the wiring in ``main.py`` reads that output directly — this
module stays independent of the pipeline package and works with plain dicts
shaped like ``SourceFile``/``ComponentCheckout`` records (camelCase aliases).

The position's ``commit_sha`` must match the pinned commit of the checkout,
and the file must have been loaded for that stage. Files the loader skipped
(size, encoding, exclusions) are reported as ``path_not_loaded``.
"""

from typing import Any

from .source_fragments import FragmentPosition, SourceFragmentError


class LoaderFragmentFetcher:
    """Serves fragment positions from one loaded-stage record (#17 output)."""

    def __init__(self, checkout: dict[str, Any], files: list[dict[str, Any]]) -> None:
        self._stage = str(checkout["stage"])
        self._members = {str(m["repoId"]): m for m in checkout["members"]}
        self._files = {(str(f["repoId"]), str(f["path"])): f for f in files}

    @classmethod
    def from_load_result_json(cls, data: dict[str, Any]) -> "LoaderFragmentFetcher":
        """Build from the #17 loader's serialised ``LoadResult`` (camelCase)."""
        return cls(checkout=data["checkout"], files=data["files"])

    def fetch(
        self, position: FragmentPosition
    ) -> tuple[str, str, str, int]:
        file = self._files.get((position.repo_id, position.path))
        if file is None:
            raise SourceFragmentError(
                "path_not_loaded",
                f"file '{position.path}' was not loaded for "
                f"'{position.repo_id}' (stage {position.stage}); "
                "it may be excluded or skipped by the loader",
            )
        if file["commitSha"] != position.commit_sha:
            raise SourceFragmentError(
                "commit_sha_mismatch",
                f"file '{position.path}' is pinned at commit {file['commitSha']}, "
                f"but the position references {position.commit_sha} "
                "(stale graph node?)",
            )
        return (
            str(file["content"]),
            str(file["language"]),
            str(file["publicUrl"]),
            int(file["sizeBytes"]),
        )
