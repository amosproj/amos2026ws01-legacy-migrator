"""Configuration of the reference source (Issue #17)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ConfigError(Exception):
    """The reference source configuration is missing, unreadable or invalid."""


class ReferenceSourceConfig(BaseModel):
    """Where the reference system is read from and which part of it is analysed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    public_url: str
    # Opaque key: only a safety check (not empty, no leading "-", limited characters).
    stage: str = Field(pattern=r"^[A-Za-z0-9._/][A-Za-z0-9._/-]*$")
    components: list[str] = Field(min_length=1)
    workspace: Path
    include: list[str] = Field(min_length=1)
    exclude: list[str]
    max_file_size_kb: int = Field(default=1024, gt=0)

    @field_validator("public_url")
    @classmethod
    def _public_url_is_http(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("must start with https:// or http://")
        return value.rstrip("/")

    @field_validator("components", "include", "exclude")
    @classmethod
    def _entries_are_not_blank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("entries must not be empty")
        return values


def load_config(path: str | Path) -> ReferenceSourceConfig:
    """Read and validate the YAML file at ``path``.

    Raises ConfigError with a message that names the file and the field.
    """
    path = Path(path)
    name = path.as_posix()

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {name}") from None
    except OSError as error:
        raise ConfigError(f"Cannot read {name}: {error}") from error

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {name}: {error}") from error

    if not isinstance(data, dict):
        raise ConfigError(f"Expected a mapping of fields in {name}")

    try:
        return ReferenceSourceConfig(**data)
    except ValidationError as error:
        problems = [_describe(problem, name) for problem in error.errors()]
        raise ConfigError("\n".join(problems)) from error


def _describe(problem: dict, name: str) -> str:
    field = ".".join(str(part) for part in problem["loc"])
    if problem["type"] == "missing":
        return f"Missing field '{field}' in {name}"
    if problem["type"] == "extra_forbidden":
        return f"Unknown field '{field}' in {name}"
    return f"Invalid value for field '{field}' in {name}: {problem['msg']}"
