"""Unit tests for Ansible playbook execution helpers.

``subprocess.run`` is patched: nothing here runs ``ansible-playbook``.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from incus.ansible import (
    build_inventory,
    build_single_role_playbook,
    run_playbook,
)
from incus.vm import IncusVM

pytestmark = pytest.mark.unit

_SSH_KEY = MagicMock(private_key_path=Path("/tmp/fake/id_ed25519"))
_PREFIX = "unit-test-"
_VM = IncusVM(
    prefix=_PREFIX, name=f"{_PREFIX}abc123", ssh_key=_SSH_KEY, ip_address="10.0.0.42",
)
_PEER = IncusVM(
    prefix=_PREFIX, name=f"{_PREFIX}peer-def456", ssh_key=_SSH_KEY, ip_address="10.0.0.43",
)


class TestBuildInventory:
    """INCUS-9: the inventory names the machine the runner was given."""

    def test_generates_valid_yaml_inventory(self):
        content = build_inventory(_VM)
        inv = yaml.safe_load(content)

        assert "all" in inv
        host_vars = inv["all"]["hosts"]["testvm"]
        assert host_vars["ansible_host"] == "10.0.0.42"
        assert host_vars["ansible_ssh_private_key_file"] == "/tmp/fake/id_ed25519"
        assert host_vars["ansible_user"] == "root"
        assert host_vars["ansible_port"] == 22

    def test_uses_vm_ssh_port(self):
        vm = IncusVM(
            prefix=_PREFIX, name=f"{_PREFIX}abc123", ssh_key=_SSH_KEY,
            ip_address="10.0.0.42", ssh_port=2222,
        )

        content = build_inventory(vm)
        inv = yaml.safe_load(content)
        assert inv["all"]["hosts"]["testvm"]["ansible_port"] == 2222

    def test_uses_custom_user(self):
        content = build_inventory(_VM, user="ansible")
        inv = yaml.safe_load(content)
        assert inv["all"]["hosts"]["testvm"]["ansible_user"] == "ansible"

    def test_holds_only_the_given_machine_by_default(self):
        inv = yaml.safe_load(build_inventory(_VM))
        assert set(inv["all"]["hosts"]) == {"testvm"}

    def test_adds_further_machines_over_incus(self):
        """INCUS-17: a further machine is reached over Incus, under the caller's name."""
        inv = yaml.safe_load(build_inventory(_VM, further_machines={"peer": _PEER}))
        hosts = inv["all"]["hosts"]
        assert hosts["peer"] == {
            "ansible_connection": "community.general.incus",
            "ansible_host": f"{_PREFIX}peer-def456",
        }
        assert hosts["testvm"] == yaml.safe_load(build_inventory(_VM))["all"]["hosts"]["testvm"]


class TestBuildSingleRolePlaybook:
    def test_generates_playbook_with_single_role(self):
        content = build_single_role_playbook("example_role")
        playbook = yaml.safe_load(content)

        assert len(playbook) == 1
        play = playbook[0]
        assert play["become"] is True
        assert {"role": "example_role"} in play["roles"]

    def test_generates_playbook_with_role_list(self):
        content = build_single_role_playbook(["other_role", "example_role"])
        playbook = yaml.safe_load(content)

        play = playbook[0]
        assert len(play["roles"]) == 2
        assert {"role": "other_role"} in play["roles"]
        assert {"role": "example_role"} in play["roles"]


class TestRunPlaybook:
    """INCUS-9: the caller's playbook, variables and paths, passed through unchanged."""

    @patch("incus.ansible.subprocess.run")
    def test_runs_ansible_playbook_directly(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        run_playbook(_VM, playbook_path=Path("/tmp/playbook.yml"))

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ansible-playbook"
        cmd_str = " ".join(str(c) for c in cmd)
        assert "/tmp/playbook.yml" in cmd_str

    @patch("incus.ansible.subprocess.run")
    def test_passes_extra_vars_via_json_file(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        run_playbook(_VM, playbook_path=Path("/tmp/playbook.yml"), extra_vars={"ssh_port": 2222})

        cmd = mock_run.call_args[0][0]
        extra_var_args = [c for c in cmd if str(c).startswith("@")]
        assert len(extra_var_args) == 1
        assert "-e" in cmd

    @patch("incus.ansible.subprocess.run")
    def test_passes_cwd(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        run_playbook(_VM, playbook_path=Path("/tmp/playbook.yml"), cwd="/some/dir")

        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == "/some/dir"

    @patch("incus.ansible.subprocess.run")
    def test_does_not_mutate_vm_ssh_port(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        run_playbook(_VM, playbook_path=Path("/tmp/playbook.yml"), extra_vars={"ssh_port": 2222})

        # run_playbook should NOT mutate vm.ssh_port
        assert _VM.ssh_port == 22

    @patch("incus.ansible.subprocess.run")
    def test_limits_the_run_to_the_given_machine(self, mock_run):
        """INCUS-17: the run is limited to testvm, with or without further machines."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        run_playbook(
            _VM, playbook_path=Path("/tmp/playbook.yml"), further_machines={"peer": _PEER},
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("--limit") + 1] == "testvm"
        assert cmd.count("--limit") == 1

        run_playbook(_VM, playbook_path=Path("/tmp/playbook.yml"))

        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("--limit") + 1] == "testvm"
        assert cmd.count("--limit") == 1

    @patch("incus.ansible.subprocess.run")
    def test_passes_further_machines_to_the_inventory(self, mock_run):
        """INCUS-17: the inventory the run reads holds the further machine."""
        seen: dict = {}

        def read_inventory(cmd, **_kwargs):
            seen.update(yaml.safe_load(Path(cmd[cmd.index("-i") + 1]).read_text()))
            return MagicMock(returncode=0, stdout="ok", stderr="")

        mock_run.side_effect = read_inventory

        run_playbook(
            _VM, playbook_path=Path("/tmp/playbook.yml"), further_machines={"peer": _PEER},
        )

        assert set(seen["all"]["hosts"]) == {"testvm", "peer"}
