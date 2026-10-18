"""Tests of the allowance register and its claims.

Covers SPEC-8 (allowances and their claims pair up) and SPEC-20 (a scoped
run still judges the pairing over the whole tree). Allowance IDs can only
take the `ALW` form the register uses; every requirement ID is unregistered.
"""

from pathlib import Path

import pytest

from spec_check.allowances import (
    check_allowances,
    find_allowance_claims,
    parse_allowance_register,
)
from spec_check.tree import Requirement

pytestmark = pytest.mark.unit

REGISTER_HEADER = (
    "| Allowance | Invariants | Claimed by | Compensating control |\n|---|---|---|---|\n"
)


def _req(req_id: str, spec: str = "s", withdrawn: bool = False) -> Requirement:
    prefix, number = req_id.split("-")
    source = Path(f"specs/{spec}/requirements.md")
    return Requirement(req_id, prefix, int(number), "T", spec, source, withdrawn=withdrawn)


def _register(tree, *rows: str) -> None:
    tree.write("specs/project/security-invariants.md", REGISTER_HEADER + "".join(rows))


def test_parse_allowance_register_reads_rows(tmp_path: Path) -> None:
    path = tmp_path / "security-invariants.md"
    path.write_text(REGISTER_HEADER + "| ALW-1 | none | BAR-2, BAR-3 | Console root only |\n")

    assert parse_allowance_register(path) == {"ALW-1": {"BAR-2", "BAR-3"}}


def test_parse_allowance_register_accepts_a_prefix_containing_a_digit(tmp_path: Path) -> None:
    path = tmp_path / "security-invariants.md"
    path.write_text(REGISTER_HEADER + "| ALW-1 | none | B4R-1 | Console root only |\n")

    assert parse_allowance_register(path) == {"ALW-1": {"B4R-1"}}


def test_parse_allowance_register_without_a_file_is_empty(tmp_path: Path) -> None:
    assert parse_allowance_register(tmp_path / "missing.md") == {}


def test_find_allowance_claims_reads_the_claims_line(tree) -> None:
    tree.spec("bar", tree.requirement("BAR-2"), {}, claims="ALW-1")

    assert find_allowance_claims(tree.root / "specs", {"BAR": "bar"}) == {"ALW-1": {"bar"}}


def test_a_claim_inside_a_fenced_code_block_is_not_a_claim(tree) -> None:
    body = "```\n**Allowances claimed:** ALW-9\n```\n" + tree.requirement("BAR-2")
    tree.spec("bar", body, {})

    assert find_allowance_claims(tree.root / "specs", {"BAR": "bar"}) == {}


def test_check_allowances_flags_a_claim_missing_from_the_register() -> None:
    findings = check_allowances({}, {"ALW-1": {"bar"}}, [])

    assert [f.kind for f in findings] == ["unregistered-allowance"]


def test_check_allowances_flags_a_register_entry_nobody_claims() -> None:
    findings = check_allowances({"ALW-1": {"BAR-2"}}, {}, [_req("BAR-2")])

    assert [f.kind for f in findings] == ["unclaimed-allowance"]


def test_check_allowances_flags_an_unknown_claimant() -> None:
    findings = check_allowances({"ALW-1": {"BAR-99"}}, {"ALW-1": {"bar"}}, [_req("BAR-2")])

    assert [f.kind for f in findings] == ["dangling-citation"]


def test_check_allowances_accepts_a_matched_pair() -> None:
    findings = check_allowances({"ALW-1": {"BAR-2"}}, {"ALW-1": {"bar"}}, [_req("BAR-2", "bar")])

    assert findings == []


def test_check_allowances_flags_a_claimant_owned_by_a_different_spec() -> None:
    findings = check_allowances({"ALW-1": {"BAR-2"}}, {"ALW-1": {"foo"}}, [_req("BAR-2", "bar")])

    assert [f.kind for f in findings] == ["allowance-claimant-mismatch"]


def test_check_allowances_flags_a_register_entry_with_no_claimant_id() -> None:
    findings = check_allowances({"ALW-1": set()}, {"ALW-1": {"bar"}}, [])

    assert [f.kind for f in findings] == ["allowance-without-claimant"]


def test_check_allowances_flags_a_withdrawn_claimant() -> None:
    findings = check_allowances(
        {"ALW-1": {"BAR-2"}}, {"ALW-1": {"bar"}}, [_req("BAR-2", "bar", withdrawn=True)]
    )

    assert [f.kind for f in findings] == ["withdrawn-allowance-claimant"]


def _tree_with_claim(clean_tree) -> None:
    clean_tree.registry({"FOO": "foo", "BAR": "bar"})
    clean_tree.spec("bar", clean_tree.requirement("BAR-2"), {"src/bar.py": "BAR-2"}, "ALW-1")
    clean_tree.write("src/bar.py", "# BAR-2\n")


def test_an_unclaimed_register_row_fails_the_run(clean_tree, capsys) -> None:
    _register(clean_tree, "| ALW-1 | none | FOO-1 | c |\n")

    assert clean_tree.run() == 1
    assert "[unclaimed-allowance] ALW-1" in capsys.readouterr().out


def test_a_claim_with_no_register_row_fails_the_run(clean_tree, capsys) -> None:
    _tree_with_claim(clean_tree)

    assert clean_tree.run() == 1
    assert "[unregistered-allowance] ALW-1 is claimed by bar" in capsys.readouterr().out


def test_a_paired_allowance_passes(clean_tree) -> None:
    _tree_with_claim(clean_tree)
    _register(clean_tree, "| ALW-1 | none | BAR-2 | c |\n")

    assert clean_tree.run() == 0


def test_a_scoped_run_judges_the_pairing_over_the_whole_tree(clean_tree, capsys) -> None:
    _tree_with_claim(clean_tree)
    _register(clean_tree, "| ALW-1 | none | BAR-2 | c |\n")

    assert clean_tree.run("--spec", "foo") == 0
    assert "allowance" not in capsys.readouterr().out
