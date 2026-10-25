# Deploy Gate — Design

## Approach

The package is a third workspace member, `deploy-gate/`, with its own
`pyproject.toml`, `src/deploy_gate/` and `tests/`. It depends on nothing
outside the standard library except pytest, which only the plugin imports.

A consumer configures it in its own `pyproject.toml`:

```toml
[tool.deploy-gate]
code = ["site.yml", "ansible.cfg", "roles", "uv.lock", "Makefile"]
marker = "integration"
```

The `code` entries are paths relative to the repository root, files or
directories, and are handed to git as pathspecs. The fingerprint (`GATE-3`)
lists them with `git ls-files -z --cached --others --exclude-standard --`,
drops names that are no file in the working tree, sorts the rest, and feeds
each name, a NUL byte and the SHA-256 of its content into one SHA-256.

The repository root is the top level of the git work tree the command is
run in, or that holds the pytest session's root directory; `pyproject.toml`
and `.integration-passed` are read and written there. The consumer ignores
`.integration-passed` in its own `.gitignore`.

The plugin, `deploy_gate.plugin`, counts the reports of tests carrying the
configured marker: a `call` phase that passed counts as passed, and a skip
or failure in any phase counts against. At the end of the session it
records the fingerprint when the session exited zero, at least one
integration test passed, none counted against, and the session selected the
whole tier (`GATE-4`, `GATE-5`). A consumer names the plugin in its
top-level `conftest.py`:

```python
pytest_plugins = ["deploy_gate.plugin"]
```

The `deploy-gate` command computes the fingerprint again and compares it
with the file's (`GATE-6`). The consumer's deploying make target runs it
first:

```make
deploy: …
	uv run deploy-gate
	uv run ansible-playbook …
```

## Implementation map

| Path | Realises |
|---|---|
| `deploy-gate/pyproject.toml` | GATE-8 |
| `deploy-gate/src/deploy_gate/config.py` | GATE-1, GATE-2 |
| `deploy-gate/src/deploy_gate/gate.py` | GATE-3, GATE-6, GATE-9 |
| `deploy-gate/src/deploy_gate/cli.py` | GATE-6, GATE-7, GATE-9 |
| `deploy-gate/src/deploy_gate/plugin.py` | GATE-1, GATE-2, GATE-4, GATE-5, GATE-9 |
| `deploy-gate/tests/test_config.py` | GATE-1, GATE-2 |
| `deploy-gate/tests/test_gate.py` | GATE-1, GATE-3, GATE-6, GATE-7, GATE-9 |
| `deploy-gate/tests/test_plugin.py` | GATE-1, GATE-4, GATE-5, GATE-8, GATE-9 |

## Key decisions

**Lifted from a consumer, minus the consumer.** The gate is the one a
consumer already ran. Its list of code paths and its marker were constants
in its module; they are now the consumer's configuration (`GATE-1`,
`GATE-2`), read the way the spec checker reads its scan (`SPEC-15`). The
fingerprint, the file name, the rule for a complete run and the absence of
an override are unchanged, so the consumer moves to the package without its
gate opening or closing differently.

**The consumer names the plugin; installing it does not activate it.** A
`pytest11` entry point would load the plugin into every session of every
environment the package is installed in, including this repository's own
suite, which deploys nothing. The plugin would then have to treat a missing
`[tool.deploy-gate]` as "not meant for me" and do nothing, and a consumer
that forgot its table would get a gate that never records and no message
saying why. Named in `pytest_plugins`, the plugin is present only where a
consumer asked for it, and there a missing table is an error (`GATE-8`).
This matches how a consumer takes the toolkit's `clean_vm` fixture: by
importing it in its own `conftest.py`.

**Both keys are required.** `marker` has the same value in every consumer
today. A default would still be a value this package chose for them, and
`PRJ-3` leaves such values to the consumer.

**The file name is fixed.** `.integration-passed` names what the file
records and nothing about any consumer; making it configurable would only
let the command and the plugin disagree about where to look.

**No override.** The reasoning is `GATE-7`'s. The gate is local, because
there is no CI that runs the integration tier: the only place a passing run
can be recorded is the controller that ran it, and the only place it can be
checked is the target the operator deploys with.

## Failure modes

- The file records one fingerprint. A run on one controller proves nothing
  for another's checkout, which needs its own run.
- A change outside the configured `code` paths, such as an inventory, a
  vault or a base image, does not close the gate. A consumer that leaves a
  directory out of `code` has a gate that misses changes there, and nothing
  here can tell.
- A test the consumer forgot to mark with the configured marker is not
  counted, so a skip or failure in it does not stop a record, as long as
  the session as a whole still exits zero.
- A hook in the consumer's suite that hides a test's failure from the
  reports hides it from the gate too.
- Anyone can write the file by hand, delete the check from the Makefile or
  run the playbook directly (`GATE-7`).

## Interactions

- `PRJ-1`, `PRJ-3`: the gate is a package of its own and takes everything
  consumer-specific from its consumer.
- `INCUS-10`: the integration tier skips as a whole without Incus, which is
  why a skip keeps the gate closed (`GATE-4`).
- `INV-1`: the gate writes one file, in the repository it runs in.
- Each consumer's own testing spec states which of its targets run the
  check, and lists its deployment code in `[tool.deploy-gate]`.
