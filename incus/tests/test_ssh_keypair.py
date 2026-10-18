"""Unit tests for ephemeral SSH keypair management.

These run ``ssh-keygen`` on the controller; they need neither Incus nor the
network.
"""


import pytest

from incus.ssh import SSHKeyPair

pytestmark = pytest.mark.unit

_PREFIX = "unit-test-"


class TestSSHKeyPairPrefix:
    """INCUS-1, PRJ-3: the prefix is the caller's, with no default."""

    def test_create_without_prefix_fails(self):
        with pytest.raises(TypeError):
            SSHKeyPair.create(name="vm")  # ty: ignore[missing-argument]

    def test_create_with_empty_prefix_fails(self):
        with pytest.raises(ValueError, match="prefix"):
            SSHKeyPair.create("", "vm")

    def test_temp_directory_and_comment_carry_the_prefix(self):
        kp = SSHKeyPair.create(_PREFIX, "vm")
        try:
            assert kp.private_key_path.parent.name.startswith(f"{_PREFIX}vm-")
            assert kp.public_key.split()[2] == f"{_PREFIX}vm"
        finally:
            kp.cleanup()

    def test_a_name_that_already_carries_the_prefix_is_not_prefixed_twice(self):
        kp = SSHKeyPair.create(_PREFIX, f"{_PREFIX}abc123")
        try:
            assert kp.private_key_path.parent.name.startswith(f"{_PREFIX}abc123-")
            assert kp.public_key.split()[2] == f"{_PREFIX}abc123"
        finally:
            kp.cleanup()


class TestSSHKeyPairCreate:
    """INCUS-7: one fresh ed25519 keypair per machine, private key at 0600."""

    def test_creates_private_key_file(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        try:
            assert kp.private_key_path.exists()
        finally:
            kp.cleanup()

    def test_private_key_has_restricted_permissions(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        try:
            mode = kp.private_key_path.stat().st_mode & 0o777
            assert mode == 0o600
        finally:
            kp.cleanup()

    def test_public_key_is_nonempty_string(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        try:
            assert isinstance(kp.public_key, str)
            assert len(kp.public_key) > 0
            assert "ssh-ed25519" in kp.public_key
        finally:
            kp.cleanup()

    def test_private_key_in_unique_temp_directory(self):
        kp1 = SSHKeyPair.create(_PREFIX, "vm-a")
        kp2 = SSHKeyPair.create(_PREFIX, "vm-b")
        try:
            assert kp1.private_key_path.parent != kp2.private_key_path.parent
        finally:
            kp1.cleanup()
            kp2.cleanup()


class TestSSHKeyPairCleanup:
    """INCUS-8: cleanup removes the key and its directory."""

    def test_cleanup_removes_private_key(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        key_path = kp.private_key_path
        kp.cleanup()
        assert not key_path.exists()

    def test_cleanup_removes_temp_directory(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        temp_dir = kp.private_key_path.parent
        kp.cleanup()
        assert not temp_dir.exists()

    def test_cleanup_idempotent(self):
        kp = SSHKeyPair.create(_PREFIX, "test-vm")
        kp.cleanup()
        kp.cleanup()  # Should not raise
