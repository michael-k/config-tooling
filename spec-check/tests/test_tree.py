"""Tests of the registry, requirement parsing and spec shape.

Covers SPEC-1 (the registry is the only source of prefixes), SPEC-6 (an ID is
defined once), SPEC-7 (every spec has its files and sections) and SPEC-9 (no
unclosed code fence).
"""

from pathlib import Path

import pytest

from spec_check.citations import find_citations
from spec_check.tree import (
    Requirement,
    check_ids,
    check_spec_markdown,
    check_structure,
    load_all_requirements,
    load_prefixes,
    parse_requirements,
)

pytestmark = pytest.mark.unit


def _req(req_id: str) -> Requirement:
    prefix, number = req_id.split("-")
    return Requirement(req_id, prefix, int(number), "T", "s", Path("specs/s/requirements.md"))


# SPEC-1: the registry table.


def test_load_prefixes_reads_the_registry_table(tree) -> None:
    tree.registry({"FOO": "foo-spec", "BAR": "bar"})

    assert load_prefixes(tree.root / "specs/README.md") == {"FOO": "foo-spec", "BAR": "bar"}


def test_load_prefixes_ignores_prose_pipes(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Use `a | b` in a shell.\n| `FOO` | `foo` | x |\n")

    assert load_prefixes(readme) == {"FOO": "foo"}


def test_load_prefixes_accepts_a_prefix_containing_a_digit(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("| `B4R` | `bar` | `src/` |\n")

    assert load_prefixes(readme) == {"B4R": "bar"}


def test_a_newly_registered_prefix_is_checked_under_it(clean_tree) -> None:
    clean_tree.registry({"FOO": "foo", "QUX": "qux"})
    clean_tree.spec("qux", clean_tree.requirement("QUX-1"), {"src/qux.py": "QUX-1"})
    clean_tree.write("src/qux.py", "# QUX-1\n")

    assert clean_tree.run("--check") == 1  # only the index is stale
    assert clean_tree.run() == 0
    assert "`QUX-1`" in clean_tree.read("specs/_traceability.md")


def test_a_prefix_missing_from_the_registry_is_not_a_citation(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("# FOO-1 BAR-2\n")

    citations = find_citations(tmp_path, [Path("a.py")], {"FOO": "foo"})

    assert citations == {"FOO-1": {Path("a.py")}}


def test_parse_requirements_extracts_id_number_and_title(tmp_path: Path) -> None:
    path = tmp_path / "requirements.md"
    path.write_text(
        "## Requirements\n\n"
        "### FOO-1 — Password authentication\n\nSHALL a.\n\n"
        "### FOO-12 — Listen address\n\nSHALL b.\n"
    )

    reqs = parse_requirements(path, "foo")

    assert [r.id for r in reqs] == ["FOO-1", "FOO-12"]
    assert [r.number for r in reqs] == [1, 12]
    assert reqs[0].title == "Password authentication"
    assert reqs[0].prefix == "FOO"
    assert reqs[0].spec == "foo"
    assert reqs[0].source == path


def test_parse_requirements_marks_withdrawn(tmp_path: Path) -> None:
    path = tmp_path / "requirements.md"
    path.write_text("### FOO-4 — Old rule (withdrawn)\n\nSuperseded by FOO-9.\n")

    (req,) = parse_requirements(path, "foo")

    assert req.withdrawn is True
    assert req.title == "Old rule"


@pytest.mark.parametrize("annotation", ["exempt", "pending"])
def test_parse_requirements_marks_annotations(tmp_path: Path, annotation: str) -> None:
    path = tmp_path / "requirements.md"
    path.write_text(f"### FOO-9 — Prose\n\nSHALL a.\n\n**Traceability:** {annotation} — why.\n")

    (req,) = parse_requirements(path, "foo")

    assert getattr(req, annotation) is True
    assert req.withdrawn is False


def test_parse_requirements_accepts_a_prefix_containing_a_digit(tmp_path: Path) -> None:
    path = tmp_path / "requirements.md"
    path.write_text("### B4R-1 — Jail\n\nSHALL a.\n")

    (req,) = parse_requirements(path, "bar")

    assert (req.id, req.prefix, req.number) == ("B4R-1", "B4R", 1)


def test_parse_requirements_ignores_headings_that_are_not_requirements(tmp_path: Path) -> None:
    path = tmp_path / "requirements.md"
    path.write_text("### In scope\n\nStuff.\n\n### FOO-1 — Real one\n\nSHALL do it.\n")

    assert [r.id for r in parse_requirements(path, "foo")] == ["FOO-1"]


def test_load_all_requirements_walks_registered_spec_directories(tmp_path: Path) -> None:
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "requirements.md").write_text("### FOO-1 — A\n\nSHALL a.\n")
    (tmp_path / "bar").mkdir()
    (tmp_path / "bar" / "requirements.md").write_text("### BAR-1 — B\n\nSHALL b.\n")
    (tmp_path / "qux").mkdir()
    (tmp_path / "qux" / "requirements.md").write_text("### QUX-1 — C\n\nSHALL c.\n")

    reqs = load_all_requirements(tmp_path, {"FOO": "foo", "BAR": "bar"})

    assert sorted(r.id for r in reqs) == ["BAR-1", "FOO-1"]


# SPEC-6: one heading per ID.


def test_check_ids_flags_duplicates() -> None:
    findings = check_ids([_req("FOO-1"), _req("FOO-1")])

    assert [f.kind for f in findings] == ["duplicate-id"]
    assert "FOO-1" in findings[0].message


def test_check_ids_does_not_require_a_gap_free_sequence() -> None:
    assert check_ids([_req("FOO-1"), _req("FOO-7")]) == []


def test_a_tree_with_one_id_under_two_headings_fails_and_names_both(clean_tree, capsys) -> None:
    clean_tree.spec(
        "foo",
        clean_tree.requirement("FOO-1") + clean_tree.requirement("FOO-1", "Again"),
        {"src/foo.py": "FOO-1"},
    )

    assert clean_tree.run() == 1
    out = capsys.readouterr().out
    assert "[duplicate-id] FOO-1" in out
    assert out.count("specs/foo/requirements.md") == 2


# SPEC-7: files and sections.


def test_check_structure_accepts_a_complete_spec(clean_tree) -> None:
    assert check_structure(clean_tree.root / "specs", {"FOO": "foo"}) == []


@pytest.mark.parametrize(
    ("filename", "section"),
    [
        ("requirements.md", "Purpose"),
        ("requirements.md", "Scope"),
        ("requirements.md", "Security invariants"),
        ("requirements.md", "Requirements"),
        ("design.md", "Approach"),
        ("design.md", "Implementation map"),
    ],
)
def test_check_structure_flags_each_missing_section(clean_tree, filename, section) -> None:
    path = clean_tree.root / "specs" / "foo" / filename
    path.write_text(path.read_text().replace(f"## {section}\n", "## Notes\n"))

    findings = check_structure(clean_tree.root / "specs", {"FOO": "foo"})

    assert [f.kind for f in findings] == ["missing-section"]
    assert f"foo/{filename}" in findings[0].message
    assert section in findings[0].message


@pytest.mark.parametrize("filename", ["requirements.md", "design.md"])
def test_check_structure_flags_each_missing_file(clean_tree, filename) -> None:
    (clean_tree.root / "specs" / "foo" / filename).unlink()

    findings = check_structure(clean_tree.root / "specs", {"FOO": "foo"})

    assert [f.kind for f in findings] == ["missing-spec-file"]
    assert f"foo/{filename}" in findings[0].message


# SPEC-9: unclosed fences.


def test_check_spec_markdown_flags_an_unclosed_code_fence(tree) -> None:
    tree.spec("foo", "```\nunterminated\n" + tree.requirement("FOO-1"), {})

    findings = check_spec_markdown(tree.root / "specs", {"FOO": "foo"})

    assert [f.kind for f in findings] == ["unclosed-code-fence"]
    assert "foo/requirements.md" in findings[0].message


def test_check_spec_markdown_accepts_balanced_fences(tree) -> None:
    tree.spec("foo", "```\nexample\n```\n" + tree.requirement("FOO-1"), {})

    assert check_spec_markdown(tree.root / "specs", {"FOO": "foo"}) == []
