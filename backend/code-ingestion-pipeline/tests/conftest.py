"""Shared fixtures: a tiny fake reference setup built with real git."""

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from migration_assistant.domain.reference_source import ReferenceSourceConfig, load_config

PUBLIC_URL = "https://example.test/org"
INCLUDE = [".java", ".xml", ".properties", ".sql", ".conf", ".yaml", ".yml", ".sh", "Dockerfile"]
EXCLUDE = ["**/.settings/**", "**/*.png"]
MAX_FILE_SIZE_KB = 1

LATIN1_SQL = "-- Größe\nSELECT 'ä';\n".encode("latin-1")


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.longpaths=true", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def extended(path: Path) -> Path:
    """Add the Windows extended-length prefix so paths over 260 characters work."""
    text = str(path.resolve())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return Path("\\\\?\\" + text)
    return path


# A folder chain whose relative path alone is longer than the 260-character Windows limit.
DEEP_DIR = "/".join(["deeply_nested_folder"] * 14)
DEEP_FILE = f"{DEEP_DIR}/Deep.java"


def tree_hashes(root: Path) -> dict[str, str]:
    """SHA-256 of every file below ``root``, ignoring .git folders and files."""
    hashes = {}
    for directory, dirnames, filenames in os.walk(extended(root)):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            if name == ".git":
                continue
            path = Path(directory) / name
            hashes[path.relative_to(extended(root)).as_posix()] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return hashes


@dataclass(frozen=True)
class Origin:
    """The fake 'GitHub organisation' on disk."""

    umbrella: Path
    component: Path
    sha_step_00: str
    sha_step_04a: str


@dataclass(frozen=True)
class Reference:
    origin: Origin
    config_path: Path
    workspace: Path

    @property
    def source(self) -> Path:
        return self.origin.umbrella

    def config(self, **overrides) -> ReferenceSourceConfig:
        base = load_config(self.config_path)
        return ReferenceSourceConfig.model_validate({**base.model_dump(), **overrides})


def _write(root: Path, name: str, data: bytes | str) -> None:
    path = extended(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def _commit(repo: Path, message: str, tag: str) -> str:
    git(repo, "add", "--all")
    git(repo, "commit", "-q", "-m", message)
    git(repo, "tag", tag)
    return git(repo, "rev-parse", "HEAD")


def _stage_json(stage: str, sha: str) -> str:
    return (
        f'{{\n  "id": "{stage}",\n  "komponenten": {{\n    "monolith": {{\n'
        f'      "tag": "{stage}",\n      "sha": "{sha}"\n    }}\n  }}\n}}\n'
    )


@pytest.fixture(scope="session")
def git_environment(tmp_path_factory):
    """Run git without the user's configuration, so tests behave the same everywhere."""
    empty_config = tmp_path_factory.mktemp("gitconfig") / "config"
    empty_config.write_text("")
    values = {
        "GIT_CONFIG_GLOBAL": str(empty_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.test",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.test",
    }
    with pytest.MonkeyPatch.context() as patch:
        for key, value in values.items():
            patch.setenv(key, value)
        yield


@pytest.fixture(autouse=True)
def _isolated_git(git_environment):
    """Make every test use the isolated git environment."""


@pytest.fixture(scope="session")
def origin(tmp_path_factory, git_environment) -> Origin:
    org = tmp_path_factory.mktemp("org")

    component = org / "legacy-example-monolith"
    component.mkdir()
    git(component, "init", "-q", "-b", "main")
    _write(component, "src/Main.java", "class Main {}\n")
    _write(component, "pom.xml", "<project/>\n")
    _write(component, "logo.png", b"\x89PNG\r\n\x1a\n")
    _write(component, ".settings/config.xml", "<settings/>\n")
    _write(component, "legacy.sql", LATIN1_SQL)
    _write(component, "big.xml", "<a>" + "x" * 2048 + "</a>")
    _write(component, "zeros.xml", b"<a>\x00</a>")
    _write(component, "notes.txt", "just notes\n")
    sha_00 = _commit(component, "step-00", "step-00")

    _write(component, "src/Main.java", "class Main { int version = 4; }\n")
    _write(component, "src/Extra.java", "class Extra {}\n")
    _write(component, "Dockerfile", "FROM scratch\n")
    _write(component, DEEP_FILE, "class Deep {}\n")
    sha_04a = _commit(component, "step-04a", "step-04a")

    umbrella = org / "legacy-example-stages"
    umbrella.mkdir()
    git(umbrella, "init", "-q", "-b", "main")
    git(
        umbrella, "-c", "protocol.file.allow=always",
        "submodule", "add", "-q", str(component), "components/monolith",
    )
    git(umbrella, "config", "-f", ".gitmodules",
        "submodule.components/monolith.url", "../legacy-example-monolith")

    git(umbrella / "components" / "monolith", "checkout", "-q", sha_00)
    _write(umbrella, "stage.json", _stage_json("step-00", sha_00))
    _commit(umbrella, "step-00", "step-00")

    git(umbrella / "components" / "monolith", "checkout", "-q", sha_04a)
    _write(umbrella, "stage.json", _stage_json("step-04a", sha_04a))
    _commit(umbrella, "step-04a", "step-04a")

    return Origin(umbrella=umbrella, component=component, sha_step_00=sha_00, sha_step_04a=sha_04a)


@pytest.fixture
def reference(origin, tmp_path) -> Reference:
    workspace = tmp_path / "workspace"
    config_path = tmp_path / "reference-source.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "source": str(origin.umbrella),
                "public_url": PUBLIC_URL,
                "stage": "step-00",
                "components": ["monolith"],
                "workspace": str(workspace),
                "include": INCLUDE,
                "exclude": EXCLUDE,
                "max_file_size_kb": MAX_FILE_SIZE_KB,
            }
        ),
        encoding="utf-8",
    )
    return Reference(origin=origin, config_path=config_path, workspace=workspace)
