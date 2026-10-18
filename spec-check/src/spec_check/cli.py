"""The `spec-check` command line.

Realises SPEC-17 (pending requirements are listed on every run), SPEC-18 (the
index is written after a clean full run), SPEC-19 (`--check` writes nothing
and fails on a stale index), SPEC-20 (`--spec` scopes every check except the
allowance pairing) and SPEC-21 (exit 0, 1 or 2).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from spec_check.allowances import (
    REGISTER_PATH,
    check_allowances,
    find_allowance_claims,
    parse_allowance_register,
)
from spec_check.citations import (
    check_citations,
    check_legacy_references,
    find_citations,
    scanned_files,
)
from spec_check.config import ConfigError, load_scan_globs
from spec_check.index import check_index, render_traceability, write_index
from spec_check.maps import check_implementation_map
from spec_check.tree import (
    Finding,
    check_ids,
    check_spec_markdown,
    check_structure,
    load_all_requirements,
    load_prefixes,
)

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_UNUSABLE = 2


@dataclass(frozen=True)
class Result:
    """What a run found, and the index a clean full run would write."""

    findings: list[Finding]
    pending: list[str]
    index: str


def run_checks(
    root: Path,
    globs: tuple[str, ...],
    prefixes: dict[str, str],
    all_prefixes: dict[str, str] | None = None,
) -> Result:
    """Run every check over `prefixes`, and the allowance pairing over `all_prefixes`.

    Whether an allowance is claimed is a whole-tree property (SPEC-20), so it
    alone is judged over the unscoped registry.
    """
    if all_prefixes is None:
        all_prefixes = prefixes
    specs_dir = root / "specs"
    files = scanned_files(root, globs)

    requirements = load_all_requirements(specs_dir, prefixes)
    citations = find_citations(root, files, prefixes)
    full_requirements = load_all_requirements(specs_dir, all_prefixes)
    findings = [
        *check_ids(requirements),
        *check_citations(requirements, citations, files),
        *check_structure(specs_dir, prefixes),
        *check_spec_markdown(specs_dir, prefixes),
        *check_implementation_map(root, specs_dir, prefixes, files, citations),
        *check_allowances(
            parse_allowance_register(specs_dir / REGISTER_PATH),
            find_allowance_claims(specs_dir, all_prefixes),
            full_requirements,
        ),
        *check_legacy_references(root, files),
    ]
    return Result(
        findings=findings,
        pending=sorted(req.id for req in requirements if req.pending),
        index=render_traceability(requirements, citations),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-check",
        description="Check the spec tree of the current directory against its code, "
        "and rewrite specs/_traceability.md after a clean full run.",
    )
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        metavar="NAME",
        help="limit the checks to this spec directory (repeatable); never writes the index",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing, and report a stale specs/_traceability.md as a finding",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Check the tree rooted at the current directory; return the exit status."""
    args = _parser().parse_args(argv)
    root = Path.cwd()

    readme = root / "specs" / "README.md"
    if not readme.is_file():
        print(f"spec-check: {readme} does not exist", file=sys.stderr)
        return EXIT_UNUSABLE
    try:
        globs = load_scan_globs(root)
    except ConfigError as error:
        print(f"spec-check: {error}", file=sys.stderr)
        return EXIT_UNUSABLE

    all_prefixes = load_prefixes(readme)
    prefixes = all_prefixes
    if args.spec:
        unknown = sorted(set(args.spec) - set(all_prefixes.values()))
        if unknown:
            print(f"spec-check: no registered spec named {', '.join(unknown)}", file=sys.stderr)
            return EXIT_UNUSABLE
        prefixes = {p: s for p, s in all_prefixes.items() if s in set(args.spec)}

    result = run_checks(root, globs, prefixes, all_prefixes)
    findings = list(result.findings)
    if args.check:
        findings += check_index(root, result.index, sorted(set(args.spec)) or None)

    for finding in sorted(findings, key=lambda f: (f.kind, f.message)):
        print(finding)
    if result.pending:
        print(f"Pending (specified, not yet implemented): {', '.join(result.pending)}")

    if findings:
        print(f"\n{len(findings)} finding(s)")
        return EXIT_FINDINGS

    print("Spec check: no findings")
    if not args.check and not args.spec:
        write_index(root, result.index)
    return EXIT_CLEAN
