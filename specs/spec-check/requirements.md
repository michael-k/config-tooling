# Spec Checker — Requirements

**Prefix:** `SPEC`

## Purpose

Every repository that uses this tooling declares its `specs/` tree
authoritative and makes `make spec-check` the gate for a change. The
checker is what makes the mechanical half of that claim hold: every
requirement is cited by the code that realises it, every citation names a
requirement that exists, every spec has the shape the tree's README gives
it, and every design's implementation map says what the code says. Without
it the links between spec and code are kept by hand, and the four copies of
it that existed before this package showed how they drift: each repository
patched its own, and none of them compared a map with the code.

The subject below is **THE Spec Checker**: the `spec-check` package and the
`spec-check` command it installs. It reads the tree of the repository it is
run in, which is the consumer's tree, not this one's, unless it is run here.

## Scope

### In scope

- Which prefixes and requirements exist, and where the checker learns them.
- Citations: which files are read, what counts as one, and which citations
  are findings.
- The shape of each spec: its files and their sections.
- The allowance registers and their claims.
- The implementation maps, held to the code.
- The traceability index: when it is written and how its currency is
  checked.
- The command line: scoping, exit status and what it prints.

### Out of scope

- The tree's own rules as prose, which each repository's `specs/README.md`
  states. This spec states what the checker enforces of them; a rule the
  README states and the checker does not enforce is the README's alone.
- Whether a citation is true: that a file citing an ID really realises it
  is a reviewer's judgment. The checker sees only that the ID is written.
- Formatting and prose style of the specs.
- How a repository runs the checker. `PRJ-2` states how it is installed;
  the make target belongs to each repository.

## Security invariants

**Upholds:** INV-1. The checker reads the repository it is run in and
writes one file in it, the traceability index (`SPEC-18`); it reads nothing
inside a submodule (`SPEC-14`), so a consumer's checkout of this repository
is never part of the consumer's tree.
**Relies on:** none
**Allowances claimed:** none

## Requirements

### SPEC-1 — The prefix registry is the only source of prefixes

THE Spec Checker SHALL take the valid prefixes and the spec directory each
belongs to from the prefix registry table in `specs/README.md`, and from
nowhere else.

**Why:** A prefix that is known in two places is known differently in one
of them sooner or later. The registry is the table a reader consults; if
the checker read anything else, a prefix could be valid to one and not the
other.
**Verified:** a tree whose registry lists a prefix the checker has never
seen is checked under that prefix, and a tree whose registry omits one makes
its citations unknown.

### SPEC-2 — Every requirement is cited

THE Spec Checker SHALL report every requirement that is neither exempt,
pending nor withdrawn and that no scanned file other than a Markdown file
cites.

**Why:** A requirement nothing cites is one nobody can find in the code, and
nothing shows whether it holds. The annotations of `specs/README.md` §3 are
the only ways for a requirement to have no citation, and each of them says
why. A citation in documentation does not count: a README line that
restates a requirement nothing else cites would make it look realised and
erase the gap `pending` exists to show. One repository stated this as a
rule for its authors; the checker makes it hold everywhere.
**Verified:** a tree with an uncited requirement fails and names it, and so
does one whose only citation is in a `.md` file; the same tree with the
requirement annotated `exempt` or `pending` passes.

### SPEC-3 — Every citation names a requirement

THE Spec Checker SHALL report every citation, with a registered prefix,
of an ID that no requirement heading defines.

**Why:** A citation of a requirement that does not exist points a reader at
nothing, and is usually a typo or a renumbering that missed a file.
**Verified:** a scanned file citing `<prefix>-99` in a tree without it fails
and names the file.

### SPEC-4 — No citation of a withdrawn requirement

THE Spec Checker SHALL report every citation of a withdrawn requirement.

**Why:** Withdrawn means nothing realises the requirement any more. Code
still citing it claims a rule the spec has retired, which is the drift the
gate exists to stop.
**Verified:** a file citing a requirement whose heading ends in
` (withdrawn)` fails and names both.

### SPEC-5 — No citation of a pending requirement

THE Spec Checker SHALL report every citation of a pending requirement.

**Why:** `pending` says a requirement is specified and not yet realised,
and that is why the orphan check exempts it. A citation contradicts the
annotation: it makes the requirement look realised in the index and erases
the gap the annotation exists to show. It is resolved by removing the
citation or the annotation, never by leaving both.
**Verified:** a file citing a requirement annotated `pending` fails and
names both.

### SPEC-6 — Every ID is defined once

THE Spec Checker SHALL report every requirement ID defined by more than one
heading.

**Why:** Two requirements under one ID make every citation of it ambiguous,
and the index would list one of them under the other's title.
**Verified:** a tree with one ID under two headings fails and names both
places.

### SPEC-7 — Every spec has its files and sections

THE Spec Checker SHALL report every registered spec that lacks a
`requirements.md` with `Purpose`, `Scope`, `Security invariants` and
`Requirements` sections, or a `design.md` with `Approach` and
`Implementation map` sections.

**Why:** The templates of `specs/README.md` give every spec the same
shape, so a reader knows where to look. A missing section is usually a
missing thought: a design with no failure modes is common, one with no map
cannot be checked at all.
**Verified:** a tree missing each file or section in turn fails and names
what is missing.

### SPEC-8 — Allowances and their claims pair up

THE Spec Checker SHALL report every allowance in the register that no
requirements file claims, and every claim of an allowance the register does
not hold.

**Why:** An allowance is a named exception to an invariant with a
compensating control. A register row nobody claims is an exception that
outlived its reason; a claim with no row is an exception nobody wrote the
control for.
**Verified:** a tree with an unclaimed register row fails, and so does one
with a claim and no row; a claim inside a fenced code block is not a claim.

### SPEC-9 — No unclosed code fence

THE Spec Checker SHALL report every `requirements.md` that leaves a code
fence open.

**Why:** Claims inside a fence are ignored (`SPEC-8`), so an unclosed fence
silently hides every real claim below it, and the register check passes on
a tree it never read.
**Verified:** a `requirements.md` with an odd number of fence lines fails.

### SPEC-10 — Every mapped path exists

THE Spec Checker SHALL report every implementation map row whose path does
not exist.

**Why:** A map that names a moved or deleted file sends a reader to nothing.
**Verified:** a map row naming a missing file fails and names the design.

### SPEC-11 — A map row says what its file cites

THE Spec Checker SHALL report every implementation map row, for a file the
scan reads, whose IDs differ from the IDs of that spec's prefixes that the
file cites.

**Why:** A map is the path-to-requirements view of a design, and the
citations are the code's own statement of the same thing. Written by hand
and checked only for existence, the maps of the four repositories had
drifted from the code by more than two hundred rows before this rule. With
it, a citation added or removed without its row fails the gate.
**Verified:** a row listing an ID its file does not cite fails, and so does
a file citing an ID its row does not list; the finding names both sides of
the difference.

### SPEC-12 — Every citing file has a row

THE Spec Checker SHALL report every scanned file, other than a Markdown
file, that cites an ID of a spec whose implementation map has no row for it.

**Why:** Without this rule a file could avoid `SPEC-11` by having no row.
Markdown files document requirements rather than realise them, so they
neither need nor get a row (`specs/README.md` §4).
**Verified:** a scanned `.py` file citing an ID with no row in that spec's
map fails; a scanned `.md` file citing the same ID does not.

### SPEC-13 — A map row names one file and lists its IDs one by one

THE Spec Checker SHALL report every implementation map row that names a
directory containing a scanned file, that names a Markdown file, or that
writes its IDs as a range.

**Why:** A directory row would hide which file realises what, and a scanned
file under it would need its own row anyway (`SPEC-12`). A Markdown file
documents rather than realises, and `specs/README.md` §4 gives it no row. A
range such as
`XFR-1 … XFR-6` cannot be found by searching for `XFR-3`, and it claims
every ID between its ends whether the file cites them or not.
**Verified:** a row naming a directory that holds a scanned file fails; a
row naming a directory that holds none passes; a row naming a `.md` file
fails; a row containing `…` or a dash between two IDs fails.

### SPEC-14 — Nothing inside a submodule is read

THE Spec Checker SHALL NOT read any file inside a git submodule of the
repository it checks.

**Why:** Every consumer has this repository as a submodule at
`config-tooling/`, and this repository is full of IDs: its own, and the
fixtures of its tests. A scan glob that reaches into the submodule would
count them as the consumer's citations. Excluding submodules in the checker
means no consumer has to remember to.
**Verified:** a tree with a submodule whose files match the scan globs and
cite registered IDs reports none of them, in the citations or in the index.

### SPEC-15 — The scan is configured, never assumed

THE Spec Checker SHALL read the files matched by the `scan` globs in the
`[tool.spec-check]` table of the repository's `pyproject.toml`, and SHALL
fail when that table or its `scan` list is missing or empty.

**Why:** Which files can carry a citation differs by repository: one has
filter plugins, another scripts, another inventory examples. The four
copies of the checker each had their own list in code, and each had a
directory it forgot. A configured list is visible in one place and
comparable across repositories, and a missing one is a failure, because a
built-in default would be a list nobody chose.
**Verified:** a tree with no `[tool.spec-check]` fails with a message
naming the table; one with globs reads exactly the matched files.

### SPEC-16 — The superseded numbering is gone

THE Spec Checker SHALL report every scanned line that cites a requirement in
the superseded `Requirement N.M` form.

**Why:** Each of the four repositories once numbered requirements that way.
A surviving reference points at a numbering that no longer exists, and the
form is distinctive enough to find mechanically.
**Verified:** a scanned file containing `Requirement 2.3` fails and names the
file and line.

### SPEC-17 — Pending requirements are listed on every run

THE Spec Checker SHALL print every pending requirement on every run.

**Why:** A gap recorded once is forgotten. Printing the list each time keeps
it in front of whoever runs the gate (`specs/README.md` §3).
**Verified:** a tree with two pending requirements prints both IDs, with
and without findings.

### SPEC-18 — The index is written after a clean full run, and nothing else

THE Spec Checker SHALL write `specs/_traceability.md` only after a run that
covered the whole tree and found nothing, and SHALL write no other file.

**Why:** The index is generated, never edited, so it must come from a tree
that passes; written from a failing or a scoped run it would record a state
the gate rejected, or one spec's rows as if they were all.
**Verified:** a run with a finding, and a run scoped to one spec, leave the
index untouched; a clean full run writes it, and no other file in the tree
changes.

### SPEC-19 — A stale index fails a check run

WHEN run with `--check`, THE Spec Checker SHALL write nothing and SHALL
report an index that differs from the one a clean full run would write.

**Why:** A change that adds a citation and forgets to regenerate the index
leaves a committed index that lies. Each repository used to guard this with
a test of its own; one mode of the checker does it the same way everywhere.
**Verified:** a tree whose index lacks a new citation fails under
`--check` and is unchanged afterwards.

### SPEC-20 — Scoped to one spec, judged whole where it must be

WHEN run with `--spec <name>`, THE Spec Checker SHALL limit every check to
the named specs except the allowance pairing, which it SHALL judge over the
whole tree.

**Why:** Scoping makes a large tree's output readable while one spec is
being changed. Whether an allowance is claimed is a property of the whole
tree, because the claimant can live in a spec outside the scope; judged
inside the scope, a correct register would fail.
**Verified:** a scoped run reports an uncited requirement of the named spec
and not one of another; an allowance claimed by another spec is not
reported as unclaimed.

### SPEC-21 — The exit status says what happened

THE Spec Checker SHALL exit with 0 when it found nothing, 1 when it found
anything, and 2 when it could not run as asked.

**Why:** The make target and CI read only the status. A run that could not
start, such as a `--spec` naming no registered spec or a missing
configuration, is not the same as a tree that fails, and the caller should
be able to tell.
**Verified:** each of the three cases returns its status.
