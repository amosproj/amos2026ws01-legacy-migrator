"""Mock repository list for the frontend repository picker (ticket #27 support).

Real repository loading is ticket #17 ("Load Reference Repository"). This stub
returns the two reference repositories of the synthetic migration example so
the vertical slice can be tested end to end.
"""

from .schemas import Repository

_MOCK_REPOSITORIES = [
    Repository(
        id=1,
        provider="github",
        provider_label="GitHub",
        full_name="IBM/application-modernization-javaee-quarkus",
        description="Synthetic reference system (legacy monolith, migration stages)",
        default_branch="main",
        is_private=False,
    ),
    Repository(
        id=2,
        provider="github",
        provider_label="GitHub",
        full_name="amosproj/amos2026ws01-legacy-migrator",
        description="SunsetTracker prototype repository",
        default_branch="main",
        is_private=False,
    ),
]


def list_repositories() -> list[Repository]:
    return list(_MOCK_REPOSITORIES)
