"""Acceptance criterion 3: the loading process can be executed repeatedly."""

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources


def _run(config):
    return load_sources(config, LocalGitAdapter().checkout(config))


def test_two_runs_give_identical_results(reference):
    config = reference.config()

    first = _run(config)
    second = _run(config)

    assert first == second
    assert first.model_dump_json(by_alias=True) == second.model_dump_json(by_alias=True)


def test_later_stage_in_same_workspace_gives_that_stage(reference):
    origin = reference.origin

    first = _run(reference.config(stage="step-00"))
    second = _run(reference.config(stage="step-04a"))

    assert first.checkout.members[0].commit_sha == origin.sha_step_00
    assert second.checkout.members[0].commit_sha == origin.sha_step_04a
    assert second.checkout.umbrella_commit_sha != first.checkout.umbrella_commit_sha

    files = {file.path: file for file in second.files}
    assert "version = 4" in files["src/Main.java"].content
    assert "src/Extra.java" in files
    assert files["Dockerfile"].language == "dockerfile"
    assert all(file.stage == "step-04a" for file in second.files)
    assert all(file.commit_sha == origin.sha_step_04a for file in second.files)


def test_going_back_to_earlier_stage_works(reference):
    _run(reference.config(stage="step-04a"))

    result = _run(reference.config(stage="step-00"))

    paths = {file.path for file in result.files}
    assert "src/Extra.java" not in paths
    assert "Dockerfile" not in paths
