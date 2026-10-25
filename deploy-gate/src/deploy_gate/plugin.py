"""The pytest plugin a consumer names in its `conftest.py`.

Realises GATE-4 (only a complete, clean run records the fingerprint) and
GATE-5 (a narrowed session is not the whole tier). It reads the
configuration GATE-1 and GATE-2 describe and fails as GATE-9 requires.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deploy_gate.config import Config, ConfigError, load_config
from deploy_gate.gate import NoWorkTreeError, record, repository_root

# Options that select a part of the collected tests.
_NARROWING = ("keyword", "deselect", "ignore", "ignore_glob", "lf", "stepwise", "stepwise_skip")


def whole_tier(config: pytest.Config, marker: str) -> bool:
    """Whether the session selected every test of the integration tier."""
    return (
        config.args_source is not pytest.Config.ArgsSource.ARGS
        and not any(getattr(config.option, name, None) for name in _NARROWING)
        and getattr(config.option, "markexpr", "") in ("", marker)
    )


class _Recorder:
    """Counts the integration tests' reports and records a complete, clean run."""

    def __init__(self, gate: Config, root: Path | None, no_work_tree: NoWorkTreeError | None):
        self.gate = gate
        self.root = root
        self.no_work_tree = no_work_tree
        self.passed = 0
        self.against = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if self.gate.marker not in report.keywords:
            return
        if report.when == "call" and report.passed:
            self.passed += 1
        elif report.skipped or report.failed:
            self.against += 1

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if not (
            exitstatus == 0
            and self.passed > 0
            and self.against == 0
            and whole_tier(session.config, self.gate.marker)
        ):
            return
        try:
            if self.root is None:
                raise self.no_work_tree or NoWorkTreeError("no git work tree")
            record(self.root, self.gate.code)
        except NoWorkTreeError as error:
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter is not None:
                reporter.write_line(f"deploy-gate: nothing recorded: {error}", red=True)
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config: pytest.Config) -> None:
    try:
        root, no_work_tree = repository_root(config.rootpath), None
    except NoWorkTreeError as error:
        root, no_work_tree = None, error
    try:
        gate = load_config(root or config.rootpath)
    except ConfigError as error:
        raise pytest.UsageError(f"deploy-gate: {error}") from None
    config.pluginmanager.register(_Recorder(gate, root, no_work_tree), "deploy-gate-recorder")
