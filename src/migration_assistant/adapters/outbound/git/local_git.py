"""Local Git adapter: checks out one stage of the reference source (Issue #17).

Git is run with argument lists only, with hooks disabled. Nothing is ever
written inside ``config.source``; all writes go to the workspace copy.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from migration_assistant.domain.checkout import (
    CheckoutError,
    CheckoutResult,
    ComponentCheckout,
    ComponentNotInStageError,
    GitNotInstalledError,
    SourceNotFoundError,
    SubmoduleError,
    UnknownStageError,
)
from migration_assistant.domain.reference_source import ReferenceSourceConfig

UMBRELLA_DIR = "legacy-example-stages"


class LocalGitAdapter:
    """Implements the GitRepo port using the git command line."""

    def checkout(self, config: ReferenceSourceConfig) -> CheckoutResult:
        source = _resolve_source(config.source)
        if shutil.which("git") is None:
            raise GitNotInstalledError("git was not found on PATH")

        workspace = config.workspace.resolve()
        umbrella = workspace / UMBRELLA_DIR

        with tempfile.TemporaryDirectory(prefix="empty-hooks-") as hooks:
            git = _Git(hooks, source)

            if umbrella.exists():
                git.run("fetch", "--tags", "origin", cwd=umbrella)
            else:
                workspace.mkdir(parents=True, exist_ok=True)
                git.run("clone", "--no-checkout", str(source), str(umbrella), cwd=workspace)

            umbrella_ref = f"refs/tags/{config.stage}"
            umbrella_sha = self._resolve_stage(git, umbrella, umbrella_ref, config.stage)
            git.run("checkout", "--force", "--detach", umbrella_sha, cwd=umbrella)

            pinned = _read_stage_components(umbrella, config.stage)
            for name in config.components:
                if name not in pinned:
                    available = ", ".join(sorted(pinned)) or "none"
                    raise ComponentNotInStageError(
                        f"Component '{name}' is not in stage '{config.stage}' "
                        f"(available: {available})"
                    )

            members = [
                self._checkout_component(git, config, source, umbrella, name, pinned[name])
                for name in config.components
            ]

        return CheckoutResult(
            stage=config.stage,
            umbrella_ref=umbrella_ref,
            umbrella_commit_sha=umbrella_sha,
            workspace=workspace,
            members=members,
        )

    def _resolve_stage(self, git: "_Git", umbrella: Path, ref: str, stage: str) -> str:
        try:
            return git.run("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=umbrella)
        except CheckoutError:
            raise UnknownStageError(f"Unknown stage '{stage}': no tag '{stage}' in the source") from None

    def _checkout_component(
        self,
        git: "_Git",
        config: ReferenceSourceConfig,
        source: Path,
        umbrella: Path,
        name: str,
        pinned: dict,
    ) -> ComponentCheckout:
        path = f"components/{name}"
        expected = str(pinned.get("sha", "")).lower()
        tag = pinned.get("tag")
        if not expected or not tag:
            raise SubmoduleError(f"stage.json has no 'tag' and 'sha' for component '{name}'")

        url_key = f"submodule.{path}.url"
        try:
            declared = git.run(
                "config", "-f", ".gitmodules", "--get", url_key, cwd=umbrella
            )
        except CheckoutError:
            raise SubmoduleError(f"Submodule '{path}' is not declared in .gitmodules") from None

        local_source = source / "components" / name
        if not local_source.exists():
            raise SubmoduleError(f"Submodule '{name}' is missing in the source: {local_source}")

        git.run("config", url_key, str(local_source), cwd=umbrella)
        git.run(
            "-c", "protocol.file.allow=always",
            "submodule", "update", "--init", "--checkout", "--", path,
            cwd=umbrella,
        )

        component_dir = umbrella / path
        if not component_dir.exists():
            raise SubmoduleError(f"Submodule '{path}' was not checked out in {umbrella}")

        actual = git.run("rev-parse", "HEAD", cwd=component_dir).lower()
        if actual != expected:
            raise SubmoduleError(
                f"Submodule '{name}' is at {actual}, but stage.json pins {expected}"
            )

        repo_id = declared.rstrip("/").rsplit("/", 1)[-1]
        return ComponentCheckout(
            repo_id=repo_id,
            ref=f"refs/tags/{tag}",
            commit_sha=actual,
            local_path=component_dir,
            public_url=f"{config.public_url}/{repo_id}",
        )


class _Git:
    """Runs git with hooks disabled, and never inside the read-only source."""

    def __init__(self, hooks_dir: str, source: Path) -> None:
        self._hooks_dir = hooks_dir
        self._source = source

    def run(self, *args: str, cwd: Path) -> str:
        if _is_inside(cwd.resolve(), self._source):
            raise CheckoutError(f"Refusing to run git inside the source: {cwd}")
        command = ["git", "-c", f"core.hooksPath={self._hooks_dir}", *args]
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                env=_git_env(),
            )
        except FileNotFoundError:
            raise GitNotInstalledError("git was not found on PATH") from None
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise CheckoutError(f"git {' '.join(args)} failed: {detail}") from error
        return completed.stdout.strip()


def _git_env() -> dict:
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def _is_inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _resolve_source(value: str) -> Path:
    if "://" in value:
        raise SourceNotFoundError(f"Only a local path is supported as source, got: {value}")
    source = Path(value).resolve()
    if not source.is_dir():
        raise SourceNotFoundError(f"Source not found: {source}")
    if not (source / ".git").exists():
        raise SourceNotFoundError(f"Source is not a Git repository: {source}")
    return source


def _read_stage_components(umbrella: Path, stage: str) -> dict:
    stage_file = umbrella / "stage.json"
    try:
        data = json.loads(stage_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UnknownStageError(f"stage.json not found at stage '{stage}'") from None
    except json.JSONDecodeError as error:
        raise UnknownStageError(f"stage.json at stage '{stage}' is not valid JSON: {error}") from error
    components = data.get("komponenten")
    if not isinstance(components, dict):
        raise UnknownStageError(f"stage.json at stage '{stage}' has no 'komponenten'")
    return components
