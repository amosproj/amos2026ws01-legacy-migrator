"""Acceptance criterion 4: errors during loading are reported clearly."""

import subprocess

import pytest

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.bootstrap import cli
from migration_assistant.domain.checkout import (
    CheckoutError,
    ComponentNotInStageError,
    SourceNotFoundError,
    UnknownStageError,
)
from migration_assistant.domain.sources import SourceLoadError


def test_unknown_stage(reference):
    with pytest.raises(UnknownStageError, match="Unknown stage 'step-99'"):
        LocalGitAdapter().checkout(reference.config(stage="step-99"))


def test_component_not_in_stage(reference):
    with pytest.raises(ComponentNotInStageError, match="'catalog-service' is not in stage 'step-00'"):
        LocalGitAdapter().checkout(reference.config(components=["catalog-service"]))


def test_source_not_found(reference, tmp_path):
    with pytest.raises(SourceNotFoundError, match="Source not found"):
        LocalGitAdapter().checkout(reference.config(source=str(tmp_path / "missing")))


@pytest.mark.parametrize(
    "source",
    ["http://github.com/x/y", "ssh://git@github.com/x/y", "file:///tmp/x", "ext::sh -c id", "https://user:secret@github.com/x/y"],
)
def test_unsupported_source_urls_are_refused(reference, source):
    with pytest.raises((SourceNotFoundError,)):
        LocalGitAdapter().checkout(reference.config(source=source))


def test_https_source_clones_over_https_only_without_network_in_this_test(reference, monkeypatch):
    url = "https://github.com/legacy-modernization-example/legacy-example-stages"
    commands = []

    def fake_run(command, *args, **kwargs):
        commands.append(command)
        raise subprocess.CalledProcessError(128, command, stderr="blocked in test")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(CheckoutError, match="blocked in test"):
        LocalGitAdapter().checkout(reference.config(source=url))

    (clone,) = commands
    assert clone[0] == "git"
    assert "protocol.allow=never" in clone and "protocol.https.allow=always" in clone
    assert any(part.startswith("core.hooksPath=") for part in clone)
    assert "core.longpaths=true" in clone and "core.fsmonitor=false" in clone
    assert clone[clone.index("clone") :][:3] == ["clone", "--no-checkout", "--"]
    assert clone[clone.index("--") + 1] == url
    assert not any("file.allow" in part for part in clone)


def test_workspace_from_another_source_is_not_reused(reference, monkeypatch):
    LocalGitAdapter().checkout(reference.config())  # creates the workspace from the local source
    commands = []

    def forbidden(command, *args, **kwargs):
        commands.append(command)
        raise AssertionError("no clone or fetch may happen")

    real_run = subprocess.run

    def guarded(command, *args, **kwargs):
        if "fetch" in command or "clone" in command:
            return forbidden(command)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded)

    with pytest.raises(CheckoutError, match="created from a different source"):
        LocalGitAdapter().checkout(
            reference.config(source="https://github.com/legacy-modernization-example/legacy-example-stages")
        )
    assert commands == []


def test_dirty_component_in_workspace_is_refused(reference):
    config = reference.config()
    result = LocalGitAdapter().checkout(config)
    changed = result.members[0].local_path / "src" / "Main.java"
    changed.write_text("class Main { /* edited */ }\n", encoding="utf-8")

    with pytest.raises(SourceLoadError, match="has local changes"):
        load_sources(config, result)


def test_cli_success_returns_zero(reference, capsys):
    code = cli.main(["--config", str(reference.config_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert "stage: step-00" in captured.out
    assert "files loaded: 3" in captured.out


def test_cli_error_is_a_single_line_with_exit_code_one(reference, capsys):
    code = cli.main(["--config", str(reference.config_path), "--stage", "step-99"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0] == "ERROR: Unknown stage 'step-99': no tag 'step-99' in the source"


def test_cli_missing_config_is_a_single_error_line(tmp_path, capsys):
    code = cli.main(["--config", str(tmp_path / "does-not-exist.yaml")])

    lines = capsys.readouterr().err.splitlines()
    assert code == 1
    assert len(lines) == 1 and lines[0].startswith("ERROR: Config file not found")


def test_cli_uses_local_override_file_when_present(reference, tmp_path, monkeypatch, capsys):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "reference-source.local.yaml").write_text(
        reference.config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    code = cli.main([])

    out = capsys.readouterr().out
    assert code == 0
    assert "config: config/reference-source.local.yaml" in out


def test_cli_override_stage_04a(reference, capsys):
    code = cli.main(["--config", str(reference.config_path), "--stage", "step-04a"])

    assert code == 0
    assert "stage: step-04a" in capsys.readouterr().out


def test_cli_out_inside_workspace_is_refused(reference, capsys):
    out = reference.workspace / "out.jsonl"

    code = cli.main(["--config", str(reference.config_path), "--out", str(out)])

    lines = capsys.readouterr().err.splitlines()
    assert code == 1
    assert len(lines) == 1 and "must not be inside the workspace" in lines[0]
    assert not out.exists()


def test_cli_out_inside_source_is_refused(reference, capsys):
    out = reference.source / "out.jsonl"

    code = cli.main(["--config", str(reference.config_path), "--out", str(out)])

    assert code == 1
    assert "must not be inside the source repository" in capsys.readouterr().err
    assert not out.exists()


def test_cli_writes_jsonl_with_camel_case(reference, tmp_path, capsys):
    out = tmp_path / "out" / "files.jsonl"

    code = cli.main(["--config", str(reference.config_path), "--out", str(out)])

    import json

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert code == 0
    assert [row["path"] for row in rows] == ["legacy.sql", "pom.xml", "src/Main.java"]
    assert {"repoId", "commitSha", "contentSha256", "sizeBytes", "githubUrl"} <= set(rows[0])
