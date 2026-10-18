"""Unit tests for IncusVM command construction and parsing.

``subprocess.run`` is patched throughout, so these tests assert on the
command the package would have run, not on anything that ran.
"""


import json
import socket
import time
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from incus.vm import IncusVM, base_image_alias, ensure_base_image

pytestmark = pytest.mark.unit

_PREFIX = "unit-test-"
_NAME = f"{_PREFIX}abc123"


def _vm(**kwargs) -> IncusVM:
    kwargs.setdefault("prefix", _PREFIX)
    kwargs.setdefault("name", _NAME)
    kwargs.setdefault("ssh_key", MagicMock())
    return IncusVM(**kwargs)


class TestIncusVMPrefix:
    """INCUS-1, PRJ-3: the prefix is the caller's, with no default."""

    def test_construction_without_prefix_fails(self):
        with pytest.raises(TypeError):
            IncusVM(name=_NAME, ssh_key=MagicMock())  # ty: ignore[missing-argument]

    def test_construction_with_empty_prefix_fails(self):
        with pytest.raises(ValueError, match="prefix"):
            IncusVM(prefix="", ssh_key=MagicMock())

    @patch("incus.vm.SSHKeyPair.create")
    def test_generated_name_begins_with_the_callers_prefix(self, mock_keypair):
        vm = IncusVM(prefix="other-")
        assert vm.name.startswith("other-")

    @patch("incus.vm.SSHKeyPair.create")
    def test_generated_keypair_is_given_the_prefix(self, mock_keypair):
        vm = IncusVM(prefix=_PREFIX)
        mock_keypair.assert_called_once_with(_PREFIX, vm.name)

    def test_knock_without_ports_or_sequence_raises_and_connects_nowhere(self):
        vm = _vm(ip_address="10.0.0.42")
        with (
            patch("socket.socket") as mock_socket,
            pytest.raises(ValueError, match="knock sequence"),
        ):
            vm.knock()
        mock_socket.assert_not_called()
        assert vm._last_knock_time == 0.0

    def test_knock_uses_explicit_ports(self):
        vm = _vm(ip_address="10.0.0.42")
        sock = MagicMock()
        sock.__enter__.return_value = sock
        with (
            patch("socket.socket", return_value=sock) as mock_socket,
            patch("incus.vm.time.sleep"),
        ):
            vm.knock(ports=[1111, 2222])
        mock_socket.assert_called_with(socket.AF_INET, socket.SOCK_STREAM)
        assert [c.args[0] for c in sock.connect.call_args_list] == [
            ("10.0.0.42", 1111),
            ("10.0.0.42", 2222),
        ]


class TestBaseImagePrefix:
    """INCUS-1: the base-image build machine and cache alias carry the caller's prefix."""

    def test_alias_begins_with_the_prefix(self):
        assert base_image_alias(_PREFIX, "13") == f"{_PREFIX}base-13"

    def test_alias_begins_with_the_base_image_prefix_where_given(self):
        assert base_image_alias(_PREFIX, "13", base_image_prefix="cache/base-") == "cache/base-13"

    def test_empty_prefix_fails(self):
        with pytest.raises(ValueError, match="prefix"):
            base_image_alias("", "13")
        with pytest.raises(ValueError, match="prefix"):
            ensure_base_image("", "13")

    def test_empty_base_image_prefix_fails(self):
        with pytest.raises(ValueError, match="base_image_prefix"):
            base_image_alias(_PREFIX, "13", base_image_prefix="")

    @patch("incus.vm.subprocess.run")
    def test_build_machine_and_alias_carry_the_prefix(self, mock_run):
        mock_run.side_effect = _build_side_effect(upstream_fp="abc123", existing=[])

        alias = ensure_base_image(_PREFIX, "13")

        assert alias.startswith(_PREFIX)
        launch = next(c.args[0] for c in mock_run.call_args_list if "launch" in c.args[0])
        assert launch[3].startswith(f"{_PREFIX}base-build-")
        publish = next(c.args[0] for c in mock_run.call_args_list if "publish" in c.args[0])
        assert f"--alias={alias}" in publish

    @patch("incus.vm.subprocess.run")
    def test_alias_uses_the_base_image_prefix_where_given(self, mock_run):
        mock_run.side_effect = _build_side_effect(upstream_fp="abc123", existing=[])

        alias = ensure_base_image(_PREFIX, "13", base_image_prefix="cache/base-")

        assert alias == "cache/base-13"
        launch = next(c.args[0] for c in mock_run.call_args_list if "launch" in c.args[0])
        assert launch[3].startswith(f"{_PREFIX}base-build-")

    @patch("incus.vm.ensure_base_image", return_value="cache/base-13")
    @patch("incus.vm.subprocess.run")
    def test_launch_passes_the_base_image_prefix_on(self, mock_run, mock_ensure):
        mock_run.return_value = MagicMock(returncode=0)

        _vm(image="images:debian/13", base_image_prefix="cache/base-").launch()

        mock_ensure.assert_called_once_with(_PREFIX, "13", base_image_prefix="cache/base-")


class TestIncusVMLaunch:
    """INCUS-2: one object launches one machine."""

    @patch("incus.vm.ensure_base_image", return_value=f"{_PREFIX}base-13")
    def test_launch_calls_incus_launch_with_vm_flag(self, _mock_ensure):
        vm = _vm(image="images:debian/13")

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            vm.launch()

        cmd = mock_run.call_args[0][0]
        assert "incus" in cmd[0]
        assert "launch" in cmd
        assert "--vm" in cmd

    @patch("incus.vm.ensure_base_image", return_value=f"{_PREFIX}base-13")
    def test_launch_does_not_use_cloud_init(self, _mock_ensure):
        vm = _vm(image="images:debian/13")

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            vm.launch()

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "cloud-init" not in cmd_str
        assert "user.user-data" not in cmd_str

    def test_launch_raises_with_empty_image(self):
        vm = _vm(image="")
        with pytest.raises(ValueError, match="image is required"):
            vm.launch()

    @patch("incus.vm.ensure_base_image", return_value=f"{_PREFIX}base-13")
    @patch("incus.vm.subprocess.run")
    @patch("incus.vm.SSHKeyPair.create")
    def test_auto_launch_calls_launch(self, mock_keypair, mock_run, _mock_ensure):
        mock_keypair.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=0)

        vm = IncusVM(prefix=_PREFIX, image="images:debian/13", auto_launch=True)

        cmd = mock_run.call_args[0][0]
        assert "launch" in cmd
        assert vm.name in cmd


class TestDebianRelease:
    """INCUS-18: Debian guests, of the release the caller names, 13 by default."""

    @patch("incus.vm.ensure_base_image", return_value=f"{_PREFIX}base-13")
    @patch("incus.vm.subprocess.run")
    def test_default_image_launches_the_cached_base_image_for_13(self, mock_run, mock_ensure):
        mock_run.return_value = MagicMock(returncode=0)

        vm = _vm()
        assert vm.image == "images:debian/13"
        vm.launch()

        mock_ensure.assert_called_once_with(_PREFIX, "13", base_image_prefix=None)
        cmd = mock_run.call_args[0][0]
        assert f"{_PREFIX}base-13" in cmd
        assert "images:debian/13" not in cmd

    @patch("incus.vm.ensure_base_image", return_value=f"{_PREFIX}base-12")
    @patch("incus.vm.subprocess.run")
    def test_caller_named_release_is_passed_through(self, mock_run, mock_ensure):
        mock_run.return_value = MagicMock(returncode=0)

        _vm(image="images:debian/12").launch()

        mock_ensure.assert_called_once_with(_PREFIX, "12", base_image_prefix=None)
        assert f"{_PREFIX}base-12" in mock_run.call_args[0][0]

    @patch("incus.vm.ensure_base_image")
    @patch("incus.vm.subprocess.run")
    def test_other_image_is_launched_as_named(self, mock_run, mock_ensure):
        mock_run.return_value = MagicMock(returncode=0)

        _vm(image="local/prebuilt-13").launch()

        mock_ensure.assert_not_called()
        cmd = mock_run.call_args[0][0]
        assert "local/prebuilt-13" in cmd


class TestIncusVMName:
    """INCUS-14: a name is generated when the caller supplies none."""

    @patch("incus.vm.SSHKeyPair.create")
    def test_name_uses_prefix_and_random_suffix(self, mock_keypair):
        mock_keypair.return_value = MagicMock()

        vm = IncusVM(prefix=_PREFIX)
        assert vm.name.startswith(_PREFIX)
        suffix = vm.name[len(_PREFIX):]
        assert len(suffix) > 0

    @patch("incus.vm.SSHKeyPair.create")
    def test_name_hint_is_incorporated(self, mock_keypair):
        mock_keypair.return_value = MagicMock()

        vm = IncusVM(prefix=_PREFIX, name_hint="myvm")
        assert vm.name.startswith(f"{_PREFIX}myvm-")


class TestIncusVMDestroy:
    """INCUS-13: force-deletion; INCUS-8: the key goes with the machine."""

    def test_destroy_calls_incus_delete_force(self):
        key = MagicMock()
        vm = _vm(ssh_key=key)

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            vm.destroy()

        cmd = mock_run.call_args[0][0]
        assert cmd == ["incus", "delete", _NAME, "--force"]
        key.cleanup.assert_called_once()


class TestIncusVMGetIP:
    def test_get_ip_parses_json_output(self):
        vm = _vm()

        mock_output = json.dumps([{
            "name": _NAME,
            "state": {
                "network": {
                    "enp5s0": {
                        "addresses": [
                            {"family": "inet", "address": "10.0.0.42", "scope": "global"},
                        ]
                    }
                }
            }
        }])

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            ip = vm.get_ip()

        assert ip == "10.0.0.42"


class TestIncusVMExec:
    """INCUS-3: the path through the Incus agent."""

    def test_exec_builds_correct_command(self):
        vm = _vm()

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.exec("whoami")

        cmd = mock_run.call_args[0][0]
        assert cmd == ["incus", "exec", _NAME, "--", "sh", "-c", "whoami"]


_SSH_KEY = MagicMock(private_key_path="/tmp/fake/id_ed25519")


class TestIncusVMSSH:
    """INCUS-3: the path through sshd; INCUS-5: the automatic re-knock."""

    def test_ssh_builds_correct_command(self):
        vm = _vm(ssh_key=_SSH_KEY, ip_address="10.0.0.42")

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.ssh("whoami")

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ssh"
        assert "-i" in cmd
        assert "/tmp/fake/id_ed25519" in cmd
        assert "root@10.0.0.42" in cmd
        assert "whoami" in cmd

    def test_ssh_uses_configured_user(self):
        vm = _vm(ssh_key=_SSH_KEY, ip_address="10.0.0.42", ssh_user="deploy")

        with patch("incus.vm.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.ssh("whoami")

        cmd = mock_run.call_args[0][0]
        assert "deploy@10.0.0.42" in cmd

    def test_ssh_auto_knocks_when_sequence_set_and_stale(self):
        vm = _vm(ssh_key=_SSH_KEY, ip_address="10.0.0.42", knock_sequence=[1111, 2222, 3333])

        with (
            patch("incus.vm.subprocess.run") as mock_run,
            patch.object(vm, "knock") as mock_knock,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.ssh("whoami")

        mock_knock.assert_called_once()

    def test_ssh_skips_knock_when_recent(self):
        vm = _vm(ssh_key=_SSH_KEY, ip_address="10.0.0.42", knock_sequence=[1111, 2222, 3333])
        vm._last_knock_time = time.monotonic()  # just knocked

        with (
            patch("incus.vm.subprocess.run") as mock_run,
            patch.object(vm, "knock") as mock_knock,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.ssh("whoami")

        mock_knock.assert_not_called()

    def test_ssh_no_knock_without_sequence(self):
        vm = _vm(ssh_key=_SSH_KEY, ip_address="10.0.0.42")

        with (
            patch("incus.vm.subprocess.run") as mock_run,
            patch.object(vm, "knock") as mock_knock,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            vm.ssh("whoami")

        mock_knock.assert_not_called()


def _build_side_effect(upstream_fp: str, existing: list):
    """A fake ``subprocess.run`` for :func:`ensure_base_image`."""

    def side_effect(cmd, **kwargs):
        if "image" in cmd and "info" in cmd:
            return MagicMock(
                returncode=0,
                stdout=f"Fingerprint: {upstream_fp}\nSize: 100MiB\n",
            )
        if "image" in cmd and "list" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(existing))
        if "exec" in cmd and "agent-ready" in cmd:
            return MagicMock(returncode=0, stdout="agent-ready")
        if "exec" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0)

    return side_effect


class TestEnsureBaseImage:
    @patch("incus.vm.subprocess.run")
    def test_returns_existing_when_fingerprint_matches(self, mock_run):
        mock_run.side_effect = _build_side_effect(
            upstream_fp="abc123",
            existing=[{
                "fingerprint": "localfp",
                "aliases": [{"name": f"{_PREFIX}base-13"}],
                "properties": {"user.upstream_fingerprint": "abc123"},
            }],
        )
        assert ensure_base_image(_PREFIX, "13") == f"{_PREFIX}base-13"

        # No launch or publish should have happened
        launched = [c for c in mock_run.call_args_list if "launch" in c[0][0]]
        assert len(launched) == 0

    @patch("incus.vm.subprocess.run")
    def test_builds_when_missing(self, mock_run):
        mock_run.side_effect = _build_side_effect(upstream_fp="abc123", existing=[])
        assert ensure_base_image(_PREFIX, "13") == f"{_PREFIX}base-13"

        publish_calls = [c for c in mock_run.call_args_list if "publish" in c[0][0]]
        assert len(publish_calls) == 1
        assert "user.upstream_fingerprint=abc123" in publish_calls[0][0][0]

    @patch("incus.vm.subprocess.run")
    def test_rebuilds_when_fingerprint_stale(self, mock_run):
        mock_run.side_effect = _build_side_effect(
            upstream_fp="new456",
            existing=[{
                "fingerprint": "localfp",
                "aliases": [{"name": f"{_PREFIX}base-13"}],
                "properties": {"user.upstream_fingerprint": "old123"},
            }],
        )
        assert ensure_base_image(_PREFIX, "13") == f"{_PREFIX}base-13"

        # Old image should have been deleted
        image_deletes = [
            c for c in mock_run.call_args_list
            if "image" in c[0][0] and "delete" in c[0][0]
        ]
        assert len(image_deletes) == 1

        # New image published with new fingerprint
        publish_calls = [c for c in mock_run.call_args_list if "publish" in c[0][0]]
        assert len(publish_calls) == 1
        assert "user.upstream_fingerprint=new456" in publish_calls[0][0][0]


class _FakeConfig:
    """Stands in for ``pytest.Config``: ``getini`` raises for an unregistered option."""

    def __init__(self, ini: dict[str, str]) -> None:
        self._ini = ini

    def getini(self, name: str) -> str:
        if name not in self._ini:
            raise ValueError(name)
        return self._ini[name]


@pytest.mark.parametrize(
    ("ini", "expected"),
    [
        ({}, None),
        ({"incus_base_image_prefix": ""}, None),
        ({"incus_base_image_prefix": "acme/base-"}, "acme/base-"),
    ],
)
def test_clean_vm_takes_a_base_image_prefix_from_the_suite(ini, expected) -> None:
    """INCUS-1: the cache alias prefix is the suite's own where it sets one."""
    from incus.fixtures import configured_base_image_prefix

    config = cast(pytest.Config, _FakeConfig(ini))
    assert configured_base_image_prefix(config) == expected
