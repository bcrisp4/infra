"""Deploy prometheus-podman-exporter as a rootful podman quadlet.

Renders /etc/containers/systemd/podman-exporter.container from host data, then
ensures podman-exporter.service is running. The quadlet generator converts the
.container file into a runtime systemd unit at daemon-reload.

prometheus-podman-exporter (quay.io/navidys/prometheus-podman-exporter) exports
podman container/pod/image/system metrics for Prometheus. It talks to podman
over the rootful API unix socket (/run/podman/podman.sock), NOT over the
network, so it does NOT need Network=host: the socket is bind-mounted in and
CONTAINER_HOST points at it. host networking only applies to the docs' TCP
socket variant.

Networking: the exporter joins the shared `monitoring` podman network (see
tasks/podman_network.py) and publishes NO host port. Prometheus is on the same
network and scrapes it by ContainerName via aardvark-dns
(http://podman-exporter:9882), exactly as it reaches Grafana. No host, LAN or
Tailscale exposure.

Socket: rootful access to /run/podman/podman.sock requires the podman.socket
systemd unit to be running, and the container to run as root (User=root, the
docs' `-u root`). We enable podman.socket here so the dependency is explicit.

Metrics: --collector.enhance-metrics is set so per-container CPU/memory/network
usage is exported, not just container/pod state and counts.

State: the exporter is stateless. Like node-exporter / image-renderer there is
no _render_config, data dir or uid chown, and no SIGHUP reload path; a quadlet
change just recreates the container.

SELinux note: the upstream docs pass `--security-opt label=type:container_runtime_t`
to let the container reach the socket under SELinux. Debian 13 uses AppArmor,
not SELinux, so that option is omitted. If the socket mount is denied on the
host (check `journalctl -u podman-exporter`), add
`PodmanArgs=--security-opt=label=disable` -- do NOT add the SELinux type label.

Gated on `podman_exporter_enabled` host/group data so other hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/podman-exporter.container"

# Rootful podman API socket. Bind-mounted into the container; CONTAINER_HOST
# points at the same path. Requires podman.socket to be running (enabled below).
SOCKET_PATH = "/run/podman/podman.sock"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for the podman exporter."""
    image = f"{data['podman_exporter_image']}:{data['podman_exporter_image_tag']}"
    exec_args = " ".join(
        [
            # Enhance every metric with per-container CPU/memory/network usage,
            # not just state/count series.
            "--collector.enhance-metrics",
            f"--web.listen-address=:{data['podman_exporter_port']}",
        ]
    )
    lines = [
        "# Rendered by pyinfra tasks/podman_exporter.py. Do not edit by hand.",
        "[Unit]",
        "Description=Prometheus podman exporter",
        "Wants=network-online.target",
        "After=network-online.target",
        # The exporter reaches podman over its API socket, so the socket unit
        # must be up first.
        "Requires=podman.socket",
        "After=podman.socket",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=podman-exporter",
        # Shared bridge with Prometheus (tasks/podman_network.py): Prometheus
        # resolves this container as `podman-exporter` via aardvark-dns. NO
        # PublishPort: reachable solely by Prometheus over this network.
        "Network=monitoring.network",
        # Rootful socket access needs the container to run as root (docs' -u root).
        "User=root",
        # Point the exporter at the rootful podman API socket and mount it in.
        f"Environment=CONTAINER_HOST=unix://{SOCKET_PATH}",
        f"Volume={SOCKET_PATH}:{SOCKET_PATH}",
        # Exec= overrides the image CMD only; the entrypoint (the exporter
        # binary) stays, so these flags are appended to it.
        f"Exec={exec_args}",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['podman_exporter_memory_max']}",
        f"MemoryHigh={data['podman_exporter_memory_high']}",
        f"CPUQuota={data['podman_exporter_cpu_quota']}",
        f"TasksMax={data['podman_exporter_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "podman_exporter_image",
    "podman_exporter_image_tag",
    "podman_exporter_port",
    "podman_exporter_memory_max",
    "podman_exporter_memory_high",
    "podman_exporter_cpu_quota",
    "podman_exporter_tasks_max",
)


@deploy("Deploy podman exporter")
def podman_exporter() -> None:
    if not host.data.get("podman_exporter_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    # The exporter reads the rootful podman API socket, which only exists while
    # podman.socket is active. It is a real installed unit (not a generated
    # quadlet), so enabling at boot is valid here.
    systemd.service(
        name="Ensure podman.socket running",
        service="podman.socket",
        running=True,
        enabled=True,
        _sudo=True,
    )

    unit = files.put(
        name="Render /etc/containers/systemd/podman-exporter.container",
        src=StringIO(_render_quadlet(data)),
        dest=UNIT_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # Boot-time start is handled by `[Install] WantedBy=multi-user.target` in the
    # quadlet file. systemctl enable does not apply to generator-produced units,
    # so we only manage running state here. The exporter is stateless, so a
    # quadlet change just recreates the container (no config-reload path).

    systemd.service(
        name="Restart podman-exporter.service on quadlet change",
        service="podman-exporter.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure podman-exporter.service running",
        service="podman-exporter.service",
        running=True,
        _sudo=True,
    )
