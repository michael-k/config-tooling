"""Where the scan comes from: `[tool.spec-check]` in `pyproject.toml` (SPEC-15)."""

from __future__ import annotations

import tomllib
from pathlib import Path


class ConfigError(Exception):
    """The checker cannot run because its configuration is missing or malformed."""


def load_scan_globs(root: Path) -> tuple[str, ...]:
    """Read the `scan` globs of `[tool.spec-check]` in `<root>/pyproject.toml`.

    There is no built-in list: a missing file, table or list, or an empty
    list, is an error (SPEC-15).
    """
    path = root / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"{path} does not exist; it must hold [tool.spec-check]") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from None

    table = data.get("tool", {}).get("spec-check")
    if not isinstance(table, dict):
        raise ConfigError(f"{path} has no [tool.spec-check] table")
    scan = table.get("scan")
    if not scan:
        raise ConfigError(f"[tool.spec-check] in {path} has no or an empty 'scan' list")
    if not isinstance(scan, list) or not all(isinstance(glob, str) and glob for glob in scan):
        raise ConfigError(
            f"[tool.spec-check] 'scan' in {path} must be a list of non-empty glob strings"
        )
    return tuple(scan)


def expand_globs(root: Path, globs: tuple[str, ...]) -> list[Path]:
    """The files matched by `globs`, relative to `root`, sorted and without repeats."""
    matched: set[Path] = set()
    for glob in globs:
        try:
            paths = list(root.glob(glob))
        except (ValueError, NotImplementedError) as error:
            raise ConfigError(f"scan glob {glob!r} is not usable: {error}") from None
        matched.update(path.relative_to(root) for path in paths if path.is_file())
    return sorted(matched)
