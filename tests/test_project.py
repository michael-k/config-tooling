"""Checks of the repository's layout: PRJ-1, PRJ-2."""

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {"incus": "incus", "spec-check": "spec_check", "deploy-gate": "deploy_gate"}


def _project(directory: str) -> dict:
    return tomllib.loads((ROOT / directory / "pyproject.toml").read_text())


@pytest.mark.parametrize("directory", PACKAGES)
def test_each_package_builds_on_its_own(directory):
    """PRJ-1: each directory is a package of its own, built from its own `src/`."""
    project = _project(directory)
    assert project["project"]["name"] == directory
    assert project["build-system"]["build-backend"] == "uv_build"
    assert (ROOT / directory / "src" / PACKAGES[directory] / "__init__.py").is_file()


@pytest.mark.parametrize("directory", PACKAGES)
def test_each_package_installs_from_its_directory_alone(directory):
    """PRJ-2: a path dependency on the directory needs nothing outside it."""
    project = _project(directory)
    assert "sources" not in project.get("tool", {}).get("uv", {})
    for requirement in project["project"].get("dependencies", []):
        assert "@" not in requirement, f"{requirement} is not an index dependency"

