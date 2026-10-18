# incus — VM lifecycle management for integration testing

Launch, configure and test against Incus virtual machines from Python: one
object per machine, a playbook runner, a pytest fixture and a small command
line for finding and removing machines a run left behind.

This package's requirements are `specs/incus-tooling/` in this repository.
Where this file and that spec disagree, the spec is authoritative and the
disagreement is a bug.

## Installation

Take this repository in as a submodule at `config-tooling/`:

```bash
git submodule add <config-tooling repository URL> config-tooling
```

and install the package from it as an editable path dependency, with the
`fixtures` extra if your suite uses `clean_vm` or `incus_available`:

```toml
[dependency-groups]
dev = ["incus[fixtures]"]

[tool.uv.sources]
incus = { path = "config-tooling/incus", editable = true }
```

The submodule commit pins the version you test with; a fix made while
debugging your suite is made in this repository too.

The package is **not published to any index**, so there is no `uv add incus`
that resolves to it. As of 2026-09-21 the name `incus` on PyPI belongs to an
unrelated project, so that command succeeds, installs something else and
fails later at import.

The package installs neither Ansible nor any collection. `run_playbook` uses
whatever `ansible-playbook` your environment provides, and further machines
(below) need `community.general` 8.2.0 or later.

## Your prefix

Every value that identifies your project comes from you, and none has a
default (INCUS-1). The one you always pass is the **prefix**: a non-empty
string such as `myproject-test-` that begins the name of every machine you
launch, the directory its throwaway key lives in, the key's comment, the
machine that builds the cached base image and, unless you name another, the
cached base image's alias.

Choose one no other repository on the same Incus daemon uses. The command
line's `list` and `destroy --all` select every instance whose name starts
with the prefix you pass, so two repositories sharing a prefix share one
namespace, and either one's `destroy --all` deletes the other's machines.
Nothing in the package can detect that.

An absent or empty prefix is an error, never a fallback: an empty prefix
would match every instance on the daemon.

## Quick start

```python
from incus import IncusVM

vm = IncusVM(prefix="myproject-test-", auto_launch=True)
try:
    vm.wait_ready()
    result = vm.ssh("systemctl is-active ssh")
    assert result.returncode == 0
finally:
    vm.destroy()
```

## Guests are Debian

The toolkit launches Debian guests, of the release you name, Debian 13 by
default (INCUS-18). Before any playbook runs, `wait_ready()` installs an SSH
server with `apt-get`, edits `/etc/ssh/sshd_config` and restarts the `ssh`
unit, and every generated inventory sets `ansible_python_interpreter` to
`/usr/bin/python3`. An image that is not Debian launches and then fails in
`wait_ready()` or at its first Ansible task.

An upstream image, `images:debian/<release>`, is swapped at launch for a
cached base image of that release with openssh-server, curl and
`PermitRootLogin yes` already in place, which saves an `apt-get install` on
every boot. The cache is rebuilt when the upstream image's fingerprint
changes. Any other image you name — your own prebuilt image, say — is
launched as named and taken to be Debian.

The cache is stored under `<prefix>base-<release>`. To keep it in an alias
namespace of your own instead, pass `base_image_prefix`:

```python
vm = IncusVM(prefix="myproject-test-", base_image_prefix="myproject/cache-base-")
# the cached image is myproject/cache-base-13
```

## IncusVM

One object per machine: it generates the name and the SSH keypair
(INCUS-14), launches (INCUS-2), waits for SSH (INCUS-12) and force-deletes
(INCUS-13). All arguments are keyword-only.

```python
# Minimal: Debian 13, generated name and keypair
vm = IncusVM(prefix="myproject-test-", auto_launch=True)

# Another release, a name hint, a non-root user on another port
vm = IncusVM(
    prefix="myproject-test-",
    image="images:debian/12",
    name_hint="webserver",
    ssh_port=2222,
    ssh_user="deploy",
    auto_launch=True,
)

# Two-step: construct first, launch later
vm = IncusVM(prefix="myproject-test-")
vm.launch()
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prefix` | `str` | required | Your prefix; must not be empty |
| `image` | `str` | `"images:debian/13"` | Incus image to launch |
| `name` | `str` | generated | `<prefix>[<name_hint>-]<random>` when empty |
| `ssh_key` | `SSHKeyPair \| None` | generated | Throwaway SSH keypair |
| `ip_address` | `str` | `""` | Set by `wait_ready()` |
| `ssh_port` | `int` | `22` | SSH port used by `ssh()` |
| `ssh_user` | `str` | `"root"` | User for `ssh()` connections; `wait_ready()` installs the key for it |
| `knock_sequence` | `list[int] \| None` | `None` | Your knock sequence; enables auto-knock |
| `base_image_prefix` | `str \| None` | `None` | Alias prefix of the cached base image |
| `name_hint` | `str` | `""` | Inserted into the generated name |
| `auto_launch` | `bool` | `False` | Call `launch()` after construction |

### Lifecycle

```python
vm.launch()       # Launch the VM in Incus
vm.wait_ready()   # Wait for boot + SSH ready (installs sshd, injects key)
vm.destroy()      # Force-delete VM and clean up keypair
```

`IncusVM` is **not** a context manager and has no finaliser, so `destroy()`
is the only thing that removes the throwaway private key from your disk
(INCUS-8). Call it on the failure path too: wrap setup in `try`/`except`
and destroy before re-raising, as `clean_vm` does.

### Running commands

```python
# Via SSH (uses ssh_user, ssh_port, handles port-knocking)
result = vm.ssh("systemctl is-active nginx")

# Via incus exec (bypasses SSH, runs as root)
result = vm.exec("cat /etc/hostname")

# Both return subprocess.CompletedProcess and do not raise on a non-zero exit
```

Two paths on purpose (INCUS-3): `exec()` goes through the Incus agent rather
than the network, so it still works on a machine whose SSH has just been
narrowed, firewalled or knock-gated, which makes it the right way to inspect
the result of the thing under test.

### Port knocking

The knock sequence is yours; the package has none (INCUS-1).

```python
vm.knock(ports=[1111, 2222, 3333])    # Explicit sequence
vm.knock()                            # Uses knock_sequence; ValueError if unset

# Or set knock_sequence and let ssh() handle it automatically
vm.knock_sequence = [1111, 2222, 3333]
vm.ssh("whoami")                      # Auto-knocks if the last knock was >20s ago
```

INCUS-5: knocks go out in order, 0.3 seconds apart, and `ssh()` and
`wait_ready()` re-knock when the last knock is older than 20 seconds. Both
values are fixed; they suit a gate whose stage timeout is a few seconds and
whose pass window is 30 seconds.

### File transfer

```python
vm.put_file("local/config.toml", "/etc/myapp/config.toml")
vm.get_file("/var/log/myapp.log", "test-output/myapp.log")
```

Push is INCUS-4, pull is INCUS-15. The remote path is concatenated onto the
VM name in both directions, so it must be absolute: a relative path
addresses a different instance rather than failing.

### Background services

```python
with vm.background_service("systemctl start myapp", "systemctl stop myapp"):
    result = vm.ssh("curl -s http://localhost:8080/health")
```

INCUS-6: the stop command runs in a `finally`, so it runs even when the block
raises. Its own exit status is discarded: a stop command that fails leaves
the service running and reports nothing.

### SSH keypair

Each VM gets a fresh passphrase-less ed25519 keypair of its own, generated
into a private temp directory named after the machine, with the key at mode
`0600` (INCUS-7). `destroy()` removes the directory. Passing your own
`ssh_key=` overrides that, and if you pass the same one to two VMs, the
first `destroy()` deletes the key the other is still using. To make one
yourself: `SSHKeyPair.create(prefix, name)`.

## run_playbook

Run an Ansible playbook against a VM:

```python
from pathlib import Path

from incus.ansible import run_playbook

result = run_playbook(
    vm,
    playbook_path=Path("playbook.yml"),
    extra_vars={"some_variable": "value"},
    user="deploy",
    cwd=Path("/path/to/repo"),
    timeout=600,
    check_mode=False,
    roles=["my_role"],          # optional: run a generated single-role playbook instead
    roles_path=Path("roles/"),
)
```

INCUS-9: your playbook, your variables, your working directory — passed
through as given, and nothing on the `IncusVM` is mutated. Extra variables
are written to a file inside a private temporary directory and passed as
`-e @file`, never on the command line. The generated inventory names the
machine `testvm`, sets `ansible_python_interpreter` to `/usr/bin/python3`
and forces four SSH options you cannot reach.

INCUS-17: `further_machines={"name": other_vm}` adds each further machine to
the inventory under the name you give it, reached through the
`community.general.incus` connection rather than SSH, so a task can delegate
to it. The run is limited to `vm` (`--limit testvm`) whether or not you pass
any, so a playbook on `hosts: all` still runs only against `vm`.

## Pytest fixtures

Install with `incus[fixtures]` to get:

- **`clean_vm`** — a session-scoped fixture providing a fresh Debian VM with
  no playbook applied.
- **`incus_available()`** — `False` when Incus is not installed or the daemon
  is not running.

`clean_vm` takes its prefix from your suite's pytest configuration, the
`incus_prefix` ini option, which your conftest registers (INCUS-1):

```python
# conftest.py
from incus.fixtures import clean_vm  # noqa: F401


def pytest_addoption(parser):
    parser.addini("incus_prefix", "Name prefix of this suite's Incus machines")
    # optional: the Debian release clean_vm launches, 13 when not declared
    parser.addoption("--debian-version", default="13")
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
incus_prefix = "myproject-test-"
```

Without the option, or with it empty, `clean_vm` **fails** the test rather
than skipping it: a missing prefix is a mistake in the suite. Without Incus
it skips (INCUS-10).

Your own fixtures should ask the same question `clean_vm` asks:

```python
import pytest

from incus import IncusVM
from incus.fixtures import incus_available


@pytest.fixture(scope="session")
def my_vm():
    if not incus_available():
        pytest.skip("Incus not available")

    vm = IncusVM(prefix="myproject-test-", auto_launch=True)
    try:
        vm.wait_ready()
    except Exception:
        vm.destroy()
        raise
    yield vm
    vm.destroy()
```

Set `KEEP_VM_ON_FAIL=1` to keep `clean_vm`'s machine, and its key, after a
failure; the fixture prints how to reach it and how to remove it.

## Command line

Every command takes the required `--prefix` (INCUS-1, INCUS-16):

```bash
uv run python -m incus create --prefix myproject-test- [--debian 13] [--base-image-prefix P]
uv run python -m incus list --prefix myproject-test-
uv run python -m incus destroy --prefix myproject-test- <name>
uv run python -m incus destroy --prefix myproject-test- --all
uv run python -m incus ssh --prefix myproject-test- <name>
```

- `create` launches a bare Debian VM, waits for SSH, prints how to reach and
  destroy it, and saves its details next to its key for `ssh`.
- `list` and `destroy --all` act on the instances whose name starts with the
  prefix, and on no others.
- `destroy <name>` and `ssh <name>` refuse a name that does not start with
  the prefix.
- `ssh <name>` connects with the key `create` saved, looking only under the
  prefix's temporary directories, and falls back to `incus exec` when there
  is none.

Wrap these in your own make targets if you like; the package does not name
any.
