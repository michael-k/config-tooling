"""When a session records: GATE-4, GATE-5, GATE-8, GATE-9.

Each test runs a real pytest session in a repository built by `repo`, the
way the consumer's own suite runs.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from deploy_gate.gate import fingerprint

pytestmark = pytest.mark.unit

CODE = ("roles", "site.yml")
PACKAGE = Path(__file__).resolve().parents[1]


def test_a_complete_clean_run_records_the_fingerprint(repo):
    """GATE-4"""
    result = repo.pytest()
    assert result.returncode == 0, result.stdout
    assert repo.stamp() == fingerprint(repo.root, CODE) + "\n"


@pytest.mark.parametrize("args", [[], ["-m", "vm"]], ids=["no marker", "the configured one"])
def test_selecting_the_whole_tier_records(repo, args):
    """GATE-5: no marker expression, or the configured marker, selects the whole tier."""
    assert repo.pytest(*args).returncode == 0
    assert repo.stamp() is not None


@pytest.mark.parametrize(
    "extra, outcome",
    [
        ("@pytest.mark.vm\ndef test_x():\n    pytest.skip('no vm')\n", 0),
        ("@pytest.mark.vm\ndef test_x():\n    assert False\n", 1),
        (
            "@pytest.fixture\ndef broken():\n    raise RuntimeError\n\n"
            "@pytest.mark.vm\ndef test_x(broken):\n    pass\n",
            1,
        ),
        ("def test_x():\n    assert False\n", 1),
    ],
    ids=["skipped", "failed", "errored", "other test failed"],
)
def test_a_run_that_is_not_clean_records_nothing(repo, extra, outcome):
    """GATE-4"""
    repo.write("tests/test_extra.py", f"import pytest\n\n{extra}")
    assert repo.pytest().returncode == outcome
    assert repo.stamp() is None


def test_a_run_without_integration_tests_records_nothing(repo):
    """GATE-4"""
    repo.write("tests/test_suite.py", "def test_outside_the_tier():\n    pass\n")
    assert repo.pytest().returncode == 0
    assert repo.stamp() is None


@pytest.mark.parametrize(
    "args",
    [
        ["tests/test_suite.py"],
        ["-k", "first"],
        ["--deselect", "tests/test_suite.py::test_second"],
        ["--ignore", "tests/other"],
        ["--ignore-glob", "*other*"],
        ["--lf"],
        ["--stepwise"],
        ["--sw-skip"],
        ["-m", "vm or not vm"],
        ["-m", "not vm"],
    ],
)
def test_a_narrowed_session_records_nothing(repo, args):
    """GATE-5: even when every test it ran passed."""
    assert repo.pytest(*args).returncode in (0, 5)
    assert repo.stamp() is None


def test_installing_the_package_activates_nothing(repo):
    """GATE-8: without the plugin named, a session neither reads the table nor records."""
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    assert repo.pytest(plugin=False).returncode == 0
    assert repo.stamp() is None


def test_the_package_declares_no_pytest_entry_point():
    """GATE-8"""
    project = tomllib.loads((PACKAGE / "pyproject.toml").read_text())
    assert "pytest11" not in project["project"].get("entry-points", {})


def test_a_missing_table_fails_the_session(repo):
    """GATE-1: a consumer that named the plugin gets an error, not silence."""
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    result = repo.pytest()
    assert result.returncode == 4
    assert "[tool.deploy-gate]" in result.stderr


def test_a_session_outside_a_work_tree_fails_instead_of_recording(repo):
    """GATE-9"""
    os.rename(repo.root / ".git", repo.root.parent / "moved.git")
    result = repo.pytest()
    assert result.returncode == 1
    assert "nothing recorded" in result.stdout
    assert repo.stamp() is None
