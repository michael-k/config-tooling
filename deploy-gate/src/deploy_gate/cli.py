"""The `deploy-gate` command.

Realises GATE-6 (exit 1, naming the reason, when no passing run matches the
code), GATE-7 (no argument changes the verdict) and GATE-9 (exit 2 outside a
git work tree).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deploy_gate.config import ConfigError, load_config
from deploy_gate.gate import NoWorkTreeError, check, repository_root


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        prog="deploy-gate",
        description="Refuse a deployment unless a complete integration run passed on its code.",
    ).parse_args(argv)
    try:
        root = repository_root(Path.cwd())
        reason = check(root, load_config(root).code)
    except (ConfigError, NoWorkTreeError) as error:
        print(f"deploy-gate: {error}", file=sys.stderr)
        return 2
    if reason is None:
        return 0
    print(
        f"Refusing to deploy: {reason}. Run the whole integration tier first.",
        file=sys.stderr,
    )
    return 1
