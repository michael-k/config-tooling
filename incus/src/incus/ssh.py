"""Ephemeral SSH keypair management for Incus VM testing.

INCUS-7: one fresh passphrase-less ed25519 keypair per VM, in a directory of
its own, private key at mode 0600 -- unless the caller passes ``IncusVM`` an
``ssh_key`` of its own, which nothing stops it from sharing between machines.

INCUS-8: ``cleanup()`` is what removes the key from the controller's disk.
Nothing here calls it -- ``IncusVM.destroy()`` does, and nothing guarantees
that anybody calls ``destroy()``; the fixtures are what make the removal
reliable.

INCUS-1: the temporary directory's name and the key comment carry the
caller's prefix, and there is no default.
"""


import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SSHKeyPair:
    """An ephemeral ed25519 SSH keypair for VM access."""

    private_key_path: Path
    public_key: str
    _temp_dir: Path = field(repr=False, compare=False)

    @classmethod
    def create(cls, prefix: str, name: str) -> SSHKeyPair:
        """Generate a new ed25519 keypair in a unique temp directory.

        Args:
            prefix: The caller's prefix (INCUS-1); must not be empty.
            name: The machine the key is for.  The temp directory name and
                the key comment are ``name`` when it already begins with
                ``prefix``, and ``prefix + name`` otherwise.
        """
        if not prefix:
            raise ValueError("prefix is required and must not be empty")
        label = name if name.startswith(prefix) else f"{prefix}{name}"
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{label}-"))
        key_path = temp_dir / "id_ed25519"

        subprocess.run(
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(key_path),
                "-N", "",
                "-C", label,
            ],
            capture_output=True,
            check=True,
        )

        key_path.chmod(0o600)
        public_key = key_path.with_suffix(".pub").read_text().strip()

        return cls(
            private_key_path=key_path,
            public_key=public_key,
            _temp_dir=temp_dir,
        )

    def cleanup(self) -> None:
        """Remove the keypair and its temp directory."""
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)
