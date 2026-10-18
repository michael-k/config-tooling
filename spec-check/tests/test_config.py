"""Tests of the scan configuration.

Covers SPEC-15 (the scan is configured, never assumed) and SPEC-21 (a run
that cannot read its configuration exits with 2).
"""

from pathlib import Path

import pytest

from spec_check.config import ConfigError, expand_globs, load_scan_globs

pytestmark = pytest.mark.unit


def test_load_scan_globs_reads_the_table(tree) -> None:
    tree.scan("a.py", "src/**/*.py")

    assert load_scan_globs(tree.root) == ("a.py", "src/**/*.py")


@pytest.mark.parametrize(
    "pyproject",
    [
        None,
        '[project]\nname = "x"\n',
        "[tool.other]\nscan = ['a']\n",
        "[tool.spec-check]\n",
        "[tool.spec-check]\nscan = []\n",
        "[tool.spec-check]\nscan = 'a.py'\n",
        "[tool.spec-check]\nscan = [1]\n",
        "[tool.spec-check\n",
    ],
    ids=["no-file", "no-tool", "no-table", "no-scan", "empty", "string", "number", "bad-toml"],
)
def test_load_scan_globs_fails_without_a_usable_scan(tree, pyproject: str | None) -> None:
    if pyproject is not None:
        tree.write("pyproject.toml", pyproject)

    with pytest.raises(ConfigError):
        load_scan_globs(tree.root)


def test_expand_globs_reads_exactly_the_matched_files(tree) -> None:
    for name in ("a.py", "b.txt", "src/c.py", "src/d/e.py", "other/f.py"):
        tree.write(name, "x\n")
    (tree.root / "src" / "dir.py").mkdir()

    globs = ("a.py", "src/**/*.py", "src/c.py", "missing/*.py")

    assert expand_globs(tree.root, globs) == [
        Path("a.py"),
        Path("src/c.py"),
        Path("src/d/e.py"),
    ]


def test_a_tree_without_the_table_exits_2_and_names_it(clean_tree, capsys) -> None:
    clean_tree.write("pyproject.toml", '[project]\nname = "x"\n')

    assert clean_tree.run() == 2
    assert "[tool.spec-check]" in capsys.readouterr().err
    assert not (clean_tree.root / "specs" / "_traceability.md").exists()


def test_a_tree_with_an_empty_scan_exits_2(clean_tree, capsys) -> None:
    clean_tree.scan()

    assert clean_tree.run() == 2
    assert "scan" in capsys.readouterr().err


def test_a_configured_scan_reads_exactly_the_matched_files(clean_tree) -> None:
    clean_tree.write("lib/extra.py", "# FOO-1\n")

    assert clean_tree.run() == 0
    assert "lib/extra.py" not in clean_tree.read("specs/_traceability.md")

    clean_tree.scan("src/**/*.py", "lib/*.py")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1", "lib/extra.py": "FOO-1"}
    )

    assert clean_tree.run() == 0
    assert "`lib/extra.py`" in clean_tree.read("specs/_traceability.md")
