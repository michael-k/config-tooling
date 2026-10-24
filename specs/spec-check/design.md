# Spec Checker — Design

## Approach

The checker is the single-file `tests/spec_check.py` the four repositories
carried, split into a package by concern and changed in four ways: the scan
comes from configuration instead of code (`SPEC-15`), submodules are never
read (`SPEC-14`), the maps are held to the citations (`SPEC-11`, `SPEC-12`,
`SPEC-13`), and the index currency that each repository tested on its own
becomes the `--check` mode (`SPEC-19`). One repository's check that a
pending requirement is not cited (`SPEC-5`) becomes everyone's. Everything else
behaves as the copies did.

A run starts in the current directory, which is the repository's root: the
make target runs it from there. It reads `[tool.spec-check]` from
`pyproject.toml` with `tomllib`, the registry from `specs/README.md`, and
every `requirements.md` and `design.md` of a registered spec. It expands the
`scan` globs, drops every path git ignores (`SPEC-23`) and every path inside
a submodule listed in `.gitmodules`, and finds citations in what remains
with one pattern built from the registered prefixes, so an ID with an
unregistered prefix is not a citation at all. Each check returns findings;
the command line prints them sorted, prints the pending list, and then
writes, compares or leaves the index.

The package installs a `spec-check` command, and `python -m spec_check`
runs the same entry point.

## Implementation map

| Path | Realises |
|---|---|
| `spec-check/src/spec_check/config.py` | SPEC-15 |
| `spec-check/src/spec_check/tree.py` | SPEC-1, SPEC-6, SPEC-7, SPEC-9 |
| `spec-check/src/spec_check/citations.py` | SPEC-2, SPEC-3, SPEC-4, SPEC-5, SPEC-14, SPEC-16, SPEC-22, SPEC-23, SPEC-24 |
| `spec-check/src/spec_check/allowances.py` | SPEC-8 |
| `spec-check/src/spec_check/maps.py` | SPEC-10, SPEC-11, SPEC-12, SPEC-13 |
| `spec-check/src/spec_check/index.py` | SPEC-18, SPEC-19 |
| `spec-check/src/spec_check/cli.py` | SPEC-17, SPEC-18, SPEC-19, SPEC-20, SPEC-21, SPEC-24 |
| `spec-check/tests/test_config.py` | SPEC-15, SPEC-21 |
| `spec-check/tests/test_tree.py` | SPEC-1, SPEC-6, SPEC-7, SPEC-9 |
| `spec-check/tests/test_citations.py` | SPEC-2, SPEC-3, SPEC-4, SPEC-5, SPEC-14, SPEC-16, SPEC-22, SPEC-23 |
| `spec-check/tests/test_allowances.py` | SPEC-8, SPEC-20 |
| `spec-check/tests/test_maps.py` | SPEC-10, SPEC-11, SPEC-12, SPEC-13 |
| `spec-check/tests/test_cli.py` | SPEC-17, SPEC-18, SPEC-19, SPEC-20, SPEC-21, SPEC-24 |

## Key decisions

**The map is compared within the spec's own prefixes.** A file may cite IDs
of several specs; the row in one spec's map lists only that spec's. A file
citing `INCUS-1` and `PRJ-3` has a row in each of the two maps, each with
its own ID.

**Markdown is told by its suffix.** A scanned file ending in `.md` is
documentation: its citations appear in the index, but they do not make a
requirement cited (`SPEC-2`), and it gets no row, and a row for one is a finding (`SPEC-13`): its IDs
could only equal its citations if someone kept them equal by hand.

**Paths the scan does not read keep their rows unchecked.** A row for
`pyproject.toml`, an inventory directory or a file type no glob matches has
no citations to compare with, so only `SPEC-10` applies to it. That is what
lets a map name configuration that realises a requirement without carrying
an ID.

**Submodules come from `.gitmodules`.** The file lists every submodule's
path and is committed. A path inside any listed submodule is dropped
before any check sees it.

**A range is `…`, or a dash between two IDs.** The tree's templates used
`XFR-1 … XFR-6`; any row whose ID column holds `…`, or an ID followed by a
dash or an en dash and another ID, is a range.

**No built-in scan list.** The previous copies each had their own list in
code; making the list configuration means it is visible in one place in
each repository and the same shape everywhere. There is no configured
exclusion list: the only file every copy excluded was the checker's own test
module, which now lives here and uses unregistered prefixes for its fixtures
(`TEST-2`). What is not a source is already listed, in each consumer's
ignore rules (`SPEC-23`).

**Git decides what is not a source.** The scan passes its glob matches
to `git check-ignore --stdin` and drops every path it names (`SPEC-23`).
Asking `git` rather than parsing `.gitignore` applies every rule git
applies, nested ignore files, `.git/info/exclude` and the user's global
excludes included, and covers the caches that carry their own
`.gitignore`, such as mypy's and ruff's, without the consumer listing
them. `check-ignore` does not name a tracked file even when a pattern
matches it, which is git's own meaning of ignored. A submodule's files are
dropped by its own filter (`SPEC-14`), not by this one. The checker's
tests build their trees in temporary directories and run `git init` in
each (`TEST-2`).

**Pass or fail, then write.** The index is written only after a clean full
run (`SPEC-18`), so a committed index always comes from a tree that passed.
`--check` renders the same text and compares, which is what CI and a
pre-commit check use (`SPEC-19`).

## Failure modes

- A citation inside a string the code uses for something else, such as a
  message or a fixture value, is still a citation. In a consumer it counts;
  in this repository's tests it is avoided by using unregistered prefixes.
- A file that cites an ID for context rather than realisation gets a row it
  should not have, because the checker cannot tell the two apart. The rule
  against such citations is `specs/README.md` §4's; holding it is review's.
- A cache or build directory a consumer forgot to ignore is read, and its
  copies of IDs show as citations in files no map lists. The fix is the
  consumer's ignore rule, which `git status` was already asking for.
- `git` is missing, or the checker runs outside a work tree, such as an
  exported tarball. The run fails with exit status 2 (`SPEC-24`, `SPEC-21`)
  rather than reading everything.
- A scan glob that matches nothing is silent: the checker reports what it
  found, not what it was told to look for. A misspelt glob shows only as
  requirements that become uncited.
- Rolling this out: each consumer's maps drifted from its citations before
  `SPEC-11` and `SPEC-12` existed, so the first run in each consumer fails
  until its maps are brought to the code. That is done in the same change
  that adopts the package.

## Interactions

- `PRJ-2`: how a consumer installs the package; `PRJ-6`: this tree runs it
  on itself.
- `TEST-2`: the checker's tests build their trees in temporary directories.
- `INV-1`: the checker writes one file of the repository it runs in, and
  reads nothing outside it or inside a submodule.
