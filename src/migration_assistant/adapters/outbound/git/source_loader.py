"""Detects and loads the relevant source files of the checked-out components (Issue #17).

Files are only read. Git is used only for ``status --porcelain``, with hooks disabled.
"""

import hashlib
import logging
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from migration_assistant.domain.checkout import CheckoutResult, ComponentCheckout
from migration_assistant.domain.reference_source import ReferenceSourceConfig
from migration_assistant.domain.sources import (
    LoadCounts,
    LoadResult,
    SkippedFile,
    SourceFile,
    SourceLoadError,
)

logger = logging.getLogger(__name__)

LANGUAGE_BY_EXTENSION = {
    ".java": "java",
    ".xml": "xml",
    ".properties": "properties",
    ".sql": "sql",
    ".conf": "nginx-conf",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".vue": "vue",
    ".html": "html",
    ".sh": "shell",
}
LANGUAGE_BY_FILENAME = {"Dockerfile": "dockerfile"}


def load_sources(config: ReferenceSourceConfig, checkout: CheckoutResult) -> LoadResult:
    """Read the relevant files of every checked-out component, sorted by path."""
    exclude = [_glob_to_regex(pattern) for pattern in config.exclude]
    max_bytes = config.max_file_size_kb * 1024

    files: list[SourceFile] = []
    skipped: list[SkippedFile] = []
    for member in checkout.members:
        _require_clean(member)
        _load_component(config, checkout, member, exclude, max_bytes, files, skipped)

    files.sort(key=lambda file: (file.repo_id, file.path))
    skipped.sort(key=lambda file: (file.repo_id, file.path, file.reason))
    counts = LoadCounts(
        loaded=len(files),
        skipped=len(skipped),
        loaded_by_language=dict(sorted(Counter(f.language for f in files).items())),
        skipped_by_reason=dict(sorted(Counter(s.reason for s in skipped).items())),
    )
    logger.info(
        "Loaded %d files %s; skipped %d %s",
        counts.loaded,
        counts.loaded_by_language,
        counts.skipped,
        counts.skipped_by_reason,
    )
    return LoadResult(checkout=checkout, files=files, skipped=skipped, counts=counts)


def _require_clean(member: ComponentCheckout) -> None:
    with tempfile.TemporaryDirectory(prefix="empty-hooks-") as hooks:
        try:
            completed = subprocess.run(
                ["git", "-c", f"core.hooksPath={hooks}", "status", "--porcelain"],
                cwd=member.local_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise SourceLoadError(
                f"Cannot check git status of '{member.repo_id}': {error}"
            ) from error
    if completed.stdout.strip():
        raise SourceLoadError(
            f"Component '{member.repo_id}' has local changes and does not match "
            f"commit {member.commit_sha}"
        )


def _load_component(
    config: ReferenceSourceConfig,
    checkout: CheckoutResult,
    member: ComponentCheckout,
    exclude: list[re.Pattern],
    max_bytes: int,
    files: list[SourceFile],
    skipped: list[SkippedFile],
) -> None:
    root = member.local_path.resolve()

    def skip(path: str, reason: str) -> None:
        skipped.append(SkippedFile(repo_id=member.repo_id, path=path, reason=reason))

    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name != ".git")
        for name in sorted(filenames) + [d for d in dirnames if (Path(directory) / d).is_symlink()]:
            full = Path(directory) / name
            relative = full.relative_to(root).as_posix()

            if name == ".git":
                continue
            if full.is_symlink():
                skip(relative, "symlink")
                continue
            if not _is_inside(full.resolve(), root):
                skip(relative, "outside_component")
                continue
            if any(pattern.fullmatch(relative) for pattern in exclude):
                skip(relative, "excluded")
                continue
            language = _language(name, config.include)
            if language is None:
                skip(relative, "not_included")
                continue
            if full.stat().st_size > max_bytes:
                skip(relative, "too_large")
                continue

            data = full.read_bytes()
            if b"\x00" in data:
                skip(relative, "binary")
                continue
            content, encoding = _decode(data)
            files.append(
                SourceFile(
                    repo_id=member.repo_id,
                    origin=member.origin,
                    stage=checkout.stage,
                    commit_sha=member.commit_sha,
                    public_url=member.public_url,
                    path=relative,
                    language=language,
                    size_bytes=len(data),
                    content_sha256=hashlib.sha256(data).hexdigest(),
                    encoding=encoding,
                    content=content,
                )
            )


def _language(name: str, include: list[str]) -> str | None:
    if name in include and name in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[name]
    suffix = Path(name).suffix.lower()
    if suffix in include and suffix in LANGUAGE_BY_EXTENSION:
        return LANGUAGE_BY_EXTENSION[suffix]
    if name in include:
        return suffix.lstrip(".") or name.lower()
    if suffix and suffix in include:
        return suffix.lstrip(".")
    return None


def _decode(data: bytes) -> tuple[str, str]:
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a "/"-separated glob ("**" crosses folders, "*" does not) to a regex."""
    parts = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts))
