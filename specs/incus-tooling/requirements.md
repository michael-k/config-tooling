# Incus tooling — Requirements

**Prefix:** `INCUS`

## Purpose

Four repositories test their playbooks against virtual machines they
launch under Incus, and all four do it through one Python package,
`incus/`, which they take in through this repository's submodule
(`PRJ-2`). The package is what actually launches a machine, waits for it
to answer, runs a playbook at it, knocks on its firewall and deletes it
again. This spec covers that
package: what it promises a caller, and what it leaves the caller to
guarantee.

A package with four consumers has an interface contract, and the contract
matters more than an internal helper's would. A default inside it is
behaviour every consumer inherits without having chosen it, and a default
that identifies one project gives the other three that project's names. This
spec therefore requires the package to take every value that identifies a
project from its caller (`INCUS-1`), and states the one assumption it keeps
— that the guest is Debian — as scope rather than as a default
(`INCUS-18`).

The subject below is **THE Test Toolkit**: the installable `incus` package
under `incus/`, its command-line interface, and the pytest fixture it ships.
Nothing here is a requirement on a deployed host. A `**Verified:**` line in
this spec describes the package, and the reader should notice which kind of
evidence it rests on. The package's unit tests live in `incus/tests/` and
need neither Incus nor the network (`TEST-1`). Of the three modules there,
only `test_ssh_keypair.py` runs anything: it invokes `ssh-keygen` and
asserts on the files it writes. `test_incus_vm.py` and
`test_ansible_helpers.py` patch `subprocess.run` out and assert on the
command the package *would* have run, or call a builder directly and assert
on the YAML it returns. Nothing in this repository yet runs the toolkit
against a real machine; `TEST-3` is the requirement that will, and until it
does every statement here about a running machine is a reading of the
implementation, and says so.

How to install and use the package is `incus/README.md`'s subject, not this
spec's.

## Scope

### In scope

- That every value identifying the project that uses the toolkit — the
  prefix of its machines, temporary directories, key comments and cached
  base-image aliases, and its knock sequence — comes from that caller.
- That the toolkit launches Debian guests only, of the release its caller
  names.
- The lifecycle of one virtual machine: construction with a prefix, an
  optional name hint and an image, launch, readiness, and force-deletion.
- The two ways a caller reaches a machine — the machine's own SSH daemon, and
  `incus exec` through the Incus agent — and the difference between them.
- Pushing a file into a machine and pulling one out.
- Knocking automatically on a machine whose knock sequence is configured.
- Starting a service on a machine for the duration of a block and stopping it
  again.
- The throwaway SSH keypair each machine gets, and how long its private half
  lives on the controller.
- Running an arbitrary Ansible playbook against a machine, with the playbook,
  the variables and the paths all supplied by the caller, and with any
  further machines the caller names in the inventory but outside the run's
  targets.
- The availability check and the one pytest fixture the package ships.
- The command-line interface's machine-management commands.

### Out of scope

- The control-server helper of one consumer's network tests, which moves
  to that consumer's integration tests, its only user.
- Building and publishing prebuilt images, and cleaning them up — the
  business of the consumer that builds its images with its own command on
  top of the toolkit (`INCUS-11`, withdrawn).
- Guests other than Debian (`INCUS-18`).
- What any consumer's integration test asserts, which tier it belongs to and
  whether it runs — the consumer's own specs. This spec states what the
  package offers a fixture; a consumer's spec states what its suite built on
  it establishes.
- The make targets through which a consumer invokes the command line, and
  the prefix and knock sequence it passes — the consumer's. This
  repository's own make targets are `PRJ-5`'s.
- Behaviour changes beyond what the move into this repository requires.
  Only `INCUS-1`, `INCUS-11` and `INCUS-18` change the package's behaviour;
  the other recorded divergences — the key that can outlive its machine in
  `INCUS-8`, the untested command line in `INCUS-16` — stay as recorded.

## Security invariants

**Upholds:** INV-1, INV-2, INV-3
**Relies on:** none
**Allowances claimed:** none

`INV-1` holds because every machine the toolkit acts on is one it launched
or one its caller names, and the caller's prefix bounds the rest. A machine
is named by the caller's prefix plus random bytes (`INCUS-14`), and every
command-line operation that selects machines by itself — `list`,
`destroy --all`, and the saved-machine search behind `ssh` — selects on the
prefix its caller passes (`INCUS-1`), so one consumer's cleanup does not
reach another consumer's machines, or a developer's own instances, on the
same daemon. The files it writes are its own temporary directories, which
it creates with `tempfile.mkdtemp` and removes again (`INCUS-8`,
`INCUS-9`); the files it reads are the playbook, roles and working
directory its caller names.

`INV-2` holds for the one credential the toolkit creates. Each `IncusVM`
gets its own passphrase-less ed25519 keypair, generated into a
`tempfile.mkdtemp` directory of its own with the private key at mode `0600`
(`ssh.py`), injected into that one machine's `authorized_keys` (`vm.py`) and
removed when the machine is destroyed (`INCUS-8`). No key is written into a
repository and none is printed: the one place a key path reaches standard
output is `print_debug_info` (`fixtures.py`), which prints the path so a
developer can reach a preserved machine, never the key material. Two gaps
are the caller's to avoid and are recorded where they arise: a caller may
hand one keypair to several machines (`INCUS-7`), and a key outlives its
machine when nobody calls `destroy()` (`INCUS-8`).

`INV-3` holds for every value the toolkit passes to Ansible.
`run_playbook` writes its extra variables to a JSON file inside a
`tempfile.mkdtemp` directory and passes `-e @<file>` (`ansible.py`), so the
values — including the password hashes consumers' suites pass — never
appear in an `ansible-playbook` argument list that `ps` would show. The
directory is mode `0700` and is removed in a `finally` (`ansible.py`), so
the file inside it, which the process umask leaves group- and
world-readable, is unreachable for as long as it exists.

## Requirements

### INCUS-1 — Every value that identifies a project comes from its caller

THE Test Toolkit SHALL take every value that identifies the project using it
— the prefix of the names of the machines it launches, of its temporary
directories and key comments, and of its cached base-image aliases, and the
knock sequence — from its caller, with no default.

**Why:** machines are named, not tracked (`design.md`'s `## Approach`), so
the prefix is the only thing that tells one consumer's machines from
another's. A prefix fixed in the package gives every consumer the same
namespace, and `list` and `destroy --all` select on exactly that prefix — so
a `destroy --all` run in one repository force-deletes another repository's
running test machines on the same daemon. A default prefix, however
neutral, does the same for every consumer that forgets to pass one. A knock
sequence fixed in the package is worse in kind: a consumer's
port-knocking spec makes the sequence a per-deployment value because a
sequence that is the same everywhere is one an attacker reads once out of a
public repository, and a test helper that falls back to a fixed one teaches
a consumer to keep it.
**Verified:** the unit tests in `incus/tests/` show it for the classes:
constructing an `IncusVM` or calling `SSHKeyPair.create` without a prefix,
or with an empty one, fails; a generated machine name, the base-image build
machine's name and the cached base-image alias all begin with the caller's
prefix, and the alias with the caller's base-image prefix where one is
given; the keypair's temporary directory name and key comment carry it;
and `knock()` with neither `ports` nor a `knock_sequence` raises and opens
no connection. The command line's half is a reading, because nothing tests
the command line (`INCUS-16`).

The prefix reaches every site that names something. `IncusVM` takes it as a
required argument and builds generated names from it (`INCUS-14`), passes
it to `SSHKeyPair.create` for the temporary directory and the key comment,
and passes it to `ensure_base_image`, which names its build machine with
it. The cached image's alias begins with the prefix as well, unless the
caller names a base-image prefix of its own: a machine name and an image
alias live in different namespaces of the daemon, and a consumer that keeps
its images under one alias namespace, as the consumer that publishes
images keeps its published ones, can put the cache there too. An absent or empty prefix is an error rather than a
fallback: an empty prefix matches every instance on the daemon. No module
spells a prefix out, and `constants.py` holds none.

The command line takes the prefix as a required `--prefix` option on every
command, and a base-image prefix as an optional `--base-image-prefix`. `create` passes it to `IncusVM`; `list` and `destroy --all` select
only instances whose name starts with it; `destroy <name>` refuses a name
that does not; and `ssh <name>` looks for a saved machine only under the
prefix's temporary directories and refuses a name outside the prefix before
falling back to `incus exec`. The fixture the package ships, `clean_vm`,
takes the prefix from the consuming suite's pytest configuration, the
`incus_prefix` ini option, and a base-image prefix from
`incus_base_image_prefix` where one is set, and fails rather than skips
when no prefix is set, since a missing prefix is a mistake in
the suite, not an absent Incus (`INCUS-10`).

The cleanup hints the toolkit prints, from `create` and from
`print_debug_info`, name its own command line —
`python -m incus destroy --prefix <prefix> <name>` — never a make target,
which would be one consumer's name for it (`PRJ-3`).

The knock sequence has no fallback. `knock()` uses `ports` when given and
the machine's `knock_sequence` otherwise, and is an error when neither is
set; the automatic re-knock of `INCUS-5` runs only for a machine whose
`knock_sequence` is set.

### INCUS-2 — One object launches one machine

THE Test Toolkit SHALL give a caller a single object that launches one
virtual machine under Incus.

**Why:** a test that has to remember a name, a key path, an IP address and
the order in which Incus wants them told is a test that will leak a machine
the first time it raises. Folding all of that into one object is what makes
the teardown a single call, and makes the fixture that wraps it short enough
to read in one screen. `INCUS-12`, `INCUS-13` and `INCUS-14` are the rest of
what that object owes its caller; this requirement is the part that puts a
machine on the daemon in the first place.
**Verified:** `IncusVM` (`vm.py`) is a dataclass, and `launch()` (`vm.py`)
runs `incus launch <image> <name> --vm`, raising `ValueError` on an empty
image. The `auto_launch` `InitVar` calls it from `__post_init__` (`vm.py`),
so a caller may launch at construction or in two steps. The launch tests in
`incus/tests/test_incus_vm.py` cover it, with `subprocess.run` patched:
that the command carries `--vm`, that no cloud-init argument is passed, that
an empty image raises, that `auto_launch` launches, and that an upstream
Debian image is swapped for the cached base image while any other image is
launched as named (`INCUS-18`).

### INCUS-3 — Two ways in, and the difference is the point

THE Test Toolkit SHALL offer both a command path that goes through the
machine's own SSH daemon as the configured user on the configured port, and
one that bypasses SSH entirely and runs as root through the Incus agent.

**Why:** the two answer different questions. A playbook under test often
changes what the machine's SSH daemon will and will not accept, so a test
of that has to be a real SSH connection made the way a real client makes
it. But the same test needs a way to look inside the machine before sshd is
configured, after a playbook has locked it down, or as a user sshd would
refuse — and a path that depends on the thing under test cannot do that.
`incus exec` goes through the Incus agent rather than the network, so it
keeps working when SSH deliberately does not.
**Verified:** `ssh()` (`vm.py`) runs the `ssh` binary with
`-p self.ssh_port`, `-i self.private_key_path` and
`f"{self.ssh_user}@{self.ip_address}"`, forcing `PubkeyAuthentication=yes`,
`BatchMode=yes`, `StrictHostKeyChecking=no`, `UserKnownHostsFile=/dev/null`
and `ConnectTimeout=SSH_CONNECT_TIMEOUT_SECONDS`. `exec()` (`vm.py`) runs
`incus exec <name> -- sh -c <cmd>`, which reaches the machine as root
through the agent and passes the command to a shell so pipes and redirection
work. Both return `subprocess.CompletedProcess` and both use `check=False`,
so a non-zero exit is a value the caller asserts on rather than an
exception. `TestIncusVMSSH` and `TestIncusVMExec` in
`incus/tests/test_incus_vm.py` pin the two command lines, with
`subprocess.run` patched.

**The package holds two copies of the SSH command.** A real `ssh` process
runs during `wait_ready()`'s fifth phase, and it honours `ssh_user` and
`ssh_port` exactly as `ssh()` would — but it builds the command inline in
`vm.py` instead of calling `ssh()`. The two copies can drift without any
test noticing, and in this repository neither has run against a machine.

### INCUS-4 — A local file is pushed into a machine

THE Test Toolkit SHALL let a caller push a local file into a machine.

**Why:** some things cannot be arranged from a command's output. A binary a
test needs inside the machine has to be put there, and writing it through a
here-document over a connection mangles anything that is not text. The
transfer goes through Incus rather than `scp`, so it works on a machine whose
SSH is shut.
**Verified:** `put_file` (`vm.py`) runs `incus file push <src>
<name><dst>` with `check=True`, so a failed transfer raises
`CalledProcessError` rather than returning a result. It has no unit test.

It builds the remote side by plain concatenation, `f"{self.name}{dst}"`,
which produces Incus's `<instance>/<path>` form only when `dst` is
absolute. A relative `dst` — `"etc/hosts"` rather than `"/etc/hosts"` —
yields `myvmetc/hosts`, which addresses an instance named `myvmetc` instead
of failing. Nothing validates the argument and no docstring mentions the
requirement. `INCUS-15`'s `get_file` has the same shape and the same gap.

### INCUS-5 — A knock-gated machine is knocked before SSH is tried

WHERE a knock sequence is configured on a machine, THE Test Toolkit SHALL
perform the knock before an SSH attempt whose last knock is older than the
window that knock buys.

**Why:** a knock-gated machine refuses the connection rather than delaying
it, so a helper that does not knock produces a failure indistinguishable from
the one a genuinely closed port produces — and a poll loop that knocks once
and then keeps trying will start failing part way through for no reason a
reader of the output could guess. Re-knocking on a threshold rather than
before every attempt keeps the packet count down while staying inside the
window.
**Verified:** both SSH paths carry the same guard. `ssh()` re-knocks when
`time.monotonic() - self._last_knock_time > 20` (`vm.py`), and
`wait_ready()`'s fifth phase applies the identical test on every iteration of
its poll loop (`vm.py`). `knock()` (`vm.py`) opens a TCP connection to each
port in order with a 0.3-second default delay, suppressing
`ConnectionRefusedError`, `TimeoutError` and `OSError` so a closed port
counts as a knock, and records `_last_knock_time` at the end. Three tests in
`TestIncusVMSSH` pin the guard: it knocks when a sequence is set and the
last knock is stale, does not when the last knock was just recorded, and
does not when no sequence is configured. In this repository only those unit
tests reach it.

The thresholds are chosen against a knock gate whose partial sequences
expire after a five-second stage timeout and whose passed entries expire
after a thirty-second pass timeout. The 20-second re-knock threshold
leaves ten seconds of margin inside the thirty, and the 0.3-second
inter-knock delay stays well inside the five. The gate accepts a sequence
only in order, which is why the loop preserves it. A consumer whose gate uses
other timeouts has no way to change either value; both are fixed in
`vm.py`.

### INCUS-6 — A background service started for a test is stopped when the test leaves

WHERE a caller starts a service on a machine for the duration of a block, THE
Test Toolkit SHALL run the stop command when the block ends, including when
it ends in an exception.

**Why:** integration machines are commonly session-scoped, so a service left
running by a failed test is still running for every test after it. That
turns one failure into a run whose later failures describe the leftover
rather than the cause — and the tests that use this are typically firewall
tests, where a stray listener is exactly the sort of thing that makes a
later assertion lie.
**Verified:** `background_service` (`vm.py`) is a
`@contextlib.contextmanager`: it runs `start_cmd` through `exec`, sleeps
`settle` seconds (default 1) to let the service come up, and wraps the
`yield` in `try: … finally: self.exec(stop_cmd)`. The `finally` is what makes
the stop unconditional against an exception raised in the body. It has no
unit test; the evidence is the definition. The stop's own outcome is
discarded — `exec` runs with `check=False` and the `CompletedProcess` is
dropped — so a stop command that fails leaves the service running and
reports nothing.

### INCUS-7 — Each machine gets its own throwaway keypair

THE Test Toolkit SHALL generate a fresh passphrase-less ed25519 keypair for
each machine whose caller supplies none, in a directory of its own, with the
private key readable only by its owner.

**Why:** a key shared between machines makes one leaked test key a way into
every machine a run created, and a key reused between runs is a key that ends
up committed the first time somebody moves it out of `/tmp`. Generating one
per machine makes the key as disposable as the machine. Ed25519 and no
passphrase are the two choices that let `ssh` and `ansible-playbook` use it
unattended while matching the algorithm hardened SSH configurations expect.
**Verified:** `SSHKeyPair.create` (`ssh.py`) makes a directory with
`tempfile.mkdtemp`, which creates it at mode `0700`, runs
`ssh-keygen -t ed25519 -f <dir>/id_ed25519 -N "" -C <comment>` with
`check=True`, then `chmod`s the private key to `0600` and reads the public
half off disk. `cleanup()` (`ssh.py`) removes the whole directory when it
still exists, so calling it twice is harmless. The tests in
`incus/tests/test_ssh_keypair.py` assert the private key exists, that its
mode is exactly `0o600`, that the public key is a non-empty string
containing `ssh-ed25519`, that two keypairs land in different directories,
that cleanup removes both the key and the directory, and that a second
cleanup does not raise. They run `ssh-keygen` on the controller, which
`TEST-1` admits: it needs neither Incus nor the network.

The "whose caller supplies none" qualifier is not decoration. `IncusVM`'s
`ssh_key` `InitVar` (`vm.py`) is used verbatim when it is not `None`, so a
caller may hand the same `SSHKeyPair` to several machines, and the
per-machine guarantee then holds for none of them. Nothing in this
repository does it outside the unit tests, which pass a `MagicMock`;
nothing forbids it either, and a caller who does it also makes `INCUS-8`'s
cleanup destructive — the first `destroy()` removes the directory the other
machines are still reading their key from.

### INCUS-8 — A throwaway key does not outlive the machine it was made for

THE Test Toolkit SHALL remove a machine's private key from the controller's
disk by the time the run that created the machine ends.

**Why:** the key is a working credential for a machine on the developer's own
Incus daemon, and it sits in a predictable directory under `/tmp` that any
process running as that user can read. One run leaving one key behind is
minor; a helper that leaks one per failed test accumulates them for as long
as the developer's `/tmp` survives, and a key the `create` command made sits
next to a `vm-info.json` naming the address it opens. The machine itself is
the obvious thing to clean up, and it is the key that gets forgotten.
**Verified:** `destroy()` calls `self._ssh_key.cleanup()` (`vm.py`) after
deleting the machine, and `cleanup()` removes the whole temporary directory
(`ssh.py`) — the private key, the public key, and the `vm-info.json` the
command line writes beside them (`__main__.py`). The unit tests pin the
removal itself: `test_cleanup_removes_private_key` and
`test_cleanup_removes_temp_directory` in `incus/tests/test_ssh_keypair.py`,
plus `TestIncusVMDestroy::test_destroy_calls_incus_delete_force` in
`incus/tests/test_incus_vm.py`, which asserts `cleanup` was called once.

**The class does not guarantee this; the fixtures do.** `IncusVM` is not a
context manager — it defines `__post_init__` and no other dunder method, so
there is no `__enter__`, no `__exit__` and no `__del__` — and nothing else in
the module removes the key. It goes when somebody calls `destroy()`. The
fixture this package ships, `clean_vm` (`fixtures.py`), wraps setup in
`try/except` and destroys on the exception path, then destroys again in
teardown; a consumer's own fixtures have to do the same, and nothing in the
package makes them. A caller that builds an `IncusVM` directly and raises
before `destroy()` leaves an ed25519 private key at mode `0600` in a
`/tmp/<prefix>…` directory that nothing later removes. The requirement is
also violated on purpose, by `KEEP_VM_ON_FAIL`, and the two paths that
honour it do not test the same thing. On the setup-failure path the
environment variable alone decides (`fixtures.py`): set it, and a fixture
that fails in `wait_ready()` prints connection details and does not
destroy, whatever the session's failure count is. In teardown the fixture
goes through `_should_keep` (`fixtures.py`), which additionally requires the
session to be carrying a failure or an error. Either way the key is kept
deliberately, because it is what makes the preserved machine reachable.

### INCUS-9 — The playbook runner takes its subject from the caller

THE Test Toolkit SHALL take the playbook, the variables, the working
directory and the roles path of a run entirely from its caller, pass the
caller's variables through unchanged, and change no state on the object it
was given.

**Why:** this is the function that decides whether the package serves four
repositories or one. A runner that merged one playbook's variables, or that
reached for a workspace root, or that quietly rewrote the machine's SSH port
on success, would be usable by exactly the repository whose habits it
encoded. Keeping the defaults in the caller is what lets each consumer's own
helpers hold that consumer's opinions.
**Verified:** `run_playbook` (`ansible.py`) takes the playbook path, the
variables, the working directory and the roles path as arguments and
declares no variable dictionary of its own — the module contains no
constant at all. Its inventory's host `testvm` names `vm.ip_address`,
`vm.ssh_port` and `vm.private_key_path` (`ansible.py`). It writes
`extra_vars` to JSON verbatim — `json.dumps(extra_vars)`, no merge — and
passes `-e @<file>`, generates a temporary single-role playbook when
`roles` is given, sets `ANSIBLE_ROLES_PATH` only when both `roles` and
`roles_path` are supplied, and removes its temporary directory in a
`finally`. It invokes `ansible-playbook` directly rather than `uv run
ansible-playbook`, so the binary comes from whatever environment the caller
is already in. `check=False` leaves the return code to the caller.
`TestRunPlaybook` in `incus/tests/test_ansible_helpers.py` covers it, with
`subprocess.run` patched, including `test_does_not_mutate_vm_ssh_port`,
which pins the no-mutation half.

The inventory is not empty of opinions, and the requirement is worded to say
what it does rather than to claim otherwise. `build_inventory`
(`ansible.py`) writes six host variables for `testvm`. Four come from the
caller or from the machine — `ansible_host`, `ansible_port` and
`ansible_ssh_private_key_file` off the `IncusVM`, and `ansible_user` from
the `user` parameter, which the caller may set and which defaults to
`"root"`. The remaining two are literals the caller cannot reach:
`ansible_python_interpreter: /usr/bin/python3`, which is `INCUS-18`'s, and
`ansible_ssh_common_args` forcing `PubkeyAuthentication=yes`,
`IdentitiesOnly=yes`, `StrictHostKeyChecking=no` and
`UserKnownHostsFile=/dev/null`, which are properties of reaching a
throwaway machine with a throwaway key. None of them is a playbook variable
the caller supplied, and none is merged into `extra_vars`.

`_get_ssh_public_key_file` (`ansible.py`) carries a leading underscore and
is imported by consumers' helpers outside the package, so the line between
the package's private and public surface is drawn in a name and
contradicted in fact.

### INCUS-10 — Incus's absence is a skip, not an error

THE Test Toolkit SHALL expose one check for whether Incus can be used, and
apply it to the fixture it ships, so that an absent Incus skips a test rather
than failing it.

**Why:** a consumer's suite has to run, and pass, on a machine without
Incus, and the check has to be one function living where every consumer can
reach it. Two copies of "is Incus available" drift, and a consumer that
writes its own gets a different answer from the fixture it is using in the
same session.
**Verified:** `incus_available()` (`fixtures.py`) is `shutil.which("incus")`
followed by the return code of `incus list --format=json`, defined once in
the package and exported for consumers. `clean_vm` (`fixtures.py`) calls it
and `pytest.skip("Incus not available")` before launching anything.
`clean_vm` reads its Debian release through
`request.config.getoption(name, default)`, which returns the supplied
default when the option was never declared, so the fixture works in a
consumer that never registers `--debian-version`; the option, where it
exists, is declared by the consumer, not by the package. The prefix is not
defaulted that way (`INCUS-1`). No test in this repository uses `clean_vm`,
so its evidence is the definition until `TEST-3` runs it.

### INCUS-11 — The image-publishing commands appear only where images are built (withdrawn)

Withdrawn with the move into this repository. Building prebuilt images —
the `publish` and `images-clean` commands — leaves the package for the
consumer that builds them with its own command on top of the toolkit. The guard that registered those commands only where a
`site.yml` was present goes with them; the command line now offers the same
commands everywhere (`INCUS-16`).

### INCUS-12 — A launched machine is brought to the point where it accepts SSH

THE Test Toolkit SHALL bring a launched machine to the point where it accepts
an SSH connection on the configured port as the configured user.

**Why:** Incus reports a machine as `Running` long before anything inside it
will answer, and the Debian images this toolkit launches have no cloud-init,
so nothing puts a key on the machine on the caller's behalf. Without a single
call that closes that gap, every consumer writes its own poll loop, and the
ones that get it wrong fail intermittently in a way that reads as a broken
test rather than a machine that was not ready. Split out of `INCUS-2`: a
machine that launched and never became reachable has satisfied `INCUS-2` and
is useless.
**Verified:** `wait_ready()` (`vm.py`) runs five phases against one shared
deadline of `VM_READY_TIMEOUT_SECONDS` = 120 seconds: the machine reaching
`Running`, the Incus agent answering `incus exec`, a global IPv4 address
appearing, `_setup_ssh()` installing openssh-server and appending the
ephemeral public key to the SSH user's `authorized_keys`, and an `ssh … echo
ready` poll. The four that poll each raise a `TimeoutError` naming which one
ran out; `_setup_ssh()` is straight-line work with no deadline of its own, so
a hang inside it is bounded only by the individual `exec` timeouts it passes.
**`wait_ready()` has no unit test at all**; the evidence above is a reading
of the implementation, not a run, and `TEST-3` is what will supply one.

### INCUS-13 — A machine is force-deleted on request

THE Test Toolkit SHALL force-delete a machine when its caller asks, whatever
state the machine is in.

**Why:** a test machine that cannot be removed because it is running, or
because a previous run left it half-configured, is a machine somebody has to
clean up by hand — and `INCUS-8`'s key removal hangs off this call, so a
delete that refused would leave the credential behind as well. Forcing it is
right here precisely because nothing on these machines is worth preserving.
Split out of `INCUS-2`.
**Verified:** `destroy()` (`vm.py`) runs `incus delete <name> --force`,
prints a warning to stderr rather than raising when that fails, and calls
`self._ssh_key.cleanup()`. `TestIncusVMDestroy` in
`incus/tests/test_incus_vm.py` asserts the exact argument list and that
`cleanup` was called once. What nothing here guarantees is that `destroy()`
is ever called — that is `INCUS-8`'s finding, and it applies to the machine
as much as to the key.

### INCUS-14 — A machine's name and access key are generated when the caller supplies neither

THE Test Toolkit SHALL generate a machine's name and its access key when its
caller supplies neither.

**Why:** a fixed name means two runs on one developer's machine collide, and
a session-scoped fixture cannot be run twice; a caller forced to invent one
per machine will reach for something stable and hit exactly that. The key is
the same argument in a sharper form — `INCUS-7` wants one per machine, and
that only happens by default if the default is to make one. Split out of
`INCUS-2`.
**Verified:** `__post_init__` (`vm.py`) builds the caller's prefix + an
optional `name_hint` + `secrets.token_hex(4)` when `name` is empty, and
creates an `SSHKeyPair` when `ssh_key` is `None`. `ssh_key`, `name_hint` and
`auto_launch` are `InitVar`s, so none of them survives on the instance.
`TestIncusVMName` in `incus/tests/test_incus_vm.py` covers the name: that
it begins with the caller's prefix and carries a non-empty suffix, and that
a `name_hint` appears in it. `INCUS-1` states where the prefix comes from,
and `INCUS-7` what the generated key is.

### INCUS-15 — A file is pulled out of a machine

THE Test Toolkit SHALL let a caller pull a file out of a machine to a local
path.

**Why:** a log, a rendered configuration file or a captured ruleset is far
easier to assert against as a local file than through `cat` over a
connection, and reading it through Incus rather than `scp` works on a machine
whose SSH is shut. Split out of `INCUS-4`.
**Verified:** `get_file` (`vm.py`) runs `incus file pull <name><src> <dst>`
with `check=True`, so a failed transfer raises `CalledProcessError` rather
than returning a result. It has no unit test, and measured on 2026-10-18 no
test in this repository or in any of the four consumers calls it. The pull
direction is offered, documented in `incus/README.md` and unexercised, and
its remote path is concatenated without validation exactly as `INCUS-4`
records for the push direction.

### INCUS-16 — The machine-management commands are available everywhere

THE Test Toolkit's command line SHALL register its machine-management
commands wherever it is run.

**Why:** these four are the reason a consumer has a command line at all — a
machine left behind by an interrupted run has to be findable and removable
from whatever directory the developer happens to be in, and a cleanup command
that is itself conditional is a cleanup command that is missing on the day it
is needed.
**Verified:** `main()` (`__main__.py`) registers `create`, `list`,
`destroy` and `ssh` — subparsers and dispatch entries alike — outside every
conditional, and registers no other command. Each takes the required
`--prefix` of `INCUS-1`.

**Nothing tests the command line.** No module under `incus/tests/` imports
`incus.__main__` or any `cmd_*` function, so these four commands, their
prefix selection and the dispatch table are exercised only by consumers'
make targets, by hand.

### INCUS-17 — Further machines join the inventory over Incus, and the run is limited to its subject

THE Test Toolkit's playbook runner SHALL add each further machine its
caller names to the run's inventory, under the name the caller gives it and
reached through the Incus connection rather than SSH, and limit the run to
the machine the runner was given.

**Why:** a playbook can need a second machine without that machine being
its subject. A role that joins a machine to a network, for one, can make
its login from a host a variable names, and in one consumer's suite that
host is a peer machine, because the suite's controller is not on the test
network. Ansible reaches a delegated host by that host's own connection
variables, so the peer has to be in the inventory. The Incus connection
reaches it through the Incus agent, as `INCUS-3`'s `exec()` does, so it
needs neither the peer's sshd nor a key for it; anything the playbook needs
on the peer is the caller's to place there, with `put_file` (`INCUS-4`).
The limit is the other half: a playbook whose plays run on `hosts: all`,
and the single-role playbook `build_single_role_playbook` writes, would
otherwise run against the peer too. Limiting the run rather than changing
the playbook's host patterns keeps the playbook the caller's, as `INCUS-9`
requires. The runner knows nothing of which variable names the further
machine: that is the caller's business, and `INCUS-1` keeps it out of the
package.
**Verified:** `build_inventory` (`ansible.py`) adds each entry of
`further_machines` as a host under its key, with exactly
`ansible_connection: community.general.incus` and `ansible_host` set to the
machine's `name`, and `run_playbook` passes it on and always passes
`--limit testvm`. In `incus/tests/test_ansible_helpers.py`,
`test_adds_further_machines_over_incus` asserts the further host's two
variables and that `testvm`'s are unchanged,
`test_holds_only_the_given_machine_by_default` that without further
machines the inventory holds `testvm` alone,
`test_limits_the_run_to_the_given_machine` the one `--limit testvm` on the
command line, and `test_passes_further_machines_to_the_inventory` the
inventory file the command names, read while `subprocess.run` is patched.
None of them runs `ansible-playbook` or reaches Incus. With ansible-core
2.20.3, a task delegated to an inventory host that `--limit` excluded ran on
that host, measured with two local-connection hosts and no Incus;
`design.md`'s `## Key decisions` gives the source read behind it.

### INCUS-18 — The guest is Debian

THE Test Toolkit SHALL launch Debian images only, of the release its caller
names, defaulting to Debian 13.

**Why:** the toolkit has to do things inside the guest before any playbook
runs — install an SSH server, put a key in place, restart the daemon — and
it does them with Debian's tools at Debian's paths. Stating that as the
toolkit's scope tells a consumer what it may launch; leaving it as a hidden
default let a consumer find out only when `wait_ready()` failed on a
machine that had launched cleanly. Making the guest's package manager, paths
and service names configurable would be a change no consumer needs.
**Verified:** the unit tests in `incus/tests/test_incus_vm.py` show the
release half: an `IncusVM` given no image launches from `images:debian/13`
swapped for the cached base image built for release 13, a caller-named
upstream release is passed through to `ensure_base_image`, and an image
that is not an upstream Debian image is launched as named. The guest-side
assumptions below are a reading, and run only where `TEST-3` does.

The release is the caller's: `IncusVM`'s default image is
`images:debian/` plus `DEFAULT_DEBIAN_VERSION` (`constants.py`), `clean_vm`
reads `--debian-version` (`fixtures.py`), and the command line's `create`
takes `--debian` (`__main__.py`). An image the caller names that is not an
upstream Debian image — a consumer's own prebuilt image, say — is launched
as named, and the toolkit takes it to be Debian.

The guest-side assumptions are these. The base-image build runs
`apt-get install openssh-server curl` and edits `PermitRootLogin` in
`/etc/ssh/sshd_config` in place (`vm.py`). `_setup_ssh` checks for
openssh-server with `dpkg -s` and installs it with `apt-get` when it is
missing, edits `/etc/ssh/sshd_config` the same way for an SSH user of
`root`, and restarts the `ssh` unit (`vm.py`). `build_inventory` writes
`ansible_python_interpreter: /usr/bin/python3` into every inventory it
generates (`ansible.py`). A non-Debian image therefore launches and then
fails in `wait_ready()`, or fails its first Ansible task.
