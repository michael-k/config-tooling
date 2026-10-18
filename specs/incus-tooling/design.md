# Incus tooling — Design

## Approach

The toolkit is a thin, synchronous wrapper around the `incus` command-line
client. Every operation is a `subprocess.run` of an `incus` or `ssh` or
`ansible-playbook` invocation whose output is parsed — `--format=json` where
Incus offers it, line-prefix matching where it does not (`vm.py`, because
`incus image info` refuses `--format=json` for a remote image). There is no
Incus SDK, no daemon socket, no async. The reason is that the CLI is Incus's
supported interface and the only one whose behaviour a developer can
reproduce by hand when a test fails, which for a test harness matters more
than either speed or type safety.

The package is seven modules under `incus/src/incus/`. `vm.py` is the
largest by a wide margin — it holds `IncusVM` and the base-image builder —
and `__main__.py`, the command line, is next; `ssh.py`, `constants.py`,
`ansible.py` and `fixtures.py` are small and single-purpose; `__init__.py`
re-exports two names. Nothing imports anything outside the standard library
except `pyyaml`, in `ansible.py`, and `pytest`, in `fixtures.py` — which is
why the package declares `pytest` as an optional `fixtures` extra
(`incus/pyproject.toml`) rather than a dependency: a consumer that wants
only `IncusVM` and `run_playbook` installs neither pytest nor anything
else. The package does not depend on Ansible either; `run_playbook` uses
whatever `ansible-playbook` the caller's environment provides (`INCUS-9`).

One shape runs through the whole package and is worth naming, because it is
what makes the toolkit usable for firewall and SSH tests: almost nothing
raises on a non-zero exit. `exec`, `ssh`, `get_ip`, `destroy` and
`run_playbook` all pass `check=False`; the first two and the last hand the
`CompletedProcess` back, so "the connection was refused" is a value a test
asserts on rather than an exception it has to catch, while `get_ip` turns a
failure into an empty string and `destroy` into a warning on stderr. The
exceptions are the operations where a failure could not be a test's
subject: `launch`, `put_file`, `get_file`, the base-image build and
`ssh-keygen` all use `check=True`, and four of the readiness poll's five
phases raise `TimeoutError` naming which one ran out.

Machines are named, not tracked. There is no registry, no lock file and no
state directory: a machine is identified by a name built from its caller's
prefix plus four random bytes, and the command line finds machines again by
asking Incus for every instance and filtering on the prefix it was given.
The prefix is therefore each consumer's namespace, and it is the caller's to
choose (`INCUS-1`): two consumers with distinct prefixes never see each
other's machines, and two that pass the same prefix share one namespace
again, which nothing in the package can detect.

## Implementation map

| Path | Realises |
|---|---|
| `incus/src/incus/vm.py` | INCUS-1, INCUS-2, INCUS-3, INCUS-4, INCUS-5, INCUS-6, INCUS-8, INCUS-12, INCUS-13, INCUS-14, INCUS-15, INCUS-18 |
| `incus/src/incus/ssh.py` | INCUS-1, INCUS-7, INCUS-8 |
| `incus/src/incus/constants.py` | INCUS-18 |
| `incus/src/incus/ansible.py` | INCUS-9, INCUS-17, INCUS-18 |
| `incus/src/incus/fixtures.py` | INCUS-1, INCUS-10, INCUS-18 |
| `incus/src/incus/__main__.py` | INCUS-1, INCUS-16, INCUS-18 |
| `incus/src/incus/__init__.py` | INCUS-2, INCUS-7, INCUS-12, INCUS-13, INCUS-14 |
| `incus/tests/test_incus_vm.py` | INCUS-1, INCUS-2, INCUS-3, INCUS-5, INCUS-8, INCUS-13, INCUS-14, INCUS-18 |
| `incus/tests/test_ssh_keypair.py` | INCUS-1, INCUS-7, INCUS-8 |
| `incus/tests/test_ansible_helpers.py` | INCUS-9, INCUS-17 |
| `incus/pyproject.toml` | INCUS-10 |

Each row lists exactly the `INCUS` IDs the file cites, as the spec README's
rules for the map require. The unit tests in `incus/tests/` cite the
requirements they test and so have rows like any other scanned file.
`incus/pyproject.toml` is not scanned, so its row is checked only for the
path's existence; it is listed because its `fixtures` extra is what makes
the fixture of `INCUS-10` installable. `incus/README.md` documents the
requirements to a consumer and, being Markdown, has no row. `INCUS-11` is
withdrawn and cited by nothing.

## Key decisions

**A `src/` layout with its own `pyproject.toml`, in a repository of its
own.** The `src/` directory means an `import incus` that resolves is
necessarily resolving the installed distribution rather than a directory that
happens to be next to the interpreter's working directory, so a broken
packaging change fails immediately instead of working locally and failing for
the first consumer. The separate `incus/pyproject.toml` means the package
declares its own dependencies — `pyyaml`, plus `pytest` behind a `fixtures`
extra — and nothing else, so it installs on its own (`PRJ-1`). Living in this
repository rather than inside one consumer is what lets it name no consumer
(`PRJ-3`): the package used to sit in one consumer and carried that
repository's machine prefix, image alias namespace and knock sequence into
the other three.

**Generic code in the package, each consumer's opinions in that consumer.**
The split is drawn at the point where a value stops being a fact about
virtual machines and starts being a fact about one playbook. `run_playbook`
takes a playbook path and a variable dictionary; the wrapper that knows
which playbook, which variables, and that a successful run has moved the
machine's SSH port is the consumer's. The same line runs through the
fixtures — `clean_vm` ships in the package because an unconfigured Debian
machine is no consumer's concept, while fixtures that run a consumer's
playbook stay in that consumer — and through the command line, which offers
machine management only (`INCUS-16`); building a consumer's images is that
consumer's own command (`INCUS-11`, withdrawn). `INCUS-1` carries the split
through to the data: the values that identify a project, which used to be
constants in the package, are now arguments its callers must pass.

**No default prefix, not even a neutral one.** A default such as
`incus-test-` would let a consumer that forgets the argument run, and every
consumer that forgets it would land in one shared namespace again, where
`destroy --all` reaches all of them. Requiring the prefix turns that
mistake into an error at the first call. The same reasoning removes the
knock fallback: a sequence the package supplies is a sequence every
consumer shares.

**Debian as stated scope, not a parameter (`INCUS-18`).** The guest-side
work `wait_ready()` does is a handful of Debian commands, and every image
the consumers launch is Debian. Making the package manager, the sshd
configuration path and the service name pluggable would add an interface
nobody calls; stating the assumption costs nothing and tells a consumer
before it launches the wrong image rather than after.

**A path dependency through a submodule, never published.** Consumers take
this repository as a submodule at `config-tooling/` and install the package
from `config-tooling/incus` as an editable `uv` path dependency (`PRJ-2`).
Nothing publishes it to an index. That is the right shape for what the
package is: it changes in step with the suites built on it, the submodule
commit pins the version a consumer tests with, and an editable path means a
fix made while debugging a consumer's test is the fix in this repository
too. A dated observation reinforces it: checked on 2026-09-21, the name
`incus` on PyPI belongs to an unrelated project, so `uv add incus` succeeds
and installs something else, failing later at import. The decision does not
rest on it.

**`incus exec` as the working path, SSH as the thing under test.** Both are
offered (`INCUS-3`), but they are not symmetric. The playbooks the
consumers test commonly narrow SSH, so a helper that depended on SSH to
look at the result would lose its own access at exactly the moment the
thing it is testing starts working — and would report the success as a
harness failure. `exec` goes through the Incus agent, not the network, so it
survives a default-drop ruleset, a knock gate and a `ListenAddress` bound to
another interface. `wait_ready()` uses a real SSH connection only to decide
the machine is up.

**Further machines go into the inventory and the run is limited, rather
than the playbook being changed (`INCUS-17`).** Each further machine is a
host entry under the caller's name, with `ansible_connection:
community.general.incus` and `ansible_host` set to the machine's Incus name,
which is the instance that connection plugin addresses. The run passes
`--limit` with the given machine's inventory name, `testvm`. A delegated
task still reaches an excluded host: in ansible-core 2.20.3,
`VariableManager.get_delegated_vars_and_hostname` (`vars/manager.py`)
resolves the delegated name with `InventoryManager.get_host`, which reads
`InventoryData.hosts` directly (`inventory/data.py`), while `--limit` is
applied only by `get_hosts` (`inventory/manager.py`). A two-host playbook
with local connections confirmed it. `community.general.incus` was added in
community.general 8.2.0, by the plugin's own documentation. The package
installs neither Ansible nor the collection; a consumer that passes further
machines supplies both.

## Failure modes

- **A shared prefix is a shared namespace.** `INCUS-1` makes the prefix the
  caller's, and nothing checks that two callers chose different ones. Two
  consumers passing the same prefix are back to one namespace, and either
  one's `destroy --all` deletes the other's machines.

- **`IncusVM.ssh()`'s option list exists twice.** `wait_ready()`'s fifth
  phase builds the same command inline in `vm.py` — the same five `-o`
  options, the same `-p`, the same `-i` — rather than calling `ssh()`. The
  two copies can diverge, a hardening option added to one or a timeout
  changed in the other, and no unit test would fail; in this repository
  both are exercised only with `subprocess.run` patched, or not at all.

- **Nothing exercises the command line at all.** `INCUS-16` records it: no
  module under `incus/tests/` imports `incus.__main__`. The dispatch table,
  the prefix selection of `INCUS-1` and `cmd_ssh`'s `os.execvp` fallback are
  covered by nothing in this repository.

- **A private key can outlive the machine it opens.** `INCUS-8` states the
  requirement and the gap: `IncusVM` is not a context manager, so the key is
  removed only when `destroy()` is called, and what calls `destroy()` on
  every path is the fixture contract rather than the class.

- **Nothing in this repository runs the toolkit against a machine.**
  `wait_ready()` (`INCUS-12`), `put_file` and `get_file` (`INCUS-4`,
  `INCUS-15`), `background_service` (`INCUS-6`) and `clean_vm` (`INCUS-10`)
  have no unit test, and the guest-side assumptions of `INCUS-18` meet a
  real guest only in consumers' suites. `TEST-3` is pending until a
  real-machine tier here supplies that evidence.

- **`get_file` is offered, documented and called by nothing.** `INCUS-15`
  is documented in `incus/README.md` and has no caller and no test. Its
  remote-path concatenation is also unvalidated in both directions: a
  destination that does not begin with `/` addresses a different instance
  rather than failing.

- **A non-Debian image fails late.** `INCUS-18` states the scope, but
  nothing checks an image the caller names: a non-Debian guest launches and
  then fails inside `wait_ready()` or at its first Ansible task. The
  `systemctl restart sshd` fallback `_setup_ssh` carries after `restart ssh`
  names a unit no guest `INCUS-18` admits has.

- **`vm.image` stops describing the image the machine was launched from.**
  `launch()` swaps an `images:debian/…` image for the cached base image in a
  local variable (`vm.py`) and never writes it back, so after a launch from
  the default image the attribute still reads `images:debian/13` while the
  instance was created from the prefixed base image.

- **`_get_ssh_public_key_file` is private in name only.** It is imported by
  consumers' helpers outside the package, so the underscore marks nothing
  and renaming it would break callers this repository cannot see.

## Interactions

- `TEST` — `TEST-1` is the tier this spec's unit evidence comes from:
  `incus/tests/`, with neither Incus nor the network. Within it,
  `test_ssh_keypair.py` really invokes `ssh-keygen`, while
  `test_incus_vm.py` and `test_ansible_helpers.py` patch `subprocess.run`
  out, so their evidence is about a constructed command line and not about
  anything that ran. `TEST-3` is the tier that will launch a machine with
  this package; until it is realised, the `**Verified:**` lines above that
  concern a running machine are readings. What `TEST` may not assume is that
  `IncusVM` cleans up after itself — `INCUS-8` says the fixtures are what
  guarantee that.

- `PRJ` — `PRJ-1` makes `incus/` a package installable on its own, and
  `PRJ-2` is how the four consumers take it in. `PRJ-3` forbids this
  repository to name anything of a consumer's; `INCUS-1` is the form that
  rule takes inside this package, for the values a consumer passes in.
  `PRJ-5`'s make targets run this package's unit tests here; the make
  targets through which a consumer drives the command line are the
  consumer's, and pass that consumer's prefix.

- Consumers — described, not named, since this tree keeps no list of them
  (`PRJ-3`). The image-publishing spec of the consumer that builds images
  owns the commands `INCUS-11` used to guard; they build on `IncusVM` and
  `run_playbook` and run in that repository. The same consumer's
  port-knocking spec describes the knock gate `INCUS-5`'s thresholds are
  chosen against; a consumer whose gate uses other timeouts cannot change
  them. Its integration tests own the control-server helper that used to
  ship in this package, and drive it through `IncusVM`.
