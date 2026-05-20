"""pyinfra inventory.

Top-level lists become groups (the variable name = group name).
Per-host data goes in the tuple; shared group data lives in group_data/<group>.py.
"""

_RPI5_USB_BY_ID = [
    "/dev/disk/by-id/usb-USB_SanDisk_3.2Gen1_05016a5aee9c6fff3283f6163f1be2c001eef17e464cbfeacacf7e1103dfd29e608d0000000000000000000058b04cc4ff11191083558107a1a91786-0:0",
    "/dev/disk/by-id/usb-USB_SanDisk_3.2Gen1_050169708d595942b92c935fa9a8760aff31ce19b0090667439e0afbdc3c05060b5e00000000000000000000e2ad1b650093191083558107a1a9175e-0:0",
    "/dev/disk/by-id/usb-USB_SanDisk_3.2Gen1_050145f0904b122c7aa37f3b91688e14faf7e0786872e063807b84111e9ce31d108f000000000000000000008cb90c1b001d191083558107a1a91798-0:0",
    "/dev/disk/by-id/usb-USB_SanDisk_3.2Gen1_0501e14601cd9ac121c089d5495792f90bb4805f568295492eda39018a0bc55cfc140000000000000000000057c64bb1ff90191083558107a1a91795-0:0",
]

homelab = [
    (
        "rpi5-4cpu-16gb-home.marlin-tet.ts.net",
        {
            "ssh_user": "ben",
            "storage": {
                "vg_name": "data",
                "pvs": _RPI5_USB_BY_ID,
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
                        "mount_opts": "noatime,prjquota",
                    },
                ],
            },
        },
    ),
]
