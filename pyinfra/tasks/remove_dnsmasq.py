"""Remove the Pi's former dnsmasq DHCP service."""

from __future__ import annotations

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, systemd

DHCP_CONFIG_PATH = "/etc/dnsmasq.d/dhcp.conf"


@deploy("Remove dnsmasq DHCP service")
def remove_dnsmasq() -> None:
    """Stop and remove the former dnsmasq DHCP service."""
    if not host.data.get("remove_dnsmasq_enabled", False):
        return

    systemd.service(
        name="Stop and disable dnsmasq.service",
        service="dnsmasq.service",
        running=False,
        enabled=False,
        _sudo=True,
    )

    apt.packages(
        name="Purge dnsmasq package",
        packages=["dnsmasq"],
        present=False,
        purge=True,
        _sudo=True,
    )

    files.file(
        name=f"Remove {DHCP_CONFIG_PATH}",
        path=DHCP_CONFIG_PATH,
        present=False,
        _sudo=True,
    )
