# Testing — Requirements

**Prefix:** `TEST`

## Purpose

Four repositories run this tooling as their gate and their integration
harness, so a defect here fails, or worse passes, four trees at once. The
tests in this repository are what a change has to get through before any
consumer moves its submodule to it. This spec states which tiers exist, how
they run, and what keeps the checker's own tests from being mistaken for
citations.

## Scope

### In scope

- The unit tier of each package and how it is run.
- How the checker's tests build the trees they check.
- Exercising the toolkit against a real Incus machine.

### Out of scope

- What any individual test asserts. Each requirement's `**Verified:**` line
  says what shows it; this spec states where those tests live and how they
  run.
- The consumers' own suites, which their own `testing` specs state.

## Security invariants

**Upholds:** INV-1. Unit tests launch no machine and write only inside
temporary directories; the integration tier launches machines only through
the toolkit, which bounds them (`INCUS`).
**Relies on:** none
**Allowances claimed:** none

## Requirements

### TEST-1 — A unit tier per package, with no Incus and no network

THE Test Suite SHALL keep each package's unit tests in `<package>/tests/`,
run them with `make test-unit`, and need neither Incus nor network access
for them.

**Why:** The unit tier is what runs on every change, on any machine and in
CI. A test that needs a daemon or the network turns a change to a regex
into a wait for infrastructure, and gets skipped.
**Verified:** `make test-unit` passes with the network disabled and no
Incus installed.

### TEST-2 — The checker is tested on trees it builds

THE Test Suite SHALL test the spec checker against spec trees each test
writes into a temporary directory, with requirement IDs whose prefixes are
not in this repository's registry.

**Why:** A test that ran the checker over this repository's tree would test
whatever state the tree is in, and fixtures written with this tree's own
prefixes would be read as citations by `make spec-check`. Each copy of the
checker used to exclude its own test module from the scan for that reason;
unregistered prefixes remove the need.
**Verified:** every test module under `spec-check/tests/` builds its tree
under `tmp_path`, and `make spec-check` here reports no citation from a
fixture.

### TEST-3 — The toolkit meets a real machine

WHERE Incus is available, THE Test Suite SHALL launch a machine with the
toolkit, reach it over SSH and through the Incus agent, run a playbook
against it and destroy it.

**Why:** The toolkit's unit tests check the commands it would run, with
`subprocess.run` replaced. Whether those commands work against a real
daemon has so far been shown only by the consumers' integration suites,
which fail for many reasons besides the toolkit. A test here shows it
directly, before a consumer moves to a new commit.
**Verified:** `make test-integration` on a host with Incus launches one
machine, runs each of the four operations and leaves no machine behind.

**Traceability:** pending — the tier does not exist yet; the toolkit is
exercised only through the consumers' integration suites.
