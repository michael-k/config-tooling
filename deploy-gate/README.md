# deploy-gate

Refuses a deployment unless a complete integration run passed on the
deployment code as it is in your checkout, uncommitted edits included. A
passing run of the whole integration tier records a fingerprint of that
code in `.integration-passed`; the `deploy-gate` command, run first by the
target that deploys, fails unless the code still has that fingerprint. The
rules are the `GATE` spec in this repository's `specs/deploy-gate/`; this
file is how to use it.

## Adopting it

1. Add this repository as a submodule at `config-tooling/`:

   ```sh
   git submodule add <url-of-config-tooling> config-tooling
   ```

2. Install the package from the submodule, in your `pyproject.toml`:

   ```toml
   [dependency-groups]
   dev = ["deploy-gate"]

   [tool.uv.sources]
   deploy-gate = { path = "config-tooling/deploy-gate", editable = true }
   ```

3. Say what your deployment code is and which marker selects your
   integration tier, also in `pyproject.toml`. There are no defaults:
   without the table, or with either key missing or empty, the command
   exits with 2 and a session that names the plugin fails (GATE-1, GATE-2).

   ```toml
   [tool.deploy-gate]
   code = ["site.yml", "ansible.cfg", "roles", "uv.lock", "Makefile"]
   marker = "integration"
   ```

   Paths are relative to the repository root, files or directories. Every
   file under them that git does not ignore counts, tracked or not; a change
   anywhere else, such as your inventory or vault, does not close the gate
   (GATE-3).

4. Name the plugin in your top-level `conftest.py`. Installing the package
   alone activates nothing (GATE-8).

   ```python
   pytest_plugins = ["deploy_gate.plugin"]
   ```

5. Ignore the record in `.gitignore`:

   ```gitignore
   .integration-passed
   ```

6. Run the check first in every target that deploys:

   ```make
   deploy:
   	uv run deploy-gate
   	uv run ansible-playbook …
   ```

## What counts as a passing run

A session records only when it selected the whole integration tier and every
integration test in it passed, with none skipped or failed (GATE-4). A
session given paths, `-k`, `--deselect`, `--ignore`, `--ignore-glob`,
`--lf`, `--stepwise` or `--sw-skip`, or a marker expression other than your
marker, records nothing (GATE-5). So does a tier that skipped because no
Incus answered. Neither the gate nor the plugin works outside a git work
tree or without `git` (GATE-9).

There is no switch to deploy without a run (GATE-7).

## Exit status

| Status | Meaning |
|---|---|
| `0` | A passing run is recorded for the deployment code as it is. |
| `1` | No run is recorded, or the code changed since; the message says which. |
| `2` | It could not run: a missing or malformed `[tool.deploy-gate]`, no git work tree or no `git`. |
