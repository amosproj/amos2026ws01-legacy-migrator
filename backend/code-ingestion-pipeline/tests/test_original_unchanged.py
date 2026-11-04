"""Acceptance criterion 5: the original reference repository is not modified."""

import subprocess
from pathlib import Path

from conftest import git, tree_hashes
from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources


def _snapshot(source):
    return {
        "head": git(source, "rev-parse", "HEAD"),
        "status": git(source, "status", "--porcelain"),
        "submodule_head": git(source / "components" / "monolith", "rev-parse", "HEAD"),
        "submodule_status": git(source / "components" / "monolith", "status", "--porcelain"),
        "refs": git(source, "for-each-ref"),
        "files": tree_hashes(source),
    }


def test_source_is_identical_before_and_after_checkout_and_load(reference):
    before = _snapshot(reference.source)

    for stage in ("step-00", "step-04a", "step-00"):
        config = reference.config(stage=stage)
        load_sources(config, LocalGitAdapter().checkout(config))

    assert _snapshot(reference.source) == before


def test_no_git_command_runs_inside_the_source_and_hooks_are_disabled(reference, monkeypatch):
    source = reference.source.resolve()
    calls = []
    real_run = subprocess.run

    def spy(command, *args, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    config = reference.config()
    load_sources(config, LocalGitAdapter().checkout(config))

    assert calls
    for command, cwd in calls:
        assert command[:2] == ["git", "-c"]
        assert command[2].startswith("core.hooksPath=")
        resolved = Path(cwd).resolve()
        assert resolved != source and source not in resolved.parents
