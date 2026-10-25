# Testing — Design

## Approach

Each package carries its tests next to its source: `spec-check/tests/`,
`incus/tests/` and `deploy-gate/tests/`, and the repository's own layout is
checked by `tests/test_project.py`. The root `pyproject.toml` lists all four
as pytest test paths and defines two markers, `unit` and `integration`; `make
test-unit` selects the first and `make test-integration` the second, and
`make test` runs both.

The checker's tests write a minimal tree for each case under `tmp_path`: a
`specs/README.md` with a registry of made-up prefixes such as `FOO` and
`BAR`, the spec files the case needs, a `pyproject.toml` with a
`[tool.spec-check]` scan, and the files to be scanned. They call the
checker's functions on that root, or its command line with the root as the
working directory, and assert on the findings and the exit status.

The toolkit's unit tests replace `subprocess.run` and assert on the
commands the package would run, as they did in the consumer it came from. The
integration tier (`TEST-3`) is the place for what those cannot show.

## Implementation map

| Path | Realises |
|---|---|
| `pyproject.toml` | TEST-1 |
| `Makefile` | TEST-1 |
| `spec-check/tests/conftest.py` | TEST-2 |

## Key decisions

**Tests beside their package.** A consumer installs a package from its
directory, and the tests travel with it; anyone changing a package sees its
tests in the same directory. The packages do not ship their tests: `uv`
builds from `src/`.

**Made-up prefixes for fixtures.** The checker's tests are full of IDs.
Written with this tree's prefixes, they would be citations of this tree's
requirements, or citations of IDs that do not exist. Unregistered prefixes
are invisible to `make spec-check` by construction (`SPEC-1`), so no
exclusion is needed (`TEST-2`).

## Failure modes

- A fixture written with a registered prefix by mistake shows up in
  `make spec-check` as an unknown or extra citation, and in the map check as
  a citation the test module's row does not list. The failure is loud.
- Without Incus, the integration tier is skipped rather than failed
  (`INCUS-10`), so a run on a developer's laptop says nothing about it.

## Interactions

- `PRJ-5`: the make targets that run the tiers.
- `SPEC`, `INCUS`: the requirements the tests verify.
