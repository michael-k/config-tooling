# Specs — Authoritative Source of Truth

## 1. Authority

The `specs/` tree is the authoritative source of truth for this project. A
mismatch between a spec and the implementation is a bug — it does not matter
which side is "more correct" in the moment, the spec wins by definition. A
change to behaviour starts by editing the spec, gets reviewed as a spec
change, and only then is the implementation brought to match it.

## 2. Audience

`specs/` is written for developers, reviewers and auditors: it states what
the tooling SHALL do and why, in requirement form, so a change to behaviour
can be reviewed against a fixed statement of intent. The `README.md` of each
package is separate and serves a different audience: it is how-to material
for the repositories that use the package, not a restatement of the
requirements.

## 3. Requirement ID scheme

Every requirement has an ID of the form `PREFIX-N`, where `PREFIX` identifies
the spec (see the registry below) and `N` is a plain integer. IDs are flat
per spec — there is no sub-numbering. Each ID states exactly one `SHALL`. IDs
are permanent: once assigned, an ID is never renumbered and never reused,
even after the requirement it named is retired. A retired requirement keeps
its heading, with ` (withdrawn)` appended to the title, so the ID remains
visible in the document rather than disappearing.

Three body annotations cover requirements that are not backed by an ordinary
code citation:

- `**Traceability:** exempt — <reason>` marks a prose requirement that has no
  code site to cite (for example, a statement of scope or an invariant that
  other specs uphold).
- `**Traceability:** pending — <reason>` marks a requirement that is intended
  but not yet realised in the implementation.
- `**Traceability:** documentation — <file>` marks a requirement whose
  deliverable is documentation, such as a section a README must have. Such
  a requirement is cited by the named Markdown file, and by no other
  Markdown file.

A `pending` requirement is not a one-time note: `make spec-check` reports
every pending requirement and marks it in the traceability index on every
run, so the gap stays visible instead of being recorded once and forgotten.

## 4. Reference direction

Code cites the spec: a comment, docstring or test name references a
requirement ID (e.g. `SPEC-2`) so a reader can find the rule it implements.
A file cites an ID only where it realises or tests that requirement; a
requirement mentioned for context is named by its spec, not its ID. Those
IDs are what `make spec-check` reads and what the traceability index is
built from. Documentation may cite a requirement too, but a citation in a
Markdown file does not count as realising it: a requirement cited only by
documentation is uncited, unless it is annotated `documentation` and the
citation is in the file the annotation names.

Specs may name code. `**Verified:**` notes and `design.md` files name files,
tests and task names where that is the clearest way to state a fact. They
name the file, never a line in it: line numbers go stale on any edit above
them, and nothing checks them.

### Implementation map

Every `design.md` has an `## Implementation map`, a table with one row per
path and the IDs of this spec that the path realises or tests.
`make spec-check` holds the map to the code:

- A row names one file. A directory may be named only where the scan reads
  none of the files in it.
- The row of a file the scan reads lists exactly the IDs of this spec's
  prefixes that the file cites.
- Every file the scan reads that cites an ID of this spec has a row, except
  Markdown files, which document a requirement and neither need nor get one.
- The row of a path the scan does not read, such as a directory, is
  checked only for the path's existence.
- IDs are listed one by one, never as a range, so a search for an ID finds
  every row that names it.

What the scan reads is set in `[tool.spec-check]` in `pyproject.toml`.

## 5. Prefix registry

This table is the single source of truth for prefixes. The checker parses
it to know which prefixes and spec directories are valid; do not hardcode
prefixes anywhere else.

| Prefix | Spec directory | Implemented by |
|---|---|---|
| `PRJ` | `project` | `pyproject.toml`, `Makefile` |
| `SPEC` | `spec-check` | `spec-check/` |
| `INCUS` | `incus-tooling` | `incus/` |
| `GATE` | `deploy-gate` | `deploy-gate/` |
| `TEST` | `testing` | `spec-check/tests/`, `incus/tests/` |

`INV` and `ALW` are reserved for `specs/project/security-invariants.md` and
are exempt from the orphan check — invariants are cited by specs, not by
code.

## 6. `requirements.md` template

Every feature spec's `requirements.md` starts from this template:

````markdown
# <Feature> — Requirements

**Prefix:** `SPEC`

## Purpose

One paragraph: what this feature is for and what would be worse without it.

## Scope

### In scope
### Out of scope

## Security invariants

**Upholds:** INV-1
**Relies on:** none
**Allowances claimed:** none

## Requirements

### SPEC-2 — Every requirement is cited

THE Spec Checker SHALL report every requirement that is neither exempt,
pending nor withdrawn and that no scanned file cites.

**Why:** A requirement nothing cites is one nobody can find in the code, and
the spec tree's claim to be authoritative rests on that link.
**Verified:** a tree with an uncited requirement makes `make spec-check` exit
non-zero and name it.
````

## 7. `design.md` template

Every feature spec's `design.md` starts from this template:

````markdown
# <Feature> — Design

## Approach

## Implementation map

| Path | Realises |
|---|---|
| `spec-check/src/spec_check/citations.py` | SPEC-2, SPEC-3, SPEC-4 |

## Key decisions

## Failure modes

## Interactions

Named by requirement ID: what this spec assumes of others, and what others assume of it.
````

## 8. Change process

1. Edit the spec first — `requirements.md`, and `design.md` if the approach
   changes.
2. Get the spec change reviewed.
3. Bring the implementation to match the spec.
4. Run `make spec-check`. It is the gate: every non-exempt, non-pending
   requirement must be cited, and every citation must name an existing
   requirement. `make spec-check` runs the `spec-check` package from
   `spec-check/`, whose `SPEC` spec states the checker's rules.

## 9. Index of specs

- [`project`](project/requirements.md) — What this repository is, how the repositories that use it take it in, and its tooling.
- [`spec-check`](spec-check/requirements.md) — The spec checker every repository's `make spec-check` runs.
- [`incus-tooling`](incus-tooling/requirements.md) — The Incus virtual-machine toolkit integration tests are built on.
- [`deploy-gate`](deploy-gate/requirements.md) — The gate that refuses a deployment until a complete integration run has passed on its code.
- [`testing`](testing/requirements.md) — This repository's own test suites.

`project/security-invariants.md` holds the cross-cutting security invariants
(`INV`) and allowance registers (`ALW`) that other specs uphold or rely on.

## 10. Traceability index

`specs/_traceability.md` is generated by `make spec-check` and must not be
hand-edited. Any change to it should come from re-running `make spec-check`,
not from a manual patch.
