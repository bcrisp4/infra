"""dnsmasq in DHCP-only mode (port=0 — bns owns DNS on :53).

Hands out bns as DHCP option 6 to LAN clients so DNS no longer flows
through the CR1000A as a middleman forwarder. The CR1000A admin UI does
not expose DHCP option 6, hence the standalone DHCP server.

Gated on `dnsmasq_enabled`. Config written to /etc/dnsmasq.d/dhcp.conf
(the package main file stays untouched; it includes /etc/dnsmasq.d/*.conf
via conf-dir).
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, systemd

CONFIG_PATH = "/etc/dnsmasq.d/dhcp.conf"

_DATA_KEYS = (
    "dnsmasq_interface",
    "dnsmasq_dhcp_range_start",
    "dnsmasq_dhcp_range_end",
    "dnsmasq_dhcp_netmask",
    "dnsmasq_dhcp_lease",
    "dnsmasq_gateway",
    "dnsmasq_dns",
)


def _render_config(data: Mapping) -> str:
    """Render dnsmasq DHCP-only config from host data."""
    dhcp_range = (
        f"{data['dnsmasq_dhcp_range_start']},"
        f"{data['dnsmasq_dhcp_range_end']},"
        f"{data['dnsmasq_dhcp_netmask']},"
        f"{data['dnsmasq_dhcp_lease']}"
    )
    lines = [
        "# Rendered by pyinfra tasks/dhcp.py. Do not edit by hand.",
        # port=0 disables dnsmasq's DNS server; bns owns :53.
        "port=0",
        f"interface={data['dnsmasq_interface']}",
        # bind-dynamic adapts to interface up/down via netlink, unlike
        # bind-interfaces which fails to start if iface not yet present.
        "bind-dynamic",
        # Authoritative responses to existing clients with router-issued
        # leases so they switch faster after the router DHCP is disabled.
        "dhcp-authoritative",
        "domain-needed",
        "bogus-priv",
        # DNS disabled, so dnsmasq has no reason to read resolv.conf.
        "no-resolv",
        f"dhcp-range={dhcp_range}",
        f"dhcp-option=3,{data['dnsmasq_gateway']}",
        f"dhcp-option=6,{data['dnsmasq_dns']}",
    ]
    return "\n".join(lines) + "\n"


@deploy("dnsmasq DHCP server")
def dnsmasq() -> None:
    if not host.data.get("dnsmasq_enabled", False):
        return

    data = {k: host.data.get(k) for k in _DATA_KEYS}

    apt.packages(
        name="Install dnsmasq",
        packages=["dnsmasq"],
        _sudo=True,
    )

    config = files.put(
        name=f"Render {CONFIG_PATH}",
        src=StringIO(_render_config(data)),
        dest=CONFIG_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    systemd.service(
        name="Restart dnsmasq on config change",
        service="dnsmasq.service",
        running=True,
        enabled=True,
        restarted=True,
        _if=config.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure dnsmasq.service running + enabled",
        service="dnsmasq.service",
        running=True,
        enabled=True,
        _sudo=True,
    )
