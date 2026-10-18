"""Tests of the implementation map checks.

Covers SPEC-10 (every mapped path exists), SPEC-11 (a row says what its file
cites), SPEC-12 (every citing file has a row) and SPEC-13 (a row names one
file and lists its IDs one by one).
"""

from pathlib import Path

import pytest

from spec_check.citations import find_citations, scanned_files
from spec_check.maps import MapRow, check_implementation_map, parse_implementation_map

pytestmark = pytest.mark.unit


def _check(tree, globs: tuple[str, ...] = ("src/**/*.py", "docs/**/*.md")) -> list:
    prefixes = {"FOO": "foo", "BAR": "bar"}
    files = scanned_files(tree.root, globs)
    citations = find_citations(tree.root, files, prefixes)
    return check_implementation_map(tree.root, tree.root / "specs", prefixes, files, citations)


@pytest.fixture
def two_specs(clean_tree):
    clean_tree.registry({"FOO": "foo", "BAR": "bar"})
    clean_tree.spec("bar", clean_tree.requirement("BAR-1"), {"src/foo.py": "BAR-1"})
    clean_tree.write("src/foo.py", "# FOO-1 BAR-1\n")
    return clean_tree


def test_parse_implementation_map_reads_only_the_map_section(tree) -> None:
    tree.write(
        "specs/foo/design.md",
        "## Approach\n\n| `elsewhere.py` | FOO-9 |\n\n"
        "## Implementation map\n\n| Path | Realises |\n|---|---|\n"
        "| `a.py` | FOO-1, FOO-2 |\n| `b/` | — |\n\nProse.\n\n## Key decisions\n",
    )

    assert parse_implementation_map(tree.root / "specs/foo/design.md") == [
        MapRow("a.py", "FOO-1, FOO-2"),
        MapRow("b/", "—"),
    ]


def test_a_consistent_tree_has_no_map_findings(two_specs) -> None:
    assert _check(two_specs) == []
    assert two_specs.run() == 0


# SPEC-10: mapped paths exist.


def test_a_row_naming_a_missing_file_fails_and_names_the_design(clean_tree) -> None:
    rows = {"src/foo.py": "FOO-1", "src/gone.py": "FOO-1"}
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), rows)

    findings = _check(clean_tree)

    assert [f.kind for f in findings] == ["missing-implementation-path"]
    assert "foo/design.md" in findings[0].message
    assert "src/gone.py" in findings[0].message


def test_a_row_for_an_unscanned_path_is_only_checked_for_existence(clean_tree) -> None:
    clean_tree.write("pyproject.toml", clean_tree.read("pyproject.toml") + "# FOO-1\n")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1", "pyproject.toml": "FOO-7"}
    )

    assert _check(clean_tree) == []


# SPEC-11: a row matches its file's citations.


def test_a_row_listing_an_id_the_file_does_not_cite_fails(clean_tree) -> None:
    clean_tree.spec(
        "foo",
        clean_tree.requirement("FOO-1") + clean_tree.requirement("FOO-2"),
        {"src/foo.py": "FOO-1, FOO-2"},
    )

    findings = _check(clean_tree)

    assert [f.kind for f in findings] == ["map-row-mismatch"]
    assert "listed but not cited: FOO-2" in findings[0].message
    assert "cited but not listed: none" in findings[0].message


def test_a_file_citing_an_id_its_row_does_not_list_fails(clean_tree) -> None:
    clean_tree.write("src/foo.py", "# FOO-1 FOO-2\n")
    clean_tree.spec(
        "foo",
        clean_tree.requirement("FOO-1") + clean_tree.requirement("FOO-2"),
        {"src/foo.py": "FOO-1"},
    )

    findings = _check(clean_tree)

    assert [f.kind for f in findings] == ["map-row-mismatch"]
    assert "src/foo.py" in findings[0].message
    assert "listed but not cited: none" in findings[0].message
    assert "cited but not listed: FOO-2" in findings[0].message


def test_a_row_is_compared_with_its_own_specs_ids_only(two_specs) -> None:
    two_specs.spec("foo", two_specs.requirement("FOO-1"), {"src/foo.py": "FOO-1, BAR-1"})

    findings = _check(two_specs)

    assert [f.kind for f in findings] == ["map-row-mismatch"]
    assert "foo/design.md" in findings[0].message
    assert "listed but not cited: BAR-1" in findings[0].message


# SPEC-12: every citing file has a row.


def test_a_scanned_file_citing_an_id_with_no_row_fails(two_specs) -> None:
    two_specs.spec("bar", two_specs.requirement("BAR-1"), {})

    findings = _check(two_specs)

    assert [f.kind for f in findings] == ["unmapped-citing-file"]
    assert "src/foo.py cites BAR-1" in findings[0].message
    assert "bar/design.md" in findings[0].message


def test_a_markdown_file_citing_an_id_needs_no_row(clean_tree) -> None:
    clean_tree.write("docs/guide.md", "See FOO-1.\n")

    assert _check(clean_tree) == []


# SPEC-13: one file per row, IDs one by one.


def test_a_row_naming_a_directory_that_holds_a_scanned_file_fails(clean_tree) -> None:
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), {"src/": "FOO-1"})

    kinds = sorted(f.kind for f in _check(clean_tree))

    assert kinds == ["map-directory-row", "unmapped-citing-file"]


def test_a_row_naming_a_directory_that_holds_no_scanned_file_passes(clean_tree) -> None:
    clean_tree.write("inventory/hosts.yml", "# FOO-1\n")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1", "inventory/": "FOO-1"}
    )

    assert _check(clean_tree) == []


def test_a_row_naming_a_markdown_file_fails(clean_tree) -> None:
    clean_tree.write("docs/guide.md", "See FOO-1.\n")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1", "docs/guide.md": "FOO-1"}
    )

    findings = _check(clean_tree)

    assert [f.kind for f in findings] == ["map-markdown-row"]
    assert "docs/guide.md" in findings[0].message


@pytest.mark.parametrize("ids", ["FOO-1 … FOO-3", "FOO-1 - FOO-3", "FOO-1–FOO-3", "…"])
def test_a_row_writing_its_ids_as_a_range_fails(clean_tree, ids: str) -> None:
    clean_tree.write("src/foo.py", "# FOO-1 FOO-2 FOO-3\n")
    body = "".join(clean_tree.requirement(f"FOO-{n}") for n in (1, 2, 3))
    clean_tree.spec("foo", body, {"src/foo.py": ids})

    kinds = {f.kind for f in _check(clean_tree)}

    assert "map-range" in kinds


@pytest.mark.parametrize("ids", ["FOO-1, FOO-2, FOO-3", "FOO-1 — x"])
def test_ids_listed_one_by_one_are_not_a_range(ids: str) -> None:
    assert MapRow("a.py", ids).is_range is False


def test_map_findings_fail_the_run(clean_tree, capsys) -> None:
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), {"src/": "FOO-1"})

    assert clean_tree.run() == 1
    assert "[map-directory-row]" in capsys.readouterr().out
    assert not Path(clean_tree.root / "specs" / "_traceability.md").exists()
