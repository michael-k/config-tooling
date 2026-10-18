"""Pytest fixtures for Incus VM integration testing.

INCUS-10: ``incus_available()`` is defined once, here, and exported so that a
consuming repository's own fixtures ask the same question this package's
fixture asks.  ``clean_vm`` calls it and skips rather than fails.

INCUS-1: ``clean_vm`` takes its machine prefix from the consuming suite's
pytest configuration, the ``incus_prefix`` ini option, and fails rather than
skips when the option is not registered or is empty: a missing prefix is a
mistake in the suite, not an absent Incus.  The cleanup hint
``print_debug_info`` prints names this package's own command line.

INCUS-18: ``clean_vm`` reads ``--debian-version`` through
``getoption(name, default)``, which falls back to Debian 13 when the option
was never declared, so the fixture also works in a consumer that does not
register it.  The option, where it exists, is the consumer's.
"""


import os
import shutil
import subprocess

import pytest

from incus.constants import DEFAULT_DEBIAN_VERSION, IMAGE_PREFIX
from incus.vm import IncusVM

PREFIX_INI_OPTION = "incus_prefix"


def incus_available() -> bool:
    """Check if Incus CLI is available and daemon is running."""
    if not shutil.which("incus"):
        return False
    result = subprocess.run(
        ["incus", "list", "--format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def configured_prefix(config: pytest.Config) -> str:
    """Return the suite's ``incus_prefix``, failing the test when it is unset."""
    try:
        prefix = config.getini(PREFIX_INI_OPTION)
    except ValueError:
        prefix = ""
    if not isinstance(prefix, str) or not prefix:
        pytest.fail(
            f"the '{PREFIX_INI_OPTION}' pytest ini option is not set: register it "
            f"with parser.addini('{PREFIX_INI_OPTION}', ...) in the suite's conftest "
            "and set it to the machine prefix this suite owns",
            pytrace=False,
        )
    return prefix


def _should_keep(request: pytest.FixtureRequest) -> bool:
    """Check if VMs should be preserved on failure."""
    if not os.environ.get("KEEP_VM_ON_FAIL"):
        return False
    failed = getattr(request.session, "testsfailed", 0)
    errored = getattr(request.session, "testserrors", 0)
    return (failed + errored) > 0


def print_debug_info(vm: IncusVM) -> None:
    """Print connection info for a preserved VM."""
    print(
        f"\nVM '{vm.name}' preserved for debugging.\n"
        f"  SSH: ssh -i {vm.private_key_path} root@{vm.ip_address}\n"
        f"  Cleanup: python -m incus destroy --prefix {vm.prefix} {vm.name}\n"
    )


@pytest.fixture(scope="session")
def clean_vm(request):
    """Fresh Debian VM with no playbook applied."""
    prefix = configured_prefix(request.config)
    if not incus_available():
        pytest.skip("Incus not available")

    version = request.config.getoption("--debian-version", DEFAULT_DEBIAN_VERSION)
    image = f"{IMAGE_PREFIX}{version}"

    vm = IncusVM(prefix=prefix, image=image, auto_launch=True)
    try:
        vm.wait_ready()
    except Exception:
        if os.environ.get("KEEP_VM_ON_FAIL"):
            print_debug_info(vm)
        else:
            vm.destroy()
        raise

    yield vm

    if _should_keep(request):
        print_debug_info(vm)
    else:
        vm.destroy()
