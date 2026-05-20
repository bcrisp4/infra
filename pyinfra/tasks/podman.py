"""Install Podman (rootful) and patch Raspberry Pi cmdline for cgroup memory controller.

On Raspberry Pi 5 with Pi OS (Debian 13 trixie), the firmware device tree injects
`cgroup_disable=memory` ahead of `cmdline.txt` content, so the memory cgroup is
disabled by default. The Raspberry Pi kernel has a downstream-only `cgroup_enable=`
parameter that, when applied AFTER the disable (i.e. in cmdline.txt, which the
firmware appends), re-enables the memory controller. `cgroup_memory=1` is not a
recognised kernel parameter and is intentionally not used (the kernel logs it as
unknown). See raspberrypi/linux issue #6980 for the maintainer's guidance.

We also defensively strip any prior `cgroup_disable=memory` or `cgroup_memory=1`
that may already exist in cmdline.txt — neither belongs there, and earlier
revisions of this task wrote `cgroup_memory=1` to it.

The user reboots the host manually after the file changes.

Gated on `install_podman` host/group data so non-podman targets are unaffected.
"""

from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import apt, files, server

CMDLINE_PATH = "/boot/firmware/cmdline.txt"
CMDLINE_BACKUP_PATH = f"{CMDLINE_PATH}.pre-podman.bak"
DROP_PARAMS = frozenset({"cgroup_disable=memory", "cgroup_memory=1"})
ENSURE_PARAMS = ("cgroup_enable=memory",)
PODMAN_PKGS = ["podman", "crun", "netavark", "catatonit", "buildah"]


def _rewrite_cmdline(content: str) -> str:
    """Return cmdline.txt content with DROP_PARAMS removed and ENSURE_PARAMS present.

    Pi cmdline.txt is a single line of space-separated kernel params. We tokenize
    on whitespace, drop blacklisted tokens, append any missing required tokens,
    then rejoin with single spaces and a single trailing newline.
    """
    tokens = [t for t in content.split() if t not in DROP_PARAMS]
    for required in ENSURE_PARAMS:
        if required not in tokens:
            tokens.append(required)
    return " ".join(tokens) + "\n"


@deploy("Install podman")
def install_podman() -> None:
    if not host.data.get("install_podman", False):
        return

    apt.packages(
        name="Install podman + container runtime deps",
        packages=PODMAN_PKGS,
        _sudo=True,
    )

    # Pi-specific cmdline patch. Skip on non-Pi hosts that lack the file.
    if not host.get_fact(File, path=CMDLINE_PATH):
        return

    current = host.get_fact(Command, command=f"cat {CMDLINE_PATH}") or ""
    desired = _rewrite_cmdline(current)
    if desired.strip() == current.strip():
        return

    # One-shot backup of the original cmdline.txt before our first patch. Fact-gated
    # so re-runs after the file has been rewritten don't overwrite the pristine copy.
    if not host.get_fact(File, path=CMDLINE_BACKUP_PATH):
        server.shell(
            name="Back up pristine cmdline.txt before patch",
            commands=[f"cp -p {CMDLINE_PATH} {CMDLINE_BACKUP_PATH}"],
            _sudo=True,
        )

    files.put(
        name="Patch cmdline.txt for memory cgroup controller (manual reboot required)",
        src=StringIO(desired),
        dest=CMDLINE_PATH,
        _sudo=True,
    )
