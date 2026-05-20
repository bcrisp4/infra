"""pyinfra inventory.

Top-level lists become groups (the variable name = group name).
Per-host data goes in the tuple; shared group data lives in group_data/<group>.py.
"""

homelab = [
    (
        "rpi5-4cpu-16gb-home.marlin-tet.ts.net",
        {
            "ssh_user": "ben",
        },
    ),
]
