"""The spec tree: its prefix registry, its requirements and their shape.

Realises SPEC-1 (prefixes come from the registry only), SPEC-6 (an ID is
defined once), SPEC-7 (every spec has its files and sections) and SPEC-9
(no unclosed code fence in a `requirements.md`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

_PREFIX_ROW = re.compile(
    r"^\|\s*`(?P<prefix>[A-Z][A-Z0-9]*)`\s*\|\s*`(?P<spec>[a-z0-9./-]+)`\s*\|"
)
_REQ_HEADING = re.compile(
    r"^### (?P<id>(?P<prefix>[A-Z][A-Z0-9]*)-(?P<number>\d+)) — (?P<title>.+?)\s*$"
)
_WITHDRAWN_SUFFIX = " (withdrawn)"
_EXEMPT_MARKER = "**Traceability:** exempt"
_PENDING_MARKER = "**Traceability:** pending"
_DOCUMENTATION = re.compile(
    r"\*\*Traceability:\*\* documentation(?:\s*[—-]\s*`?(?P<file>[^`\s]+)`?)?"
)

REQUIRED_REQUIREMENTS_SECTIONS: tuple[str, ...] = (
    "Purpose",
    "Scope",
    "Security invariants",
    "Requirements",
)
REQUIRED_DESIGN_SECTIONS: tuple[str, ...] = ("Approach", "Implementation map")


@dataclass(frozen=True)
class Finding:
    """One spec/implementation disagreement."""

    kind: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


@dataclass(frozen=True)
class Requirement:
    """One numbered SHALL statement in a spec."""

    id: str
    prefix: str
    number: int
    title: str
    spec: str
    source: Path
    withdrawn: bool = False
    exempt: bool = False
    pending: bool = False
    # The Markdown file named by a `documentation` annotation; "" when it names none.
    documentation: str | None = None


def load_prefixes(readme: Path) -> dict[str, str]:
    """Read the prefix registry table from `specs/README.md` (SPEC-1)."""
    prefixes: dict[str, str] = {}
    for line in readme.read_text().splitlines():
        match = _PREFIX_ROW.match(line)
        if match:
            prefixes[match["prefix"]] = match["spec"]
    return prefixes


def spec_names(prefixes: dict[str, str]) -> list[str]:
    """The registered spec directories, sorted and without repeats."""
    return sorted(set(prefixes.values()))


def parse_requirements(path: Path, spec: str) -> list[Requirement]:
    """Extract every requirement heading and its body annotations from a spec."""
    found: list[Requirement] = []
    current: Requirement | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal current, body
        if current is not None:
            text = "\n".join(body)
            doc = _DOCUMENTATION.search(text)
            found.append(
                replace(
                    current,
                    exempt=_EXEMPT_MARKER in text,
                    pending=_PENDING_MARKER in text,
                    documentation=None if doc is None else (doc["file"] or ""),
                )
            )
        current, body = None, []

    for line in path.read_text().splitlines():
        match = _REQ_HEADING.match(line)
        if match:
            flush()
            title = match["title"]
            current = Requirement(
                id=match["id"],
                prefix=match["prefix"],
                number=int(match["number"]),
                title=title.removesuffix(_WITHDRAWN_SUFFIX).strip(),
                spec=spec,
                source=path,
                withdrawn=title.endswith(_WITHDRAWN_SUFFIX),
            )
        elif current is not None:
            body.append(line)

    flush()
    return found


def load_all_requirements(specs_dir: Path, prefixes: dict[str, str]) -> list[Requirement]:
    """Parse the requirements of every registered spec directory.

    Each requirement's `source` is relative to the directory holding `specs_dir`.
    """
    found: list[Requirement] = []
    for spec in spec_names(prefixes):
        path = specs_dir / spec / "requirements.md"
        if path.is_file():
            found.extend(
                replace(req, source=path.relative_to(specs_dir.parent))
                for req in parse_requirements(path, spec)
            )
    return found


def check_ids(requirements: list[Requirement]) -> list[Finding]:
    """Flag IDs defined by more than one heading (SPEC-6)."""
    seen: dict[str, Requirement] = {}
    findings: list[Finding] = []
    for req in requirements:
        if req.id in seen:
            findings.append(
                Finding(
                    "duplicate-id",
                    f"{req.id} is defined twice: {seen[req.id].source} and {req.source}",
                )
            )
        else:
            seen[req.id] = req
    return findings


def sections(text: str) -> set[str]:
    """The `## ` section titles of a Markdown document."""
    return {
        line.removeprefix("## ").strip() for line in text.splitlines() if line.startswith("## ")
    }


def check_structure(specs_dir: Path, prefixes: dict[str, str]) -> list[Finding]:
    """Flag specs missing a mandatory file or section (SPEC-7)."""
    findings: list[Finding] = []
    for spec in spec_names(prefixes):
        for filename, required in (
            ("requirements.md", REQUIRED_REQUIREMENTS_SECTIONS),
            ("design.md", REQUIRED_DESIGN_SECTIONS),
        ):
            path = specs_dir / spec / filename
            if not path.is_file():
                findings.append(Finding("missing-spec-file", f"{spec}/{filename} does not exist"))
                continue
            present = sections(path.read_text())
            findings.extend(
                Finding("missing-section", f"{spec}/{filename} has no '## {section}' section")
                for section in required
                if section not in present
            )
    return findings


def check_spec_markdown(specs_dir: Path, prefixes: dict[str, str]) -> list[Finding]:
    """Flag a `requirements.md` that leaves a code fence open (SPEC-9).

    Claims inside a fence are ignored, so an unclosed fence would silently
    hide every claim below it.
    """
    findings: list[Finding] = []
    for spec in spec_names(prefixes):
        path = specs_dir / spec / "requirements.md"
        if not path.is_file():
            continue
        in_fence = False
        for line in path.read_text().splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
        if in_fence:
            findings.append(
                Finding("unclosed-code-fence", f"{spec}/requirements.md has an unclosed code fence")
            )
    return findings
