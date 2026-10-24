"""Builds the spec trees the checker's tests run against (TEST-2).

Every tree lives under `tmp_path`, and every requirement ID in it uses a
prefix this repository's registry does not hold (`FOO`, `BAR`), so nothing
here is read as a citation of this repository's own requirements.

Every tree is a git work tree, because the scan asks git what it ignores.
Git's global and system configuration are switched off, so the
excludes of whoever runs the tests change nothing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from spec_check.cli import main

Rows = dict[str, str]


def requirements_md(body: str, claims: str = "none") -> str:
    """A `requirements.md` with every mandatory section and `body` as its requirements."""
    return (
        "# X — Requirements\n\n"
        "## Purpose\n\np\n\n"
        "## Scope\n\ns\n\n"
        f"## Security invariants\n\n**Allowances claimed:** {claims}\n\n"
        f"## Requirements\n\n{body}"
    )


def design_md(rows: Rows) -> str:
    """A `design.md` with every mandatory section and `rows` as its implementation map."""
    table = "".join(f"| `{path}` | {ids} |\n" for path, ids in rows.items())
    return (
        "# X — Design\n\n## Approach\n\na\n\n"
        f"## Implementation map\n\n| Path | Realises |\n|---|---|\n{table}\n"
        "## Key decisions\n\nk\n"
    )


def requirement(req_id: str, title: str = "A rule", annotation: str = "") -> str:
    """One requirement heading and body, optionally with a traceability annotation."""
    extra = f"\n**Traceability:** {annotation} — because.\n" if annotation else ""
    return f"### {req_id} — {title}\n\nTHE Thing SHALL do it.\n{extra}\n"


class Tree:
    """A spec tree under construction in a temporary directory."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = root
        self._monkeypatch = monkeypatch

    requirement = staticmethod(requirement)
    requirements_md = staticmethod(requirements_md)
    design_md = staticmethod(design_md)

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text()

    def git(self, *args: str) -> None:
        git(self.root, *args)

    def registry(self, prefixes: dict[str, str]) -> None:
        rows = "".join(f"| `{p}` | `{s}` | `src/` |\n" for p, s in prefixes.items())
        self.write(
            "specs/README.md",
            f"# Specs\n\n| Prefix | Spec directory | Implemented by |\n|---|---|---|\n{rows}",
        )

    def scan(self, *globs: str) -> None:
        listed = ", ".join(f'"{glob}"' for glob in globs)
        self.write(
            "pyproject.toml", f'[project]\nname = "x"\n\n[tool.spec-check]\nscan = [{listed}]\n'
        )

    def spec(self, name: str, body: str, rows: Rows, claims: str = "none") -> None:
        self.write(f"specs/{name}/requirements.md", requirements_md(body, claims))
        self.write(f"specs/{name}/design.md", design_md(rows))

    def snapshot(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in sorted(self.root.rglob("*"))
            if p.is_file()
        }

    def run(self, *args: str) -> int:
        self._monkeypatch.chdir(self.root)
        return main(list(args))


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Tree:
    """An empty git work tree under `tmp_path`."""
    git(tmp_path, "init", "-q")
    return Tree(tmp_path, monkeypatch)


@pytest.fixture
def clean_tree(tree: Tree) -> Tree:
    """A tree with one spec, `foo`, whose one requirement `src/foo.py` cites and maps."""
    tree.registry({"FOO": "foo"})
    tree.scan("src/**/*.py", "docs/**/*.md")
    tree.spec("foo", requirement("FOO-1"), {"src/foo.py": "FOO-1"})
    tree.write("src/foo.py", "# FOO-1\n")
    return tree

