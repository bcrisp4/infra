"""Force PCIe Gen 3.0 on the Raspberry Pi 5 via /boot/firmware/config.txt.

The Pi 5 defaults all PCIe lanes to Gen 2.0 (~5 GT/s). Adding `dtparam=pciex1`
and `dtparam=pciex1_gen=3` forces Gen 3.0 (~10 GT/s). Gen 3.0 is NOT officially
certified on the Pi 5 and may be unstable depending on cable/device quality.

This task edits config.txt SURGICALLY: it only ever inserts/replaces a single
marked block (BLOCK_BEGIN..BLOCK_END) and never touches any other line of the
distro-owned file. A pristine backup is taken once before the first patch.

A reboot is required for the change to take effect. The user reboots manually
(matches tasks/podman.py, which patches cmdline.txt the same way).

Gated on `pcie_gen3_enabled`; the gen value is `pcie_gen` (default 3).
"""

from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

CONFIG_PATH = "/boot/firmware/config.txt"
CONFIG_BACKUP_PATH = f"{CONFIG_PATH}.pre-pcie.bak"
BLOCK_BEGIN = "# BEGIN pyinfra pcie (tasks/pcie.py) - managed, do not edit"
BLOCK_END = "# END pyinfra pcie"


def _render_block(gen: int) -> str:
    """Render the managed config.txt block forcing PCIe Gen ``gen``.

    The block carries its own ``[all]`` filter so the dtparams apply globally
    regardless of any trailing section filter already in config.txt.
    """
    return (
        "\n".join(
            [
                BLOCK_BEGIN,
                "[all]",
                "dtparam=pciex1",
                f"dtparam=pciex1_gen={gen}",
                BLOCK_END,
            ]
        )
        + "\n"
    )


def _strip_block(content: str) -> str:
    """Return ``content`` with the managed block (markers inclusive) removed.

    Any blank lines immediately preceding the block are also dropped so repeated
    apply/strip cycles do not accumulate whitespace. The result is normalized to
    a single trailing newline (empty input yields an empty string). All lines
    outside the markers are preserved verbatim and in order.
    """
    out: list[str] = []
    inside = False
    for line in content.split("\n"):
        if line == BLOCK_BEGIN:
            inside = True
            while out and out[-1] == "":
                out.pop()
            continue
        if inside:
            if line == BLOCK_END:
                inside = False
            continue
        out.append(line)
    text = "\n".join(out).rstrip("\n")
    return text + "\n" if text else ""


def _ensure_block(content: str, gen: int) -> str:
    """Return config.txt content with exactly one managed PCIe block for ``gen``.

    Strips any pre-existing managed block, then appends a fresh one separated by
    a single blank line. Idempotent: same content + same gen yields identical
    output. Only the managed block is ever changed; all other lines are kept
    verbatim and in their original order.
    """
    base = _strip_block(content).rstrip("\n")
    block = _render_block(gen)
    if base:
        return f"{base}\n\n{block}"
    return block


@deploy("PCIe Gen 3")
def pcie_gen3() -> None:
    """Patch config.txt to force PCIe Gen N on the Pi 5 (manual reboot required)."""
    if not host.data.get("pcie_gen3_enabled", False):
        return

    gen = int(host.data.get("pcie_gen", 3))

    # Pi-only: skip hosts lacking the boot config file.
    if not host.get_fact(File, path=CONFIG_PATH):
        return

    current = host.get_fact(Command, command=f"cat {CONFIG_PATH}") or ""
    desired = _ensure_block(current, gen)
    if desired == current:
        return

    # One-shot backup of the pristine config.txt before our first patch. Fact-gated
    # so re-runs after the file has been patched don't overwrite the pristine copy.
    if not host.get_fact(File, path=CONFIG_BACKUP_PATH):
        server.shell(
            name="Back up pristine config.txt before PCIe patch",
            commands=[f"cp -p {CONFIG_PATH} {CONFIG_BACKUP_PATH}"],
            _sudo=True,
        )

    # /boot/firmware is vfat: omit user/group/mode (same as tasks/podman.py).
    files.put(
        name=f"Patch config.txt for PCIe Gen {gen} (manual reboot required)",
        src=StringIO(desired),
        dest=CONFIG_PATH,
        _sudo=True,
    )
