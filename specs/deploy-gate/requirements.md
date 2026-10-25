# Deploy Gate — Requirements

**Prefix:** `GATE`

## Purpose

Each repository that uses this tooling deploys to live hosts, and each has
an integration tier that runs the same deployment against machines it
launches and throws away. A change that renders correctly can still leave a
host nothing can reach, and the throwaway machine is the only place to find that out for free. A rule that
relies on remembering to run the tier first is skipped exactly when a change
looks too small to need it. The gate turns the rule into a refusal: a
complete, passing integration run records a fingerprint of the code it
proved, and the deployment refuses to start unless the code still has that
fingerprint.

The gate first existed inside one consumer. This package is that gate with
everything the consumer knew about itself taken out: which files make up its
deployment code and which marker selects its integration tier are the
consumer's to say.

The subject below is **THE Deploy Gate**: the `deploy-gate` package, the
`deploy-gate` command it installs, and the pytest plugin it ships. It works
on the repository it is run in, which is the consumer's, not this one.

## Scope

### In scope

- Where the gate learns the deployment code and the integration marker.
- The fingerprint: which files it covers and how it is computed.
- When a pytest session records a passing run, and where.
- The check: what it compares, and how it refuses.
- How a consumer brings the plugin into its suite.

### Out of scope

- Which make target runs the check and which runs the tier. Each consumer's
  own spec names its deploying targets and makes them run `deploy-gate`
  first.
- What the integration tier tests, and how it launches machines (`INCUS`).
- Anything outside the deployment code a consumer names, such as its
  inventory, its vault or a base image. A change there does not close the
  gate; the consumer decides what its code is.
- Stopping an operator who means to deploy without a run. The gate guards
  against forgetting, not against intent.

## Security invariants

**Upholds:** INV-1. The gate reads the repository it is run in and writes
one file in it, `.integration-passed` at its root (`GATE-4`); it acts on no
machine.
**Relies on:** none
**Allowances claimed:** none

## Requirements

### GATE-1 — The deployment code is named by the consumer

THE Deploy Gate SHALL take the paths that make up the deployment code from
the `code` list of the `[tool.deploy-gate]` table in the repository's
`pyproject.toml`, and fail when that table or its `code` list is missing or
empty.

**Why:** What decides how a deployment runs differs by repository: one has
filter plugins, another a collections requirements file, another a second
playbook. The consumer the gate came from listed its own directories in
code, which is the list this package must not carry (`PRJ-3`). A missing
list is a failure, because a built-in default would be a list nobody chose,
and an empty one would fingerprint nothing and open the gate on any change.
**Verified:** a repository with no `[tool.deploy-gate]`, or with no or an
empty `code` list, makes the command and the plugin fail with a message
naming the table and the key.

**Traceability:** pending — the package does not exist yet.

### GATE-2 — The integration tier is named by the consumer

THE Deploy Gate SHALL take the marker that selects the integration tier
from the `marker` string of the `[tool.deploy-gate]` table, and fail when it
is missing or empty.

**Why:** The gate has to tell an integration test from any other, and to
tell a session that selected the tier from one that narrowed it
(`GATE-5`). Every consumer today calls the marker `integration`, which is
exactly why it must be said rather than assumed: a default that matches all
of them today is one a fifth consumer inherits without noticing.
**Verified:** a table without `marker`, or with an empty one, makes the
command and the plugin fail with a message naming the key.

**Traceability:** pending — the package does not exist yet.

### GATE-3 — The fingerprint covers the content, not a commit

THE Deploy Gate SHALL fingerprint the deployment code as a SHA-256 over the
path and the content of every file under the `code` paths that git does not
ignore, tracked or not, in path order.

**Why:** A commit hash would let an uncommitted edit deploy on the strength
of a run that never saw it, and the edit made after the last run is the one
most likely to be untested. Untracked files count because a new task file
is part of the next deployment whether or not it is staged. Ignored files
do not, because they are caches and build output the deployment does not
read, and counting them would close the gate on every run of the tools that
write them. A file deleted from the working tree is not part of the code
any more, so it drops out of the fingerprint rather than breaking it.
**Verified:** after a recorded run, editing, adding or deleting a file under
a `code` path makes the check refuse; changing a file outside every `code`
path, or adding a file git ignores, does not.

**Traceability:** pending — the package does not exist yet.

### GATE-4 — Only a complete, clean run records it

WHEN a pytest session that selected the whole integration tier ends with
every integration test passed and none skipped or failed, THE Deploy Gate
SHALL write the fingerprint to `.integration-passed` at the repository root.

**Why:** A run that skipped a test proved nothing about what that test
covers, and the integration tier skips as a whole on a machine without
Incus (`INCUS-10`): a green session of skips would otherwise open the gate
on a laptop that never launched a machine. A failed test, or a session that
ended with any other failure, is not a pass of the tier. A session with no
integration test passed at all records nothing.
**Verified:** a session in which every integration test passed writes the
file; one with a skipped, failed or erroring integration test, one that
exits non-zero for another reason, and one that ran no integration test
leave it as it was.

**Traceability:** pending — the package does not exist yet.

### GATE-5 — A narrowed session is not the whole tier

THE Deploy Gate SHALL count a session as selecting the whole integration
tier only when it was given no paths, no `-k` expression, no `--deselect`,
`--ignore` or `--ignore-glob`, no `--lf` and no `--stepwise`, and its marker
expression is the configured marker or empty.

**Why:** Every one of these selects a part of the tier, and a part that
passes says nothing about the tests it left out. Re-running only the tests
that failed is the most natural thing to do after a fix, and it is exactly
the session that must not open the gate. An empty marker expression runs
every test, the tier included, so it counts.
**Verified:** a session given any one of the listed options, a path, or a
marker expression other than the configured marker or empty, records
nothing even when every test it ran passed.

**Traceability:** pending — the package does not exist yet.

### GATE-6 — The check refuses and names the reason

THE Deploy Gate SHALL provide a `deploy-gate` command that exits non-zero,
naming the reason, when `.integration-passed` is missing or holds a
fingerprint other than the deployment code's current one.

**Why:** The refusal has to come before anything connects to a host, so it
is a command the consumer's deploying target runs first, and a non-zero
exit stops `make`. The two reasons need different actions: no run on this
checkout at all, or a run on code that has since changed. Saying which one
tells the operator that the fix is the tier, not the gate.
**Verified:** the command exits zero when the file holds the current
fingerprint, and non-zero with one of two distinct messages when the file is
missing or holds another.

**Traceability:** pending — the package does not exist yet.

### GATE-7 — No override

THE Deploy Gate SHALL offer no option, environment variable or setting that
lets the check pass without a recorded run of the current deployment code.

**Why:** The change an operator most wants to push past the gate is an
urgent fix, and an urgent fix is exactly the change that most needs proving:
a fix that locks the host out cannot be fixed again. A run takes minutes. A
switch would be used precisely when it should not be. Anyone who means to
deploy unproved code can still delete the gate from the Makefile, write the
file by hand or run `ansible-playbook` directly; the gate is for the
operator who forgot, and none of those is forgetting.
**Verified:** the command's arguments and the package's configuration keys
include nothing that changes its verdict.

**Traceability:** pending — the package does not exist yet.

### GATE-8 — The consumer names the plugin

THE Deploy Gate SHALL take part in a pytest session only when the consumer
names its plugin, never through an entry point that installing the package
activates.

**Why:** A pytest entry point loads the plugin into every session of every
environment the package is installed in, this repository's own included,
whether that environment deploys anything or not. Naming it is the
consumer's opt-in, and it makes a missing `[tool.deploy-gate]` an error
(`GATE-1`) instead of something a plugin loaded by accident would have to
tolerate silently.
**Verified:** the package declares no `pytest11` entry point, and a session
that does not name the plugin neither reads `[tool.deploy-gate]` nor writes
the file.

**Traceability:** pending — the package does not exist yet.

### GATE-9 — Outside a git work tree the gate does not run

IF the repository is not a git work tree, or `git` cannot be run, THEN THE
Deploy Gate SHALL fail, in the command and in the plugin, without
fingerprinting anything.

**Why:** `GATE-3` lets git decide which files are code. Without git there is
no such answer, and fingerprinting every file under the `code` paths
instead would give a different fingerprint for the same code depending on
where it was computed, which either opens the gate wrongly or never opens
it.
**Verified:** in a directory that is not a git work tree, and with no `git`
on `PATH`, the command fails naming the cause, and a session that would
otherwise record fails instead.

**Traceability:** pending — the package does not exist yet.
