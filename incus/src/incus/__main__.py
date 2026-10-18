"""CLI entry point for manual Incus VM management.

Usage:
    python -m incus create --prefix PREFIX [--debian VERSION] [--base-image-prefix P]
    python -m incus list --prefix PREFIX
    python -m incus destroy --prefix PREFIX <name>
    python -m incus destroy --prefix PREFIX --all
    python -m incus ssh --prefix PREFIX <name>

INCUS-16: ``create``, ``list``, ``destroy`` and ``ssh`` are registered
wherever this module is run, outside every conditional, and no other command
is.

INCUS-1: every command takes a required, non-empty ``--prefix``.  ``create``
passes it to ``IncusVM``; ``list`` and ``destroy --all`` select only instances
whose name starts with it; ``destroy <name>`` refuses a name that does not;
``ssh <name>`` refuses such a name too and looks for a saved machine only
under the prefix's temporary directories before falling back to
``incus exec``.  The cleanup hint ``create`` prints names this command line.

INCUS-18: ``create`` launches the Debian release ``--debian`` names, 13 by
default.
"""


import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable

from incus.constants import DEFAULT_DEBIAN_VERSION, IMAGE_PREFIX
from incus.vm import IncusVM


def _prefix(value: str) -> str:
    """Argument type for ``--prefix``: an empty prefix matches every instance."""
    if not value:
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def _destroy_hint(prefix: str, name: str) -> str:
    return f"python -m incus destroy --prefix {prefix} {name}"


def _prefixed_instances(prefix: str) -> list[dict]:
    """Every Incus instance whose name starts with ``prefix``."""
    result = subprocess.run(
        ["incus", "list", "--format=json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [v for v in json.loads(result.stdout) if v["name"].startswith(prefix)]


def _refuse_outside_prefix(prefix: str, name: str) -> None:
    if not name.startswith(prefix):
        print(
            f"Error: '{name}' does not start with the prefix '{prefix}'",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_create(args: argparse.Namespace) -> None:
    """Create a new test VM."""
    image = f"{IMAGE_PREFIX}{args.debian}"
    print(f"Creating VM with image {image}...")
    vm = IncusVM(
        prefix=args.prefix,
        image=image,
        base_image_prefix=args.base_image_prefix,
        auto_launch=True,
    )
    print(f"VM '{vm.name}' launched. Waiting for SSH...")
    vm.wait_ready()
    print(f"VM '{vm.name}' ready.")
    print(f"  IP: {vm.ip_address}")
    print(f"  SSH: ssh -i {vm.private_key_path} root@{vm.ip_address}")
    print(f"  Destroy: {_destroy_hint(args.prefix, vm.name)}")

    # Save VM info for the ssh command to find later
    info_path = vm.private_key_path.parent / "vm-info.json"
    info_path.write_text(json.dumps({
        "name": vm.name,
        "ip_address": vm.ip_address,
        "ssh_key": str(vm.private_key_path),
    }))


def cmd_list(args: argparse.Namespace) -> None:
    """List running test VMs."""
    test_vms = _prefixed_instances(args.prefix)

    if not test_vms:
        print("No test VMs running.")
        return

    for vm in test_vms:
        status = vm.get("status", "Unknown")
        ip = ""
        network = vm.get("state", {}).get("network", {})
        for iface_name, iface in network.items():
            if iface_name == "lo":
                continue
            for addr in iface.get("addresses", []):
                if addr.get("family") == "inet" and addr.get("scope") == "global":
                    ip = addr["address"]
                    break
        print(f"  {vm['name']}  {status}  {ip}")


def cmd_destroy(args: argparse.Namespace) -> None:
    """Destroy test VM(s)."""
    if args.all:
        test_vms = _prefixed_instances(args.prefix)

        if not test_vms:
            print("No test VMs to destroy.")
            return

        for vm in test_vms:
            name = vm["name"]
            print(f"Destroying {name}...")
            subprocess.run(
                ["incus", "delete", name, "--force"],
                capture_output=True,
                text=True,
                check=False,
            )
        print(f"Destroyed {len(test_vms)} test VM(s).")
    else:
        if not args.name:
            print("Error: specify a VM name or use --all", file=sys.stderr)
            sys.exit(1)
        _refuse_outside_prefix(args.prefix, args.name)
        print(f"Destroying {args.name}...")
        subprocess.run(
            ["incus", "delete", args.name, "--force"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"Destroyed {args.name}.")


def cmd_ssh(args: argparse.Namespace) -> None:
    """SSH into a test VM."""
    _refuse_outside_prefix(args.prefix, args.name)

    pattern = os.path.join(tempfile.gettempdir(), f"{glob.escape(args.prefix)}*", "vm-info.json")
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            info = json.loads(f.read())
        if info.get("name") != args.name:
            continue
        os.execvp("ssh", [
            "ssh",
            "-o", "PubkeyAuthentication=yes",
            "-o", "StrictHostKeyChecking=no",
            "-i", info["ssh_key"],
            f"root@{info['ip_address']}",
        ])

    # Fallback: use incus exec (works even without saved SSH key)
    print(f"No saved SSH key found for '{args.name}'. Using incus exec instead.")
    os.execvp("incus", ["incus", "exec", args.name, "--", "/bin/bash"])


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--prefix", required=True, type=_prefix,
        help="Name prefix of the machines this command acts on (required)",
    )

    parser = argparse.ArgumentParser(
        description="Manage Incus VMs for integration testing",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = subparsers.add_parser("create", parents=[common], help="Create a new test VM")
    p_create.add_argument(
        "--debian", default=DEFAULT_DEBIAN_VERSION,
        help=f"Debian version (default: {DEFAULT_DEBIAN_VERSION})",
    )
    p_create.add_argument(
        "--base-image-prefix", default=None,
        help="Alias prefix of the cached base image (default: the --prefix)",
    )

    # list
    subparsers.add_parser("list", parents=[common], help="List running test VMs")

    # destroy
    p_destroy = subparsers.add_parser("destroy", parents=[common], help="Destroy test VM(s)")
    p_destroy.add_argument("name", nargs="?", help="VM name to destroy")
    p_destroy.add_argument("--all", action="store_true", help="Destroy all prefixed VMs")

    # ssh
    p_ssh = subparsers.add_parser("ssh", parents=[common], help="SSH into a test VM")
    p_ssh.add_argument("name", help="VM name")

    commands: dict[str, Callable[[argparse.Namespace], None]] = {
        "create": cmd_create,
        "list": cmd_list,
        "destroy": cmd_destroy,
        "ssh": cmd_ssh,
    }

    args = parser.parse_args()
    commands[args.command](args)


if __name__ == "__main__":
    main()
