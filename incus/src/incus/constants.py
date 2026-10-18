"""Default constants for Incus VM testing.

INCUS-18: ``IMAGE_PREFIX`` and ``DEFAULT_DEBIAN_VERSION`` make the default
image ``images:debian/13``; the release is the caller's to change.

No value here identifies a project: the machine, temporary-directory, key and
base-image prefixes all come from the caller.
"""


IMAGE_PREFIX = "images:debian/"

DEFAULT_DEBIAN_VERSION = "13"

VM_READY_TIMEOUT_SECONDS = 120

SSH_CONNECT_TIMEOUT_SECONDS = 10

SSH_POLL_INTERVAL_SECONDS = 2
