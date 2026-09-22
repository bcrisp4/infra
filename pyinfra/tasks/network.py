"""Manage the Pi's DHCP network profile through its Netplan source file."""

from __future__ import annotations

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server

NETPLAN_DIR = "/etc/netplan"
LEGACY_KEYFILE_PATH = (
    "/etc/NetworkManager/system-connections/Wired connection 1.nmconnection"
)


def _render_netplan(data: Mapping) -> str:
    """Render a DHCP-enabled Netplan profile.

    Args:
        data: The interface and NetworkManager profile identity.

    Returns:
        Netplan YAML for the DHCP profile.
    """
    connection_uuid = data["connection_uuid"]
    connection_name = data["connection_name"]

    return (
        "\n".join(
            [
                "network:",
                "  version: 2",
                "  ethernets:",
                f"    {data['interface']}:",
                "      renderer: NetworkManager",
                "      match: {}",
                "      dhcp4: true",
                "      networkmanager:",
                f'        uuid: "{connection_uuid}"',
                f'        name: "{connection_name}"',
                "        passthrough:",
                '          proxy._: ""',
            ]
        )
        + "\n"
    )


@deploy("DHCP network config")
def dhcp_network() -> None:
    """Configure eth0 for DHCP through Netplan."""
    config = host.data.get("netplan")
    if not config:
        return

    data = dict(config)
    netplan_path = f"{NETPLAN_DIR}/90-NM-{data['connection_uuid']}.yaml"

    netplan_config = files.put(
        name=f"Render {netplan_path}",
        src=StringIO(_render_netplan(data)),
        dest=netplan_path,
        user="root",
        group="root",
        mode="0600",
        _sudo=True,
    )

    legacy_keyfile = files.file(
        name=f"Remove legacy static profile {LEGACY_KEYFILE_PATH}",
        path=LEGACY_KEYFILE_PATH,
        present=False,
        _sudo=True,
    )

    server.shell(
        name="Reload NetworkManager profiles after legacy profile removal",
        commands=["nmcli connection reload"],
        _if=legacy_keyfile.did_change,
        _sudo=True,
    )

    server.shell(
        name="Apply Netplan DHCP config on change",
        commands=["netplan generate && netplan apply"],
        _if=netplan_config.did_change,
        _sudo=True,
    )
