"""Install + enable unattended-upgrades for security patches."""

from pathlib import Path

from pyinfra.api import deploy
from pyinfra.operations import apt, files

FILES_DIR = Path(__file__).resolve().parent.parent / "files"


@deploy("Unattended upgrades")
def unattended_upgrades() -> None:
    apt.packages(
        name="Install unattended-upgrades",
        packages=["unattended-upgrades"],
        _sudo=True,
    )

    files.put(
        name="Enable periodic unattended-upgrades",
        src=str(FILES_DIR / "20auto-upgrades"),
        dest="/etc/apt/apt.conf.d/20auto-upgrades",
        mode="644",
        user="root",
        group="root",
        _sudo=True,
    )
