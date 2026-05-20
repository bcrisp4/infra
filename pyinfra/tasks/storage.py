"""LVM RAID10 + XFS provisioning for hosts with the `storage` data key.

Host-specific: hosts without a `storage` dict in inventory data no-op.

Data shape (per host):

    storage = {
        "vg_name": "data",
        "pvs": ["/dev/disk/by-id/usb-...", ...],
        "lvs": [
            {
                "name": "containers",
                "size": "5G",
                "stripes": 2,
                "mirrors": 1,
                "stripesize": "64k",
                "fs": "xfs",
                "mkfs_opts": "-n ftype=1 -m reflink=1,crc=1 -d su=64k,sw=2",
                "mount": "/var/lib/containers",
                "mount_opts": "defaults,noatime,pquota",
            },
        ],
    }

Idempotency: every step queries current state (pvs/vgs/lvs/blkid) and only
yields mutating commands when reality diverges from desired. Safe to re-run.

mkfs safety: refuse to format a device that already holds a different
filesystem. Manual intervention required.

USB write-cache caveat: consumer USB sticks lie about FLUSH/FUA. Power loss
risks RAID10 leg divergence and FS corruption. Not mitigated here. Treat
volumes provisioned by this task as recoverable cache, not durable storage.
Use a UPS if power blips are a concern.
"""

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.command import QuoteString, StringCommand
from pyinfra.facts.server import Command
from pyinfra.operations import apt, files, server


def _lvcreate_args(vg: str, lv: dict) -> list[str]:
    """Render the lvcreate argv for a RAID10 LV spec."""
    return [
        "lvcreate",
        "--yes",
        "--type",
        "raid10",
        "-i",
        str(lv["stripes"]),
        "-m",
        str(lv["mirrors"]),
        "--stripesize",
        lv["stripesize"],
        "-L",
        lv["size"],
        "-n",
        lv["name"],
        vg,
    ]


def _mkfs_command(fs: str, opts: str, device: str) -> str:
    """Render the mkfs command for an LV. Opts is a single string of extra args."""
    if fs != "xfs":
        raise NotImplementedError(f"fs {fs!r} not supported; only xfs")
    return f"mkfs.xfs -f {opts} {device}".strip()


def _fstab_line(device: str, mount: str, fs: str, opts: str) -> str:
    """Render an /etc/fstab line. dump=0, pass=2 (non-root)."""
    return f"{device}\t{mount}\t{fs}\t{opts}\t0\t2"


def _lv_device(vg: str, lv_name: str) -> str:
    """Canonical LVM device path."""
    return f"/dev/{vg}/{lv_name}"


def _ensure_pv(pv: str) -> None:
    """Wipe + pvcreate a disk if it is not already a PV.

    LVM reports PVs by canonical path (e.g. /dev/sda), not by-id symlinks.
    Resolve the symlink before querying so the idempotency check matches.
    """
    is_pv = host.get_fact(
        Command,
        command=(
            f"pvs --noheadings -o pv_name $(readlink -f {pv}) 2>/dev/null "
            "| grep -q . && echo yes || echo no"
        ),
        _sudo=True,
    )
    if is_pv.strip() == "yes":
        return
    server.shell(
        name=f"Wipe + pvcreate {pv}",
        commands=[
            StringCommand("wipefs", "-a", QuoteString(pv)),
            StringCommand("pvcreate", "--yes", QuoteString(pv)),
        ],
        _sudo=True,
    )


def _ensure_vg(vg: str, pvs: list[str]) -> None:
    """vgcreate if missing. Does not vgextend on drift (manual intervention)."""
    exists = host.get_fact(
        Command,
        command=f"vgs --noheadings -o vg_name {vg} 2>/dev/null | grep -q . && echo yes || echo no",
        _sudo=True,
    )
    if exists.strip() == "yes":
        return
    server.shell(
        name=f"vgcreate {vg}",
        commands=[StringCommand("vgcreate", vg, *[QuoteString(p) for p in pvs])],
        _sudo=True,
    )


def _ensure_lv(vg: str, lv: dict) -> None:
    """lvcreate if missing."""
    exists = host.get_fact(
        Command,
        command=(
            f"lvs --noheadings -o lv_name {vg}/{lv['name']} 2>/dev/null "
            "| grep -q . && echo yes || echo no"
        ),
        _sudo=True,
    )
    if exists.strip() == "yes":
        return
    server.shell(
        name=f"lvcreate {vg}/{lv['name']}",
        commands=[StringCommand(*_lvcreate_args(vg, lv))],
        _sudo=True,
    )


def _ensure_fs(device: str, lv: dict) -> None:
    """mkfs if device has no FS. Refuse if a different FS is present."""
    current = host.get_fact(
        Command,
        command=f"blkid -s TYPE -o value {device} 2>/dev/null || true",
        _sudo=True,
    )
    current = (current or "").strip()
    if current == lv["fs"]:
        return
    if current:
        raise ValueError(
            f"{device} already has filesystem {current!r}; refusing to mkfs as "
            f"{lv['fs']!r}. Manual intervention required."
        )
    server.shell(
        name=f"mkfs.{lv['fs']} {device}",
        commands=[_mkfs_command(lv["fs"], lv["mkfs_opts"], device)],
        _sudo=True,
    )


def _ensure_mount(device: str, lv: dict) -> None:
    """Create mount dir, fstab entry, then mount."""
    files.directory(
        name=f"Ensure mount dir {lv['mount']}",
        path=lv["mount"],
        present=True,
        user="root",
        group="root",
        mode="0700",
        _sudo=True,
    )
    files.line(
        name=f"fstab entry for {lv['mount']}",
        path="/etc/fstab",
        line=f"^{device}\\s",
        replace=_fstab_line(device, lv["mount"], lv["fs"], lv["mount_opts"]),
        _sudo=True,
    )
    server.mount(
        name=f"Mount {device} at {lv['mount']}",
        path=lv["mount"],
        device=device,
        fs_type=lv["fs"],
        options=lv["mount_opts"].split(","),
        mounted=True,
        _sudo=True,
    )


@deploy("Storage (LVM RAID10 + XFS)")
def storage() -> None:
    spec = host.data.get("storage")
    if not spec:
        return

    apt.packages(
        name="Install LVM + xfsprogs",
        packages=["lvm2", "xfsprogs"],
        _sudo=True,
    )

    vg = spec["vg_name"]
    pvs = spec["pvs"]
    lvs = spec["lvs"]

    for pv in pvs:
        # `test -b` follows symlinks (by-id paths resolve to /dev/sdX) and
        # asserts the target is a block device. Falsy if drive is unplugged.
        present = host.get_fact(
            Command,
            command=f"test -b {pv} && echo yes || echo no",
        )
        if present.strip() != "yes":
            raise ValueError(f"PV device {pv} not present on host as block device")
        _ensure_pv(pv)

    _ensure_vg(vg, pvs)

    for lv in lvs:
        _ensure_lv(vg, lv)
        device = _lv_device(vg, lv["name"])
        _ensure_fs(device, lv)
        _ensure_mount(device, lv)
