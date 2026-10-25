"""What the consumer names: `[tool.deploy-gate]` in `pyproject.toml` (GATE-1, GATE-2)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """The gate cannot run because its configuration is missing or malformed."""


@dataclass(frozen=True)
class Config:
    code: tuple[str, ...]
    marker: str


def load_config(root: Path) -> Config:
    """Read `code` and `marker` of `[tool.deploy-gate]` in `<root>/pyproject.toml`.

    There is no built-in value for either: a missing file, table or key, or
    an empty one, is an error.
    """
    path = root / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"{path} does not exist; it must hold [tool.deploy-gate]") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from None

    table = data.get("tool", {}).get("deploy-gate")
    if not isinstance(table, dict):
        raise ConfigError(f"{path} has no [tool.deploy-gate] table")
    code = table.get("code")
    if not code:
        raise ConfigError(f"[tool.deploy-gate] in {path} has no or an empty 'code' list")
    if not isinstance(code, list) or not all(isinstance(entry, str) and entry for entry in code):
        raise ConfigError(
            f"[tool.deploy-gate] 'code' in {path} must be a list of non-empty path strings"
        )
    marker = table.get("marker")
    if not marker:
        raise ConfigError(f"[tool.deploy-gate] in {path} has no or an empty 'marker'")
    if not isinstance(marker, str):
        raise ConfigError(f"[tool.deploy-gate] 'marker' in {path} must be a string")
    return Config(code=tuple(code), marker=marker)
