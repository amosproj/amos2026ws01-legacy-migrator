"""Port for checking out the reference source (Issue #17)."""

from typing import Protocol

from migration_assistant.domain.checkout import CheckoutResult
from migration_assistant.domain.reference_source import ReferenceSourceConfig


class GitRepo(Protocol):
    """Prepares a local, pinned copy of the configured reference source."""

    def checkout(self, config: ReferenceSourceConfig) -> CheckoutResult:
        """Check out ``config.stage`` and its components; raise CheckoutError on failure."""
        ...
