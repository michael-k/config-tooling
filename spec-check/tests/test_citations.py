"""Tests of the scan and the citation checks.

Covers SPEC-2 (every requirement is cited outside Markdown), SPEC-3 (every
citation names a requirement), SPEC-4 (no citation of a withdrawn
requirement), SPEC-5 (no citation of a pending requirement), SPEC-14
(nothing inside a submodule is read), SPEC-16 (the superseded numbering
is gone), SPEC-22 (a documentation requirement names a scanned file) and
SPEC-23 (files git ignores are not read).
"""

from pathlib import Path
from typing import Any

import pytest

from spec_check.citations import (
    check_citations,
    check_legacy_references,
    citation_pattern,
    find_citations,
    read_submodules,
    scanned_files,
)
from spec_check.tree import Requirement, parse_requirements

pytestmark = pytest.mark.unit

# Built in two pieces so this module's own lines do not match the pattern.
LEGACY = "Requirement 2" + ".3"


def _req(req_id: str, **kwargs: Any) -> Requirement:
    prefix, number = req_id.split("-")
    source = Path("specs/s/requirements.md")
    return Requirement(req_id, prefix, int(number), "T", "s", source, **kwargs)


def test_citation_pattern_matches_registered_prefixes_only() -> None:
    pattern = citation_pattern({"FOO": "foo", "BAR": "bar"})

    assert pattern.findall("see FOO-3 and BAR-12 and QUX-1") == [("FOO", "3"), ("BAR", "12")]


def test_citation_pattern_ignores_lookalike_tokens() -> None:
    pattern = citation_pattern({"SHA": "sha", "AES": "aes"})

    assert pattern.findall("XSHA-512 AES-256x CVE-2024-1234") == []


def test_citation_pattern_prefers_the_longest_prefix() -> None:
    pattern = citation_pattern({"B4R": "bar", "B4": "b"})

    assert pattern.findall("B4R-1") == [("B4R", "1")]


def test_find_citations_maps_ids_to_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("# FOO-1: something\n")
    (tmp_path / "b.yml").write_text("# FOO-1 and FOO-2\n")

    citations = find_citations(tmp_path, [Path("src/a.py"), Path("b.yml")], {"FOO": "foo"})

    assert citations == {"FOO-1": {Path("src/a.py"), Path("b.yml")}, "FOO-2": {Path("b.yml")}}


def test_scan_reads_only_what_the_globs_match(clean_tree) -> None:
    clean_tree.write("other/x.py", "# FOO-1\n")
    clean_tree.write("specs/foo/notes.py", "# FOO-1\n")

    assert scanned_files(clean_tree.root, ("src/**/*.py",)) == [Path("src/foo.py")]


# SPEC-2: uncited requirements.


def test_check_citations_flags_orphan_requirements() -> None:
    assert [f.kind for f in check_citations([_req("FOO-1")], {})] == ["orphan-requirement"]


def test_check_citations_accepts_a_cited_requirement() -> None:
    assert check_citations([_req("FOO-1")], {"FOO-1": {Path("a.py")}}) == []


def test_a_markdown_citation_does_not_make_a_requirement_cited() -> None:
    findings = check_citations([_req("FOO-1")], {"FOO-1": {Path("docs/a.md")}})

    assert [f.kind for f in findings] == ["orphan-requirement"]
    assert "FOO-1" in findings[0].message


def _doc_req(req_id: str, doc: str) -> Requirement:
    return Requirement(req_id, "FOO", 1, "title", "foo", Path("specs/foo/requirements.md"),
                       documentation=doc)


def test_a_documentation_requirement_is_cited_by_its_named_file() -> None:
    req = _doc_req("FOO-1", "README.md")
    scanned = [Path("README.md")]
    assert check_citations([req], {"FOO-1": {Path("README.md")}}, scanned) == []


def test_a_documentation_requirement_is_not_cited_by_another_markdown_file() -> None:
    req = _doc_req("FOO-1", "README.md")
    scanned = [Path("README.md"), Path("docs/a.md")]
    findings = check_citations([req], {"FOO-1": {Path("docs/a.md")}}, scanned)
    assert [f.kind for f in findings] == ["orphan-requirement"]


# SPEC-22: the named file must be scanned.


@pytest.mark.parametrize("doc", ["", "docs/missing.md"])
def test_a_documentation_annotation_must_name_a_scanned_file(doc: str) -> None:
    findings = check_citations([_doc_req("FOO-1", doc)], {}, [Path("README.md")])
    assert "documentation-file-not-scanned" in [f.kind for f in findings]


def test_the_documentation_annotation_is_parsed(tmp_path) -> None:
    spec = tmp_path / "requirements.md"
    spec.write_text(
        "### FOO-1 — A section\n\nTHE Docs SHALL.\n\n"
        "**Traceability:** documentation — `README.md`\n\n"
        "### FOO-2 — Another\n\n**Traceability:** documentation\n"
    )
    reqs = parse_requirements(spec, "foo")
    assert [r.documentation for r in reqs] == ["README.md", ""]


@pytest.mark.parametrize("annotation", ["exempt", "pending", "withdrawn"])
def test_check_citations_does_not_require_annotated_requirements(annotation: str) -> None:
    assert check_citations([_req("FOO-1", **{annotation: True})], {}) == []


def test_an_uncited_requirement_fails_the_run_and_is_named(clean_tree, capsys) -> None:
    clean_tree.write("src/foo.py", "nothing\n")
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), {"src/foo.py": ""})

    assert clean_tree.run() == 1
    assert "[orphan-requirement] FOO-1" in capsys.readouterr().out


def test_a_requirement_cited_only_in_markdown_fails_the_run(clean_tree, capsys) -> None:
    clean_tree.write("src/foo.py", "nothing\n")
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), {"src/foo.py": ""})
    clean_tree.write("docs/guide.md", "See FOO-1.\n")

    assert clean_tree.run() == 1
    assert "[orphan-requirement] FOO-1" in capsys.readouterr().out


@pytest.mark.parametrize("annotation", ["exempt", "pending"])
def test_an_annotated_uncited_requirement_passes(clean_tree, annotation: str) -> None:
    clean_tree.write("src/foo.py", "nothing\n")
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1", annotation=annotation), {"src/foo.py": ""}
    )

    assert clean_tree.run() == 0


def test_markdown_citations_appear_in_the_index(clean_tree) -> None:
    clean_tree.write("docs/guide.md", "See FOO-1.\n")

    assert clean_tree.run() == 0
    assert "`docs/guide.md`" in clean_tree.read("specs/_traceability.md")


# SPEC-3: citations of nothing.


def test_check_citations_flags_dangling_references() -> None:
    findings = check_citations([_req("FOO-1")], {"FOO-1": {Path("a.py")}, "FOO-9": {Path("b.py")}})

    assert [f.kind for f in findings] == ["dangling-citation"]
    assert "FOO-9" in findings[0].message
    assert "b.py" in findings[0].message


def test_a_citation_of_a_missing_id_fails_the_run_and_names_the_file(clean_tree, capsys) -> None:
    clean_tree.write("src/foo.py", "# FOO-1 FOO-99\n")
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), {"src/foo.py": "FOO-1, FOO-99"})

    assert clean_tree.run() == 1
    assert "[dangling-citation] FOO-99 is cited by src/foo.py" in capsys.readouterr().out


# SPEC-4: withdrawn requirements.


def test_check_citations_flags_a_cited_withdrawn_requirement() -> None:
    findings = check_citations([_req("FOO-4", withdrawn=True)], {"FOO-4": {Path("a.py")}})

    assert [f.kind for f in findings] == ["cited-withdrawn-requirement"]
    assert "FOO-4" in findings[0].message
    assert "a.py" in findings[0].message


def test_a_citation_of_a_withdrawn_requirement_fails_the_run(clean_tree, capsys) -> None:
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1", "Old (withdrawn)"), {"src/foo.py": "FOO-1"}
    )

    assert clean_tree.run() == 1
    assert "[cited-withdrawn-requirement] FOO-1" in capsys.readouterr().out


# SPEC-5: pending requirements.


def test_check_citations_flags_a_cited_pending_requirement() -> None:
    findings = check_citations([_req("FOO-3", pending=True)], {"FOO-3": {Path("a.py")}})

    assert [f.kind for f in findings] == ["cited-pending-requirement"]
    assert "FOO-3" in findings[0].message
    assert "a.py" in findings[0].message


def test_a_citation_of_a_pending_requirement_fails_the_run(clean_tree, capsys) -> None:
    clean_tree.spec(
        "foo", clean_tree.requirement("FOO-1", annotation="pending"), {"src/foo.py": "FOO-1"}
    )

    assert clean_tree.run() == 1
    assert "[cited-pending-requirement] FOO-1 is pending but already cited by src/foo.py" in (
        capsys.readouterr().out
    )


# SPEC-14: submodules.


def test_read_submodules_lists_every_path(tmp_path: Path) -> None:
    (tmp_path / ".gitmodules").write_text(
        '[submodule "tooling"]\n\tpath = config-tooling\n\turl = ../x.git\n'
        '[submodule "b"]\n  path = vendor/b\n'
    )

    assert read_submodules(tmp_path) == [Path("config-tooling"), Path("vendor/b")]


def test_read_submodules_without_gitmodules_is_empty(tmp_path: Path) -> None:
    assert read_submodules(tmp_path) == []


def test_nothing_inside_a_submodule_is_read(clean_tree, capsys) -> None:
    clean_tree.write(".gitmodules", '[submodule "t"]\n\tpath = src/tooling\n\turl = ../t.git\n')
    clean_tree.write("src/tooling/deep/x.py", "# FOO-1 FOO-77 " + LEGACY + "\n")
    clean_tree.write("src/toolingx.py", "# FOO-1\n")
    rows = {"src/foo.py": "FOO-1", "src/toolingx.py": "FOO-1"}
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), rows)

    assert scanned_files(clean_tree.root, ("src/**/*.py",)) == [
        Path("src/foo.py"),
        Path("src/toolingx.py"),
    ]
    assert clean_tree.run() == 0
    assert "tooling/" not in capsys.readouterr().out
    assert "src/tooling/" not in clean_tree.read("specs/_traceability.md")


# SPEC-23: files git ignores.


def test_files_git_ignores_are_not_read(clean_tree, capsys) -> None:
    clean_tree.write(".gitignore", "__pycache__/\n*.cache.py\n")
    clean_tree.write("src/tracked.py", "# FOO-1\n")
    clean_tree.write("src/__pycache__/foo.cpython-314.pyc", "FOO-1 FOO-77\n")
    clean_tree.write("src/stale.cache.py", "# FOO-77\n")
    clean_tree.git("add", "src/tracked.py")
    rows = {"src/foo.py": "FOO-1", "src/tracked.py": "FOO-1"}
    clean_tree.spec("foo", clean_tree.requirement("FOO-1"), rows)

    assert scanned_files(clean_tree.root, ("src/**/*",)) == [
        Path("src/foo.py"),
        Path("src/tracked.py"),
    ]
    clean_tree.scan("src/**/*")
    assert clean_tree.run() == 0
    assert "FOO-77" not in capsys.readouterr().out


def test_a_tracked_file_an_ignore_pattern_matches_is_read(clean_tree) -> None:
    clean_tree.write(".gitignore", "*.py\n")
    clean_tree.git("add", "--force", "src/foo.py")

    assert scanned_files(clean_tree.root, ("src/**/*.py",)) == [Path("src/foo.py")]


def test_the_ignore_rules_in_nested_files_and_info_exclude_count(clean_tree) -> None:
    clean_tree.write("src/.gitignore", "nested.py\n")
    clean_tree.write(".git/info/exclude", "excluded.py\n")
    clean_tree.write("src/nested.py", "# FOO-1\n")
    clean_tree.write("src/excluded.py", "# FOO-1\n")

    assert scanned_files(clean_tree.root, ("src/**/*.py",)) == [Path("src/foo.py")]


# SPEC-16: the superseded numbering.


def test_check_legacy_references_flags_old_style_citations(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text(f"ok\n# {LEGACY} is stale\n")

    findings = check_legacy_references(tmp_path, [Path("a.yml")])

    assert [f.kind for f in findings] == ["legacy-reference"]
    assert "a.yml:2" in findings[0].message


def test_check_legacy_references_accepts_a_clean_file(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("# FOO-11, Requirements section 2\n")

    assert check_legacy_references(tmp_path, [Path("a.yml")]) == []


def test_a_legacy_reference_fails_the_run(clean_tree, capsys) -> None:
    clean_tree.write("src/foo.py", f"# FOO-1, formerly {LEGACY}\n")

    assert clean_tree.run() == 1
    assert "[legacy-reference] src/foo.py:1" in capsys.readouterr().out
