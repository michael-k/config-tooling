# Project — Design

## Approach

The repository is a `uv` workspace with three members, `incus/`,
`spec-check/` and `deploy-gate/`, each a package with its own `pyproject.toml`, `src/` layout
and `tests/`. The root `pyproject.toml` declares the workspace, the
development tools (ruff, ty, pytest) and this tree's own
`[tool.spec-check]` scan; it is not a package itself. The root `Makefile`
runs the tools over every member.

A consumer adds the repository as a submodule at `config-tooling/` and
points `[tool.uv.sources]` at the members it uses:

```toml
[tool.uv.sources]
incus = { path = "config-tooling/incus", editable = true }
spec-check = { path = "config-tooling/spec-check", editable = true }
deploy-gate = { path = "config-tooling/deploy-gate", editable = true }
```

Its `make spec-check` then runs `uv run spec-check`, which reads the
consumer's own `[tool.spec-check]` and spec tree. Updating the tooling is a
commit in the consumer that moves the submodule.

## Implementation map

| Path | Realises |
|---|---|
| `pyproject.toml` | PRJ-1, PRJ-4, PRJ-6 |
| `incus/pyproject.toml` | PRJ-1, PRJ-4 |
| `spec-check/pyproject.toml` | PRJ-1, PRJ-4 |
| `deploy-gate/pyproject.toml` | PRJ-1, PRJ-4 |
| `Makefile` | PRJ-4, PRJ-5, PRJ-6 |
| `tests/test_project.py` | PRJ-1, PRJ-2 |
| `incus/tests/test_incus_vm.py` | PRJ-3 |
| `incus/tests/test_ssh_keypair.py` | PRJ-3 |

## Key decisions

**A submodule, not a git dependency.** `uv` can install a package straight
from a subdirectory of a git URL, and that would cover all three packages. It
would not put anything else of the repository into a consumer's tree, and
the follow-ups planned for it are not packages: the shared parts of
`specs/README.md`, and a template for the configuration files the
repositories share. A submodule carries all of it at one pinned commit, and
a consumer's checkout is complete without network access once cloned.

**A separate repository, not a consumer.** The toolkit lived in one
consumer, and a submodule of that repository would have worked as well. It
would also have put a host-hardening playbook, its roles and its spec tree
into every other consumer, against that repository's own statement that
purpose repositories are not coupled to its code, and against the other
consumers' statements that they import nothing from it. That repository
becomes a consumer like the other three (`PRJ-3`).

**The remote is renamed after each clone.** A submodule's clone names its
remote `origin`. The repositories name remotes after their GitHub owner, so
the setup step after `git clone --recurse-submodules` is
`git -C config-tooling remote rename origin michael-k`. Nothing depends on
the name; it is a convention, and the step is in each consumer's README.

**A workspace, so the tree checks itself.** As a workspace member,
`spec-check` is installed into the repository's own environment from its
own source, so `make spec-check` here runs the checker as it is in the
working tree, with no submodule of itself (`PRJ-6`).

**No release process.** The commit is the version, and nothing promises
compatibility between two commits. A change that needs consumers to change
says so in its commit message, and each consumer moves its submodule when it
is ready. A consumer that has not moved keeps working on the commit it pins.

## Failure modes

- A consumer is cloned without `--recurse-submodules`: `config-tooling/` is
  empty, `uv sync` fails on a missing path dependency, and nothing runs.
  The fix is `git submodule update --init`. The failure is loud and early,
  which is the reason for the path dependency over an optional one.
- A consumer edits a file inside its `config-tooling/` checkout: the
  submodule shows as modified in the consumer, and the edit is lost on the
  next update unless it is committed in this repository. Changes belong
  here, then a submodule move in the consumer.
- Two consumers pin different commits: each runs the checker it pins, so
  the same tree can pass in one and fail in the other. That is the cost of
  pinning, and it lasts until both move.

## Interactions

- `SPEC`, `INCUS`, `GATE`: the three packages this spec lays out.
- `TEST`: the tests each package carries, run by the targets of `PRJ-5`.
- `INV-1`: a consumer's checkout of this repository is a directory of that
  consumer; the checker never reads inside it (`SPEC-14`).
