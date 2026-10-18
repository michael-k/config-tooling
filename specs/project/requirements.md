# Project — Requirements

**Prefix:** `PRJ`

## Purpose

Four repositories share a way of working: an authoritative spec tree
checked by `make spec-check`, and integration tests that launch their own
Incus machines. Each of them used to carry its own copy of the checker and
reach the Incus toolkit inside one of them, and the copies drifted apart.
This repository holds the one shared copy of both, and each of the four
takes it in the same way and pins the version it uses. This spec states
what the repository is, how a consumer takes it in, and the tooling it
offers its own developers.

## Scope

### In scope

- The two packages the repository provides and where they live.
- How a consuming repository takes them in and pins their version.
- That the repository depends on nothing in any consumer.
- The Python version, the environment and the make targets.
- That the repository checks its own spec tree with its own checker.

### Out of scope

- What the checker checks — `SPEC`'s.
- What the toolkit offers — `INCUS`'s.
- This repository's own tests — `TEST`'s.
- How a consumer configures its scan and runs its suites. That is each
  consumer's own spec; this spec states only what a consumer can rely on.
- Publishing the packages to an index. Nothing is built or uploaded: a
  consumer installs from the submodule's working tree.

## Security invariants

**Upholds:** none. The invariants bind what the tooling does when it runs;
this spec states how the repository is laid out and taken in.
**Relies on:** none
**Allowances claimed:** none

## Requirements

### PRJ-1 — Two packages, installed separately

THE Repository SHALL provide the `incus` toolkit and the `spec-check`
checker as two packages, each installable on its own from its own directory,
`incus/` and `spec-check/`.

**Why:** Every consumer runs the checker, but not every consumer has an
integration tier, and the toolkit pulls in what the checker does not need.
Two packages let a consumer take only what it uses, and let a change to one
be bumped without touching the other's users.
**Verified:** each directory carries its own `pyproject.toml`; `uv build`
in either builds that package alone.

### PRJ-2 — Taken in as a submodule

THE Repository SHALL be usable by a consumer as a git submodule mounted at
`config-tooling/`, with each package installed from there as an editable
`uv` path dependency.

**Why:** A path inside the consumer's own checkout needs no package index,
no release and no credentials, and works offline and in CI alike. The
submodule's commit is the version a consumer uses: it is recorded in the
consumer's history, it changes only in a commit that says so, and every
clone of the consumer at one commit gets the same tooling. The earlier
arrangement, a path to a sibling checkout of the consumer that held the
toolkit, worked only where that checkout happened to sit next to the
consumer, and at whatever commit it happened to be.
**Verified:** a consumer with `config-tooling` added at `config-tooling/`
and `[tool.uv.sources]` pointing at `config-tooling/incus` and
`config-tooling/spec-check` runs `uv sync`, `make test-unit` and
`make spec-check` from a fresh clone made with `--recurse-submodules`.

### PRJ-3 — Nothing from any consumer

THE Repository SHALL NOT import, read or name a file, a variable or a
default of any repository that uses it.

**Why:** The repository exists because a shared toolkit that lived inside
one consumer carried that consumer's names into every other one: machine
prefixes, image aliases, a knock sequence. Shared code that names a
consumer has a favourite, and the others inherit its defaults without
noticing. A value only one consumer needs is that consumer's to pass in.
**Verified:** the `INCUS-1` unit tests in `incus/tests/` show that the
toolkit takes each project-specific value from its caller and falls back
to none, and the checker reads its scan from the consumer's
`[tool.spec-check]` (`SPEC-15`). This repository keeps no list of the
consumers' names: such a list would name them, and it could never be
complete. Each consumer knows its own names and defaults and can search
its `config-tooling/` submodule for them.

### PRJ-4 — Python 3.14 through `uv`

THE Repository SHALL require Python 3.14 or newer and run every Python tool
through `uv`.

**Why:** The consumers already require 3.14 and run everything through
`uv`; a shared package with a lower floor would be tested against a
version none of its users runs, and one with a higher floor would not
install in them.
**Verified:** both packages and the root `pyproject.toml` declare
`requires-python = ">=3.14"`, and every make target runs its tool with
`uv run`.

### PRJ-5 — The same make targets as the consumers

THE Repository SHALL offer `test`, `test-unit`, `test-integration`, `python-lint`,
`python-lint-fix`, `python-typecheck`, `spec-check`, `lint` and `clean` as
make targets with the same meaning they have in the consumers.

**Why:** A developer moving between the five repositories should not have
to learn a sixth way of running the same checks, and an agent following a
consumer's instructions should find the same targets here.
**Verified:** `make help` lists each target, and each runs the tool its
name says.

### PRJ-6 — Checked by its own checker

THE Repository SHALL check its own spec tree with the `spec-check` package
from its own working tree.

**Why:** The checker is the gate every consumer's change passes. Running it
on the tree that specifies it means a change to the checker meets its own
rules before any consumer sees it, and a spec change here is held to the
same standard as everywhere else.
**Verified:** `make spec-check` runs the checker installed from
`spec-check/` as a workspace member, not from a submodule, and passes on
this tree.
