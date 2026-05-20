"""Shared data for the `homelab` group.

Override per host by setting the same key in inventory.py host tuple.
"""

timezone = "UTC"

base_packages = [
    "vim",
    "git",
    "htop",
    "tmux",
    "curl",
]
