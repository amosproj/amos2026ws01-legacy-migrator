"""Optional integration test against the real local copy of the reference source.

Run with: REFERENCE_SOURCE=<path to legacy-example-stages> pytest tests/test_real_reference_source.py
"""

import os
from pathlib import Path

import pytest

from migration_assistant.adapters.outbound.git.local_git import LocalGitAdapter
from migration_assistant.adapters.outbound.git.source_loader import load_sources
from migration_assistant.domain.reference_source import ReferenceSourceConfig, load_config

pytestmark = pytest.mark.skipif(
    not os.environ.get("REFERENCE_SOURCE"),
    reason="set REFERENCE_SOURCE to the local legacy-example-stages path to run this test",
)


def test_step_00_loads_from_real_source(tmp_path):
    base = load_config(Path(__file__).resolve().parents[1] / "config" / "reference-source.yaml")
    config = ReferenceSourceConfig.model_validate(
        {
            **base.model_dump(),
            "source": os.environ["REFERENCE_SOURCE"],
            "workspace": tmp_path / "workspace",
            "stage": "step-00",
        }
    )

    result = load_sources(config, LocalGitAdapter().checkout(config))

    assert result.checkout.members[0].repo_id == "legacy-example-monolith"
    assert len(result.checkout.umbrella_commit_sha) == 40
    assert result.counts.loaded > 0
    assert "java" in result.counts.loaded_by_language
