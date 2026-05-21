"""Static network config via NetworkManager keyfile.

Renders /etc/NetworkManager/system-connections/<id>.nmconnection from host
data. On change, runs `nmcli con reload && nmcli con up '<id>'` so NM picks
up the edit. Gated on `static_network_enabled`.

Required keys in host data `static_network` dict: connection_id,
connection_uuid, interface, ipv4_address (CIDR), ipv4_gateway, ipv4_dns
(list), ipv6_method.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server

KEYFILE_DIR = "/etc/NetworkManager/system-connections"


def _render_nmconnection(data: Mapping) -> str:
    """Render an NM ethernet keyfile from host data."""
    ipv4_dns = ";".join(data["ipv4_dns"]) + ";"
    lines = [
        "# Rendered by pyinfra tasks/network.py. Do not edit by hand.",
        "[connection]",
        f"id={data['connection_id']}",
        # UUID must match the existing in-memory connection or NM creates a
        # new one alongside, leading to two profiles fighting for the iface.
        f"uuid={data['connection_uuid']}",
        "type=ethernet",
        f"interface-name={data['interface']}",
        "autoconnect=true",
        "autoconnect-priority=-999",
        "",
        "[ethernet]",
        "",
        "[ipv4]",
        "method=manual",
        f"address1={data['ipv4_address']},{data['ipv4_gateway']}",
        f"dns={ipv4_dns}",
        "ignore-auto-dns=true",
        "may-fail=false",
        "",
        "[ipv6]",
        f"method={data['ipv6_method']}",
        "",
        "[proxy]",
        "",
    ]
    return "\n".join(lines) + "\n"


@deploy("Static network config")
def static_network() -> None:
    if not host.data.get("static_network_enabled", False):
        return

    cfg = host.data.get("static_network") or {}
    data = dict(cfg)

    keyfile_path = f"{KEYFILE_DIR}/{data['connection_id']}.nmconnection"

    written = files.put(
        name=f"Render {keyfile_path}",
        src=StringIO(_render_nmconnection(data)),
        dest=keyfile_path,
        user="root",
        group="root",
        mode="0600",
        _sudo=True,
    )

    server.shell(
        name="nmcli con reload + bring up connection on keyfile change",
        commands=[
            f"nmcli con reload && nmcli con up '{data['connection_id']}'",
        ],
        _if=written.did_change,
        _sudo=True,
    )
