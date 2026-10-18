"""Tests of the command line.

Covers SPEC-17 (pending requirements are listed on every run), SPEC-18 (the
index is written after a clean full run, and nothing else), SPEC-19 (a stale
index fails a check run), SPEC-20 (`--spec` scopes the checks) and SPEC-21
(the exit status says what happened).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from spec_check.index import render_traceability
from spec_check.tree import Requirement

pytestmark = pytest.mark.unit

INDEX = "specs/_traceability.md"


# SPEC-17: the pending list.


@pytest.mark.parametrize("with_finding", [False, True])
def test_every_pending_requirement_is_printed(clean_tree, capsys, with_finding: bool) -> None:
    body = (
        clean_tree.requirement("FOO-1")
        + clean_tree.requirement("FOO-2", annotation="pending")
        + clean_tree.requirement("FOO-3", annotation="pending")
    )
    clean_tree.spec("foo", body, {"src/foo.py": "FOO-1"})
    if with_finding:
        clean_tree.write("src/foo.py", "# FOO-1 FOO-9\n")

    assert clean_tree.run() == (1 if with_finding else 0)
    assert "Pending (specified, not yet implemented): FOO-2, FOO-3" in capsys.readouterr().out


# SPEC-18: when the index is written.


def test_a_clean_full_run_writes_the_index_and_nothing_else(clean_tree, capsys) -> None:
    before = clean_tree.snapshot()

    assert clean_tree.run() == 0
    after = clean_tree.snapshot()

    assert "no findings" in capsys.readouterr().out
    assert set(after) - set(before) == {INDEX}
    assert {k: v for k, v in after.items() if k != INDEX} == before
    assert "| `FOO-1` | A rule | `src/foo.py` |" in clean_tree.read(INDEX)


def test_a_run_with_a_finding_leaves_the_index_untouched(clean_tree) -> None:
    clean_tree.write(INDEX, "sentinel\n")
    clean_tree.write("src/foo.py", "# FOO-1 FOO-9\n")

    assert clean_tree.run() == 1
    assert clean_tree.read(INDEX) == "sentinel\n"


def test_a_scoped_run_leaves_the_index_untouched(clean_tree, capsys) -> None:
    clean_tree.write(INDEX, "sentinel\n")

    assert clean_tree.run("--spec", "foo") == 0
    assert "no findings" in capsys.readouterr().out
    assert clean_tree.read(INDEX) == "sentinel\n"


def test_render_traceability_is_deterministic_and_marks_states() -> None:
    def req(n: int, **kwargs: bool) -> Requirement:
        return Requirement(f"FOO-{n}", "FOO", n, f"T{n}", "foo", Path(INDEX), **kwargs)

    requirements = [req(10), req(2, pending=True), req(1, withdrawn=True)]
    citations = {"FOO-10": {Path("b.py"), Path("a.py")}}

    first = render_traceability(requirements, citations)

    assert first == render_traceability(list(reversed(requirements)), citations)
    assert first.index("`FOO-1`") < first.index("`FOO-2`") < first.index("`FOO-10`")
    assert "| `FOO-1` | T1 (withdrawn) | — |" in first
    assert "| `FOO-2` | T2 (pending) | — |" in first
    assert "| `FOO-10` | T10 | `a.py`, `b.py` |" in first
    assert first.endswith("\n")


# SPEC-19: --check.


def test_check_passes_on_a_current_index_and_writes_nothing(clean_tree) -> None:
    assert clean_tree.run() == 0
    before = clean_tree.snapshot()

    assert clean_tree.run("--check") == 0
    assert clean_tree.snapshot() == before


def test_check_fails_on_a_stale_index_and_leaves_it_unchanged(clean_tree, capsys) -> None:
    assert clean_tree.run() == 0
    clean_tree.write("lib.py", "")
    clean_tree.scan("src/**/*.py", "lib.py")
    clean_tree.write("lib.py", "# FOO-1\n")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1", "lib.py": "FOO-1"}
    )
    stale = clean_tree.read(INDEX)
    capsys.readouterr()

    assert clean_tree.run("--check") == 1
    assert "[stale-index]" in capsys.readouterr().out
    assert clean_tree.read(INDEX) == stale


def test_check_fails_when_the_index_is_missing(clean_tree, capsys) -> None:
    assert clean_tree.run("--check") == 1
    assert "[stale-index]" in capsys.readouterr().out
    assert not (clean_tree.root / INDEX).exists()


def test_check_with_findings_writes_nothing(clean_tree) -> None:
    clean_tree.write("src/foo.py", "# FOO-1 FOO-9\n")
    before = clean_tree.snapshot()

    assert clean_tree.run("--check") == 1
    assert clean_tree.snapshot() == before


# SPEC-20: --spec.


@pytest.fixture
def two_specs(clean_tree):
    clean_tree.registry({"FOO": "foo", "BAR": "bar"})
    clean_tree.spec("bar", clean_tree.requirement("BAR-1"), {"src/bar.py": "BAR-1"})
    clean_tree.write("src/bar.py", "# BAR-1\n")
    return clean_tree


def test_a_scoped_run_reports_only_the_named_spec(two_specs, capsys) -> None:
    two_specs.write("src/foo.py", "nothing\n")
    two_specs.write("src/bar.py", "nothing\n")
    two_specs.spec("foo", two_specs.requirement("FOO-1"), {"src/foo.py": ""})
    two_specs.spec("bar", two_specs.requirement("BAR-1"), {"src/bar.py": ""})

    assert two_specs.run("--spec", "foo") == 1
    out = capsys.readouterr().out
    assert "[orphan-requirement] FOO-1" in out
    assert "BAR-1" not in out

    assert two_specs.run("--spec", "foo", "--spec", "bar") == 1
    out = capsys.readouterr().out
    assert "FOO-1" in out
    assert "BAR-1" in out


def test_a_scoped_check_compares_only_the_named_specs_index(two_specs, capsys) -> None:
    assert two_specs.run() == 0
    two_specs.write(INDEX, two_specs.read(INDEX).replace("`src/bar.py`", "`src/old.py`"))

    assert two_specs.run("--check", "--spec", "foo") == 0
    assert two_specs.run("--check", "--spec", "bar") == 1
    assert "[stale-index]" in capsys.readouterr().out


# SPEC-21: exit status.


def test_exit_status_is_0_when_clean(clean_tree) -> None:
    assert clean_tree.run() == 0


def test_exit_status_is_1_on_a_finding(clean_tree) -> None:
    clean_tree.write("src/foo.py", "nothing\n")

    assert clean_tree.run() == 1


def test_exit_status_is_2_for_an_unregistered_spec(clean_tree, capsys) -> None:
    assert clean_tree.run("--spec", "foo", "--spec", "nope") == 2
    assert "nope" in capsys.readouterr().err


def test_exit_status_is_2_without_a_registry(tree, capsys) -> None:
    tree.scan("src/*.py")

    assert tree.run() == 2
    assert "specs/README.md" in capsys.readouterr().err


def test_exit_status_is_2_for_an_unknown_option(clean_tree) -> None:
    with pytest.raises(SystemExit) as exit_info:
        clean_tree.run("--nope")

    assert exit_info.value.code == 2


def test_python_dash_m_runs_the_same_entry_point(clean_tree) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spec_check", "--check"],
        cwd=clean_tree.root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[stale-index]" in result.stdout
