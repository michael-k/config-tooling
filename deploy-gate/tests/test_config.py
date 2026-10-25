"""The consumer names the code and the marker: GATE-1, GATE-2."""

from __future__ import annotations

import pytest

from deploy_gate.config import Config, ConfigError, load_config

pytestmark = pytest.mark.unit


def test_code_and_marker_are_read(repo):
    """GATE-1, GATE-2"""
    assert load_config(repo.root) == Config(code=("roles", "site.yml"), marker="vm")


@pytest.mark.parametrize(
    "table, complaint",
    [
        ("", r"no \[tool.deploy-gate\] table"),
        ('[tool.deploy-gate]\nmarker = "vm"\n', "'code'"),
        ('[tool.deploy-gate]\ncode = []\nmarker = "vm"\n', "'code'"),
        ('[tool.deploy-gate]\ncode = "roles"\nmarker = "vm"\n', "'code'"),
        ('[tool.deploy-gate]\ncode = ["roles", ""]\nmarker = "vm"\n', "'code'"),
    ],
)
def test_the_code_list_has_no_default(repo, table, complaint):
    """GATE-1: a missing table or a missing, empty or malformed list is an error."""
    repo.write("pyproject.toml", '[project]\nname = "x"\n\n' + table)
    with pytest.raises(ConfigError, match=complaint):
        load_config(repo.root)


@pytest.mark.parametrize("marker", ["", 'marker = ""\n', "marker = 1\n"])
def test_the_marker_has_no_default(repo, marker):
    """GATE-2"""
    repo.write("pyproject.toml", f'[tool.deploy-gate]\ncode = ["roles"]\n{marker}')
    with pytest.raises(ConfigError, match="'marker'"):
        load_config(repo.root)


def test_a_missing_pyproject_is_an_error(tmp_path):
    """GATE-1"""
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(tmp_path)
