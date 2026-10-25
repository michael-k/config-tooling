"""The fingerprint, the record and the check.

Realises GATE-3 (the fingerprint covers the content of every file git does
not ignore), GATE-6 (the check names why it refuses) and GATE-9 (without a
git work tree nothing is fingerprinted).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

STAMP = ".integration-passed"


class NoWorkTreeError(Exception):
    """Git cannot say which files are code, so the gate cannot run (GATE-9)."""


def _git(start: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), *args], capture_output=True, check=False
        )
    except FileNotFoundError:
        raise NoWorkTreeError("`git` cannot be run; the deploy gate needs it") from None
    if result.returncode != 0:
        raise NoWorkTreeError(
            f"{start} is not in a git work tree: {result.stderr.decode().strip()}"
        )
    return result.stdout


def repository_root(start: Path) -> Path:
    """The top level of the git work tree that holds `start`."""
    return Path(_git(start, "rev-parse", "--show-toplevel").decode().strip())


def fingerprint(root: Path, code: tuple[str, ...]) -> str:
    """SHA-256 over the path and content of every file under `code` git does not ignore."""
    listed = _git(
        root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *code
    )
    digest = hashlib.sha256()
    for name in sorted(set(filter(None, listed.decode().split("\0")))):
        path = root / name
        if not path.is_file():
            # Tracked but deleted in the working tree: not part of the code.
            continue
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def record(root: Path, code: tuple[str, ...]) -> None:
    (root / STAMP).write_text(fingerprint(root, code) + "\n")


def check(root: Path, code: tuple[str, ...]) -> str | None:
    """None when the deployment may go ahead, otherwise the reason it may not."""
    stamp = root / STAMP
    if not stamp.is_file():
        return "no integration run has passed on this checkout"
    if stamp.read_text().strip() != fingerprint(root, code):
        return "the deployment code changed since the last passing integration run"
    return None
