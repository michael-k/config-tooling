"""Builds the repositories the gate's tests run in.

Each is a consumer in miniature under `tmp_path`: a git work tree with a
`pyproject.toml` holding `[tool.deploy-gate]`, a `roles/` directory as its
deployment code, a file outside it, and a `conftest.py` that names the
plugin. Git's global and system configuration are switched off, so the
excludes of whoever runs the tests change nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

GATE_TABLE = '[tool.deploy-gate]\ncode = ["roles", "site.yml"]\nmarker = "vm"\n'

# A suite with two tests of the `vm` tier and one test outside it.
SUITE = """\
import pytest

@pytest.mark.vm
def test_first():
    pass

@pytest.mark.vm
def test_second():
    pass

def test_outside_the_tier():
    pass
"""


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


class Repo:
    def __init__(self, root: Path):
        self.root = root

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(self.root), *args],
            check=True, capture_output=True,
        )

    def stamp(self) -> str | None:
        path = self.root / ".integration-passed"
        return path.read_text() if path.is_file() else None

    def pytest(self, *args: str, plugin: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a pytest session in the repository, as its own suite would run."""
        self.write("conftest.py", 'pytest_plugins = ["deploy_gate.plugin"]\n' if plugin else "")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
        return subprocess.run(
            [sys.executable, "-m", "pytest", *args],
            cwd=self.root, env=env, capture_output=True, text=True, check=False,
        )


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """A git work tree whose deployment code is `roles/` and `site.yml`."""
    repo = Repo(tmp_path / "repo")
    repo.root.mkdir()
    repo.git("init", "-q")
    repo.write(
        "pyproject.toml",
        '[project]\nname = "x"\n\n[tool.pytest.ini_options]\nmarkers = ["vm: the tier"]\n\n'
        + GATE_TABLE,
    )
    repo.write(".gitignore", "*.cache\n.pytest_cache/\n__pycache__/\n.integration-passed\n")
    repo.write("site.yml", "- hosts: all\n")
    repo.write("roles/web/tasks/main.yml", "- ansible.builtin.ping:\n")
    repo.write("README.md", "outside the code\n")
    repo.write("tests/test_suite.py", SUITE)
    return repo
