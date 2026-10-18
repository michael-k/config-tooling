"""Implementation maps, held to the paths and citations they describe.

Realises SPEC-10 (every mapped path exists), SPEC-11 (a row says what its
file cites), SPEC-12 (every citing file has a row) and SPEC-13 (a row names
one file and lists its IDs one by one).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from spec_check.citations import Citations, is_markdown
from spec_check.tree import Finding, spec_names

_MAP_ROW = re.compile(r"^\|\s*`(?P<path>[^`]+)`\s*\|(?P<ids>[^|]*)")
_ID = r"[A-Z][A-Z0-9]*-\d+"
_ID_TOKEN = re.compile(rf"\b{_ID}\b")
_RANGE = re.compile(rf"…|\b{_ID}\s*[-–]\s*{_ID}\b")
_MAP_SECTION = "Implementation map"


@dataclass(frozen=True)
class MapRow:
    """One row of a design's implementation map."""

    path: str
    ids: str

    @property
    def id_set(self) -> set[str]:
        return set(_ID_TOKEN.findall(self.ids))

    @property
    def is_range(self) -> bool:
        return _RANGE.search(self.ids) is not None


def parse_implementation_map(design: Path) -> list[MapRow]:
    """The rows of the `## Implementation map` section of a `design.md`."""
    rows: list[MapRow] = []
    in_map = False
    for line in design.read_text().splitlines():
        if line.startswith("## "):
            in_map = line.removeprefix("## ").strip() == _MAP_SECTION
            continue
        match = _MAP_ROW.match(line)
        if in_map and match:
            rows.append(MapRow(match["path"], match["ids"].strip()))
    return rows


def _prefix(req_id: str) -> str:
    return req_id.rsplit("-", 1)[0]


def citations_by_file(citations: Citations) -> dict[Path, set[str]]:
    """Invert `ID -> files` into `file -> IDs`."""
    by_file: dict[Path, set[str]] = {}
    for req_id, paths in citations.items():
        for path in paths:
            by_file.setdefault(path, set()).add(req_id)
    return by_file


def _ids(ids: set[str]) -> str:
    return ", ".join(sorted(ids, key=lambda i: (_prefix(i), int(i.rsplit("-", 1)[1])))) or "none"


def check_implementation_map(
    root: Path,
    specs_dir: Path,
    prefixes: dict[str, str],
    scanned: list[Path],
    citations: Citations,
) -> list[Finding]:
    """Hold every registered spec's implementation map to the tree and its citations."""
    findings: list[Finding] = []
    scanned_set = set(scanned)
    by_file = citations_by_file(citations)

    for spec in spec_names(prefixes):
        design = specs_dir / spec / "design.md"
        if not design.is_file():
            continue  # reported as missing-spec-file
        where = f"{spec}/design.md"
        own = {prefix for prefix, owner in prefixes.items() if owner == spec}
        rowed: set[Path] = set()

        for row in parse_implementation_map(design):
            path = Path(row.path)
            if not (root / path).exists():
                findings.append(
                    Finding(
                        "missing-implementation-path",
                        f"{where} maps {row.path}, which does not exist",
                    )
                )
                continue
            if row.is_range:
                findings.append(
                    Finding(
                        "map-range",
                        f"{where} lists the IDs of {row.path} as a range ({row.ids}); "
                        "list them one by one",
                    )
                )
            if is_markdown(path):
                findings.append(
                    Finding(
                        "map-markdown-row",
                        f"{where} has a row for {row.path}, a Markdown file, which gets none",
                    )
                )
                continue
            if (root / path).is_dir():
                inside = sorted(f for f in scanned_set if path in f.parents)
                if inside:
                    findings.append(
                        Finding(
                            "map-directory-row",
                            f"{where} maps the directory {row.path}, which holds scanned "
                            f"files ({', '.join(str(f) for f in inside)}); map each file",
                        )
                    )
                continue
            rowed.add(path)
            if path not in scanned_set:
                continue  # not scanned: only its existence is checked
            listed = row.id_set
            cited = {i for i in by_file.get(path, ()) if _prefix(i) in own}
            if listed != cited:
                findings.append(
                    Finding(
                        "map-row-mismatch",
                        f"{where} maps {row.path} to {_ids(listed)} but it cites "
                        f"{_ids(cited)}: listed but not cited: {_ids(listed - cited)}; "
                        f"cited but not listed: {_ids(cited - listed)}",
                    )
                )

        for path in sorted(scanned_set - rowed):
            if is_markdown(path):
                continue
            cited = {i for i in by_file.get(path, ()) if _prefix(i) in own}
            if cited:
                findings.append(
                    Finding(
                        "unmapped-citing-file",
                        f"{path} cites {_ids(cited)} but {where} has no row for it",
                    )
                )
    return findings
