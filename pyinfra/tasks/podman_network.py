"""Deploy user-defined podman networks as systemd quadlets.

Renders /etc/containers/systemd/<name>.network from host data, then reloads so
the quadlet generator creates the corresponding podman network at daemon-reload.

The `monitoring` network is the shared bridge for the metrics stack: Prometheus
and Grafana attach to it and resolve each other by ContainerName via
aardvark-dns (e.g. Grafana's datasource targets http://prometheus:9090). Only
user-defined networks get aardvark name resolution; the podman default bridge
does not, which is why this explicit unit exists.

A `.container` unit that sets `Network=monitoring.network` gets
`Wants=`/`After=monitoring-network.service` auto-injected by the generator, so
the network always comes up before the containers that need it; no manual
ordering is required here.

node-exporter is deliberately NOT on this network: it runs `Network=host` for
real host metrics and is scraped via host.containers.internal instead.

Gated on `monitoring_network_enabled` host/group data so other hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_DIR = "/etc/containers/systemd"


def _unit_path(name: str) -> str:
    """Quadlet unit path for the network named `name`."""
    return f"{UNIT_DIR}/{name}.network"


def _render_network(data: Mapping) -> str:
    """Render the systemd quadlet .network unit from host data.

    NetworkName pins the podman network name explicitly; without it the
    generator would derive `systemd-<unit>`. Pinning keeps the name stable and
    matches what `.container` units reference via `Network=<name>.network`.
    """
    lines = [
        "# Rendered by pyinfra tasks/podman_network.py. Do not edit by hand.",
        "[Network]",
        f"NetworkName={data['monitoring_network_name']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


@deploy("Configure podman networks")
def podman_networks() -> None:
    if not host.data.get("monitoring_network_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    name = host.data.get("monitoring_network_name")
    data = {"monitoring_network_name": name}

    unit = files.put(
        name=f"Render {_unit_path(name)}",
        src=StringIO(_render_network(data)),
        dest=_unit_path(name),
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # A daemon-reload runs the quadlet generator, which creates the podman
    # network. The network has no long-running service to "start"; the reload is
    # the action. Containers referencing it pull it up via the generated
    # <name>-network.service dependency.
    systemd.daemon_reload(
        name="Reload systemd to create the podman network",
        _if=unit.did_change,
        _sudo=True,
    )
