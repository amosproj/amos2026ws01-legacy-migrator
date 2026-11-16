"""Result of checking out the reference source locally (Issue #17)."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

COMMIT_SHA_PATTERN = r"^[0-9a-f]{40}([0-9a-f]{24})?$"


class CheckoutError(Exception):
    """The reference source could not be checked out."""


class SourceNotFoundError(CheckoutError):
    """The configured local source is missing or not a Git repository."""


class GitNotInstalledError(CheckoutError):
    """The git executable was not found."""


class UnknownStageError(CheckoutError):
    """The configured stage is not a tag of the umbrella repository."""


class ComponentNotInStageError(CheckoutError):
    """A configured component is not part of the selected stage."""


class SubmoduleError(CheckoutError):
    """A component submodule is missing, cannot be initialised or is at the wrong commit."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)


class ComponentCheckout(_Model):
    """One component repository checked out at the commit pinned by the stage."""

    repo_id: str
    origin: Literal["legacy"] = "legacy"
    ref: str
    commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    local_path: Path
    public_url: str


class CheckoutResult(_Model):
    """The umbrella repository at one stage, with its selected components."""

    stage: str
    umbrella_ref: str
    umbrella_commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    workspace: Path
    members: list[ComponentCheckout]
