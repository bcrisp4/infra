"""Deploy user-defined podman networks as systemd quadlets.

Renders /etc/containers/systemd/<name>.network from host data, then reloads so
the quadlet generator creates the corresponding podman network at daemon-reload.

The `monitoring` network is the shared bridge for the metrics stack: Prometheus
and Grafana attach to it and resolve each other by ContainerName via
aardvark-dns (e.g. Grafana's datasource targets http://prometheus:9090). The
`rendering` network is a dedicated bridge for Grafana <-> image renderer only, so
the renderer is reachable by Grafana but not by Prometheus (Grafana joins both;
see tasks/grafana.py and tasks/image_renderer.py). Only user-defined networks get
aardvark name resolution; the podman default bridge does not, which is why these
explicit units exist.

A `.container` unit that sets `Network=<name>.network` gets
`Wants=`/`After=<name>-network.service` auto-injected by the generator, so the
network always comes up before the containers that need it; no manual ordering is
required here.

node-exporter is deliberately NOT on any of these: it runs `Network=host` for
real host metrics and is scraped via host.containers.internal instead.

Each network is gated independently on its `<name>_network_enabled` host/group
data so other hosts no-op.
"""

from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_DIR = "/etc/containers/systemd"


def _unit_path(name: str) -> str:
    """Quadlet unit path for the network named `name`."""
    return f"{UNIT_DIR}/{name}.network"


def _render_network(name: str) -> str:
    """Render the systemd quadlet .network unit for the network named `name`.

    NetworkName pins the podman network name explicitly; without it the
    generator would derive `systemd-<unit>`. Pinning keeps the name stable and
    matches what `.container` units reference via `Network=<name>.network`.
    """
    lines = [
        "# Rendered by pyinfra tasks/podman_network.py. Do not edit by hand.",
        "[Network]",
        f"NetworkName={name}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


# Each entry: (enable-flag data key, network-name data key). Add a network by
# defining both keys in group_data and appending here.
_NETWORKS = (
    ("monitoring_network_enabled", "monitoring_network_name"),
    ("rendering_network_enabled", "rendering_network_name"),
)


@deploy("Configure podman networks")
def podman_networks() -> None:
    units = []
    for enabled_key, name_key in _NETWORKS:
        if not host.data.get(enabled_key, False):
            continue
        name = host.data.get(name_key)

        units.append(
            files.put(
                name=f"Render {_unit_path(name)}",
                src=StringIO(_render_network(name)),
                dest=_unit_path(name),
                user="root",
                group="root",
                mode="0644",
                _sudo=True,
            )
        )

    # A daemon-reload runs the quadlet generator, which creates the podman
    # networks. A network has no long-running service to "start"; the reload is
    # the action. Containers referencing one pull it up via the generated
    # <name>-network.service dependency. did_change() is deferred via the _if
    # callable: it can only be read after the execute phase.
    systemd.daemon_reload(
        name="Reload systemd to create the podman networks",
        _if=lambda: any(u.did_change() for u in units),
        _sudo=True,
    )
