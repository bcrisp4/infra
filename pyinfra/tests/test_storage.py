"""Unit tests for pure helpers in tasks.storage."""

import pytest

from tasks.storage import (
    _fstab_line,
    _lv_device,
    _lvcreate_args,
    _mkfs_command,
)


CONTAINERS_LV = {
    "name": "containers",
    "size": "5G",
    "stripes": 2,
    "mirrors": 1,
    "stripesize": "64k",
    "fs": "xfs",
    "mkfs_opts": "-n ftype=1 -m reflink=1,crc=1 -d su=64k,sw=2",
    "mount": "/var/lib/containers",
    "mount_opts": "noatime,prjquota",
}


def test_lv_device_path() -> None:
    assert _lv_device("data", "containers") == "/dev/data/containers"


def test_lvcreate_args_raid10() -> None:
    assert _lvcreate_args("data", CONTAINERS_LV) == [
        "lvcreate",
        "--yes",
        "--type",
        "raid10",
        "-i",
        "2",
        "-m",
        "1",
        "--stripesize",
        "64k",
        "-L",
        "5G",
        "-n",
        "containers",
        "data",
    ]


def test_lvcreate_args_stringifies_ints() -> None:
    """stripes/mirrors come from inventory as ints, must render as strings."""
    args = _lvcreate_args("vg", CONTAINERS_LV)
    assert all(isinstance(a, str) for a in args)


def test_mkfs_command_xfs() -> None:
    cmd = _mkfs_command(
        fs="xfs",
        opts="-n ftype=1 -m reflink=1,crc=1 -d su=64k,sw=2",
        device="/dev/data/containers",
    )
    assert cmd == (
        "mkfs.xfs -f -n ftype=1 -m reflink=1,crc=1 -d su=64k,sw=2 /dev/data/containers"
    )


def test_mkfs_command_always_force() -> None:
    """-f flag must always be present so re-runs do not stall on signature prompts."""
    cmd = _mkfs_command(fs="xfs", opts="", device="/dev/data/x")
    assert " -f " in cmd


def test_mkfs_command_rejects_non_xfs() -> None:
    with pytest.raises(NotImplementedError):
        _mkfs_command(fs="ext4", opts="", device="/dev/data/x")


def test_fstab_line_tab_separated_and_correct_passno() -> None:
    line = _fstab_line(
        device="/dev/data/containers",
        mount="/var/lib/containers",
        fs="xfs",
        opts="noatime,prjquota",
    )
    fields = line.split("\t")
    assert fields == [
        "/dev/data/containers",
        "/var/lib/containers",
        "xfs",
        "noatime,prjquota",
        "0",
        "2",
    ]


@pytest.mark.parametrize(
    ("opts", "expected_tail"),
    [
        ("defaults", "defaults\t0\t2"),
        ("noatime,prjquota", "noatime,prjquota\t0\t2"),
    ],
)
def test_fstab_line_options_preserved_verbatim(opts: str, expected_tail: str) -> None:
    line = _fstab_line("/dev/x", "/mnt/x", "xfs", opts)
    assert line.endswith(expected_tail)
