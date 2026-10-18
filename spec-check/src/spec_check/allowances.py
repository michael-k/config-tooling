"""The allowance register and the claims on it pair up (SPEC-8)."""

from __future__ import annotations

import re
from pathlib import Path

from spec_check.tree import Finding, Requirement, spec_names

_ALLOWANCE_ROW = re.compile(r"^\|\s*(?P<id>ALW-\d+)\s*\|[^|]*\|(?P<claimed_by>[^|]*)\|")
_CLAIMS_LINE = re.compile(r"^\*\*Allowances claimed:\*\*\s*(?P<value>.+?)\s*$")
_REQ_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")
_ALW_TOKEN = re.compile(r"\bALW-\d+\b")

REGISTER_PATH = Path("project") / "security-invariants.md"


def parse_allowance_register(path: Path) -> dict[str, set[str]]:
    """Map each register row's allowance to the requirements it names as claimants."""
    register: dict[str, set[str]] = {}
    if not path.is_file():
        return register
    for line in path.read_text().splitlines():
        match = _ALLOWANCE_ROW.match(line)
        if match:
            register[match["id"]] = set(_REQ_TOKEN.findall(match["claimed_by"]))
    return register


def find_allowance_claims(specs_dir: Path, prefixes: dict[str, str]) -> dict[str, set[str]]:
    """Read the `**Allowances claimed:**` line of every spec, outside code fences."""
    claims: dict[str, set[str]] = {}
    for spec in spec_names(prefixes):
        path = specs_dir / spec / "requirements.md"
        if not path.is_file():
            continue
        in_fence = False
        for line in path.read_text().splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = _CLAIMS_LINE.match(line)
            if not match:
                continue
            for allowance in _ALW_TOKEN.findall(match["value"]):
                claims.setdefault(allowance, set()).add(spec)
    return claims


def check_allowances(
    register: dict[str, set[str]],
    claims: dict[str, set[str]],
    requirements: list[Requirement],
) -> list[Finding]:
    """Flag allowances claimed but unregistered, registered but unclaimed, or dangling.

    A register row must also name at least one claimant, that claimant must
    not be withdrawn, and it must belong to a spec that claims the allowance.
    """
    by_id = {req.id: req for req in requirements}
    findings: list[Finding] = []

    findings.extend(
        Finding(
            "unregistered-allowance",
            f"{allowance} is claimed by {', '.join(sorted(specs))} "
            "but is not in the allowance register",
        )
        for allowance, specs in sorted(claims.items())
        if allowance not in register
    )
    findings.extend(
        Finding("unclaimed-allowance", f"{allowance} is registered but no spec claims it")
        for allowance in sorted(register)
        if allowance not in claims
    )
    findings.extend(
        Finding(
            "allowance-without-claimant",
            f"{allowance} names no claimant requirement in the register",
        )
        for allowance, req_ids in sorted(register.items())
        if not req_ids
    )
    findings.extend(
        Finding(
            "dangling-citation",
            f"{allowance} names {req_id} as its claimant but no spec defines it",
        )
        for allowance, req_ids in sorted(register.items())
        for req_id in sorted(req_ids)
        if req_id not in by_id
    )

    for allowance, req_ids in sorted(register.items()):
        for req_id in sorted(req_ids):
            req = by_id.get(req_id)
            if req is None:
                continue  # already reported as dangling-citation
            if req.withdrawn:
                findings.append(
                    Finding(
                        "withdrawn-allowance-claimant",
                        f"{allowance} names withdrawn requirement {req_id} as its claimant",
                    )
                )
                continue
            if allowance not in claims:
                continue  # already reported as unclaimed-allowance
            if req.spec not in claims[allowance]:
                findings.append(
                    Finding(
                        "allowance-claimant-mismatch",
                        f"{allowance} names {req_id} ({req.spec}) as its claimant but is "
                        f"claimed by {', '.join(sorted(claims[allowance]))}",
                    )
                )
    return findings
