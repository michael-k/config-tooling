"""The fingerprint and the check: GATE-3, GATE-6, GATE-7, GATE-9."""

from __future__ import annotations

import pytest

from deploy_gate import cli
from deploy_gate.gate import NoWorkTreeError, check, fingerprint, record

pytestmark = pytest.mark.unit

CODE = ("roles", "site.yml")


@pytest.mark.parametrize(
    "change",
    [
        lambda repo: repo.write("roles/web/tasks/main.yml", "- ansible.builtin.setup:\n"),
        lambda repo: repo.write("roles/web/handlers/main.yml", "[]\n"),
        lambda repo: (repo.root / "site.yml").unlink(),
    ],
    ids=["edited", "added", "deleted"],
)
def test_a_change_to_the_code_closes_the_gate(repo, change):
    """GATE-3: committed or not, tracked or not."""
    record(repo.root, CODE)
    change(repo)
    assert check(repo.root, CODE) == (
        "the deployment code changed since the last passing integration run"
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda repo: repo.write("README.md", "changed\n"),
        lambda repo: repo.write("roles/web/facts.cache", "ignored\n"),
    ],
    ids=["outside the code", "ignored by git"],
)
def test_other_changes_leave_it_open(repo, change):
    """GATE-3"""
    record(repo.root, CODE)
    change(repo)
    assert check(repo.root, CODE) is None


def test_a_tracked_file_deleted_from_the_tree_drops_out(repo):
    """GATE-3: it is no part of the code any more, and breaks nothing."""
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "x")
    before = fingerprint(repo.root, CODE)
    (repo.root / "site.yml").unlink()
    assert fingerprint(repo.root, CODE) != before


def test_the_fingerprint_does_not_depend_on_staging(repo):
    """GATE-3: the content counts, not whether git has seen it."""
    before = fingerprint(repo.root, CODE)
    repo.git("add", "-A")
    assert fingerprint(repo.root, CODE) == before


def test_without_a_record_the_check_refuses(repo):
    """GATE-6"""
    assert check(repo.root, CODE) == "no integration run has passed on this checkout"


def test_the_command_names_both_reasons(repo, monkeypatch, capsys):
    """GATE-6: exit 1 with one of two messages, exit 0 on a matching record."""
    monkeypatch.chdir(repo.root / "roles")
    assert cli.main([]) == 1
    assert "no integration run has passed" in capsys.readouterr().err
    record(repo.root, CODE)
    assert cli.main([]) == 0
    repo.write("site.yml", "- hosts: web\n")
    assert cli.main([]) == 1
    assert "changed since the last passing" in capsys.readouterr().err


def test_the_command_takes_no_option(repo, monkeypatch):
    """GATE-7: nothing on the command line changes the verdict."""
    monkeypatch.chdir(repo.root)
    for argument in ["--force", "--skip", "-f"]:
        with pytest.raises(SystemExit) as raised:
            cli.main([argument])
        assert raised.value.code == 2


def test_the_command_reports_a_missing_table(repo, monkeypatch, capsys):
    """GATE-1: the command fails, naming the table."""
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    monkeypatch.chdir(repo.root)
    assert cli.main([]) == 2
    assert "[tool.deploy-gate]" in capsys.readouterr().err


def test_outside_a_work_tree_nothing_is_fingerprinted(tmp_path, monkeypatch, capsys):
    """GATE-9"""
    (tmp_path / "pyproject.toml").write_text('[tool.deploy-gate]\ncode = ["r"]\nmarker = "vm"\n')
    with pytest.raises(NoWorkTreeError, match="not in a git work tree"):
        fingerprint(tmp_path, ("r",))
    monkeypatch.chdir(tmp_path)
    assert cli.main([]) == 2
    assert "git work tree" in capsys.readouterr().err


def test_without_git_nothing_is_fingerprinted(repo, monkeypatch, capsys):
    """GATE-9"""
    monkeypatch.setenv("PATH", "")
    with pytest.raises(NoWorkTreeError, match="cannot be run"):
        fingerprint(repo.root, CODE)
    monkeypatch.chdir(repo.root)
    assert cli.main([]) == 2
    assert "`git` cannot be run" in capsys.readouterr().err
