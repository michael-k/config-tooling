"""Citations: which files are read, what counts as one, and which are findings.

Realises SPEC-2 (every requirement is cited by a file other than Markdown),
SPEC-3 (every citation names a requirement), SPEC-4 (no citation of a
withdrawn requirement), SPEC-5 (no citation of a pending requirement),
SPEC-14 (nothing inside a submodule is read), SPEC-16 (the superseded
numbering is gone), SPEC-22 (a documentation requirement names a scanned
file), SPEC-23 (files git ignores are not read) and SPEC-24 (outside a git
work tree the check does not run).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from spec_check.config import expand_globs
from spec_check.tree import Finding, Requirement

_LEGACY_REF = re.compile(r"\bRequirements?:?\s+\d+\.\d+")
_SUBMODULE_PATH = re.compile(r"^\s*path\s*=\s*(?P<path>.+?)\s*$")

Citations = dict[str, set[Path]]


class NoWorkTreeError(Exception):
    """Git cannot say what it ignores, so the scan cannot run (SPEC-24)."""


def is_markdown(path: Path) -> bool:
    """A scanned file ending in `.md` documents requirements rather than realising them."""
    return path.suffix == ".md"


def read_submodules(root: Path) -> list[Path]:
    """The submodule paths listed in `<root>/.gitmodules` (SPEC-14)."""
    gitmodules = root / ".gitmodules"
    if not gitmodules.is_file():
        return []
    return [
        Path(match["path"])
        for line in gitmodules.read_text().splitlines()
        if (match := _SUBMODULE_PATH.match(line))
    ]


def ignored_by_git(root: Path, paths: list[Path]) -> set[Path]:
    """Those of `paths` that git ignores in the work tree at `root` (SPEC-23).

    Raises `NoWorkTreeError` when `git` is missing or `root` is no work tree
    (SPEC-24).  A path inside a submodule makes `check-ignore` fail, so the
    caller drops those first.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--stdin", "-z"],
            input="".join(f"{path}\0" for path in paths),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise NoWorkTreeError("git is not installed; it decides which files are read") from None
    # check-ignore exits 0 when it names a path, 1 when it names none.
    if result.returncode not in (0, 1):
        raise NoWorkTreeError(f"{root} is not a git work tree: {result.stderr.strip()}")
    return {Path(name) for name in result.stdout.split("\0") if name}


def scanned_files(root: Path, globs: tuple[str, ...]) -> list[Path]:
    """The files the scan reads: every glob match outside every submodule
    (SPEC-14) that git does not ignore (SPEC-23)."""
    submodules = read_submodules(root)
    outside = [
        path
        for path in expand_globs(root, globs)
        if not any(path == sub or sub in path.parents for sub in submodules)
    ]
    ignored = ignored_by_git(root, outside)
    return [path for path in outside if path not in ignored]


def citation_pattern(prefixes: dict[str, str]) -> re.Pattern[str]:
    """Build a pattern matching `PREFIX-N` for registered prefixes only."""
    alternatives = "|".join(sorted(prefixes, key=len, reverse=True))
    return re.compile(rf"\b({alternatives})-(\d+)\b")


def find_citations(root: Path, files: list[Path], prefixes: dict[str, str]) -> Citations:
    """Map each cited requirement ID to the scanned files citing it."""
    if not prefixes:
        return {}
    pattern = citation_pattern(prefixes)
    citations: Citations = {}
    for path in files:
        for match in pattern.finditer((root / path).read_text(errors="replace")):
            citations.setdefault(f"{match[1]}-{match[2]}", set()).add(path)
    return citations


def _counts(req: Requirement, path: Path) -> bool:
    """Whether a citation in `path` makes `req` cited (SPEC-2)."""
    if not is_markdown(path):
        return True
    return bool(req.documentation) and path == Path(req.documentation)


def check_citations(
    requirements: list[Requirement],
    citations: Citations,
    scanned: list[Path] | None = None,
) -> list[Finding]:
    """Flag citations without a live requirement, and requirements nothing cites."""
    by_id = {req.id: req for req in requirements}
    findings: list[Finding] = []

    for cited, paths in sorted(citations.items()):
        where = ", ".join(str(p) for p in sorted(paths))
        req = by_id.get(cited)
        if req is None:
            findings.append(
                Finding("dangling-citation", f"{cited} is cited by {where} but no spec defines it")
            )
        elif req.withdrawn:
            findings.append(
                Finding(
                    "cited-withdrawn-requirement",
                    f"{cited} is withdrawn but still cited by {where}",
                )
            )
        elif req.pending:
            findings.append(
                Finding(
                    "cited-pending-requirement",
                    f"{cited} is pending but already cited by {where}",
                )
            )

    scanned_set = set(scanned or ())
    for req in requirements:
        if req.withdrawn or req.exempt or req.pending:
            continue
        if req.documentation is not None and (
            not req.documentation or Path(req.documentation) not in scanned_set
        ):
            named = req.documentation or "no file"
            findings.append(
                Finding(
                    "documentation-file-not-scanned",
                    f"{req.id} is annotated documentation, but names {named}, "
                    "which the scan does not read",
                )
            )
        if any(_counts(req, path) for path in citations.get(req.id, ())):
            continue
        findings.append(
            Finding(
                "orphan-requirement",
                f"{req.id} ({req.title}) is defined in {req.source} but nothing cites it"
                + (" outside Markdown" if citations.get(req.id) else ""),
            )
        )

    return findings


def check_legacy_references(root: Path, files: list[Path]) -> list[Finding]:
    """Flag scanned lines citing a requirement in the superseded numbered form."""
    findings: list[Finding] = []
    for path in files:
        lines = (root / path).read_text(errors="replace").splitlines()
        for number, line in enumerate(lines, start=1):
            if _LEGACY_REF.search(line):
                findings.append(
                    Finding(
                        "legacy-reference",
                        f"{path}:{number} still cites the superseded numbering: {line.strip()}",
                    )
                )
    return findings
