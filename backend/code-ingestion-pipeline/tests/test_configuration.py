"""Acceptance criterion 1: the reference source can be configured as an input source."""

from pathlib import Path

import pytest
import yaml

from migration_assistant.domain.reference_source import (
    ConfigError,
    default_config_path,
    load_config,
)


def _rewrite(reference, **changes):
    data = yaml.safe_load(reference.config_path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            data.pop(key)
        else:
            data[key] = value
    reference.config_path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_valid_config_loads(reference):
    config = load_config(reference.config_path)

    assert config.stage == "step-00"
    assert config.components == ["monolith"]
    assert config.public_url == "https://example.test/org"
    assert config.max_file_size_kb == 1


def test_real_project_config_loads():
    config = load_config("config/reference-source.yaml")

    assert config.source == "https://github.com/legacy-modernization-example/legacy-example-stages"

    assert config.max_file_size_kb == 1024


def test_local_override_is_preferred_when_it_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_config_path() == Path("config/reference-source.yaml")

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "reference-source.local.yaml").write_text(
        "source: x\n", encoding="utf-8"
    )

    assert default_config_path() == Path("config/reference-source.local.yaml")


def test_missing_field_is_reported_by_name(reference):
    _rewrite(reference, stage=None)

    with pytest.raises(ConfigError, match=r"Missing field 'stage' in .*reference-source\.yaml"):
        load_config(reference.config_path)


@pytest.mark.parametrize("stage", ["", "-x", "--help", "step 1", "a;b"])
def test_invalid_stage_is_rejected(reference, stage):
    _rewrite(reference, stage=stage)

    with pytest.raises(ConfigError, match="Invalid value for field 'stage'"):
        load_config(reference.config_path)


@pytest.mark.parametrize("stage", ["step-00", "step-04a", "step-08x", "release/1.0"])
def test_stage_is_an_opaque_key(reference, stage):
    _rewrite(reference, stage=stage)

    assert load_config(reference.config_path).stage == stage


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match=r"Config file not found: .*does-not-exist\.yaml"):
        load_config(tmp_path / "does-not-exist.yaml")
