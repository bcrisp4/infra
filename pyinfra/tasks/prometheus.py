"""Deploy Prometheus as a rootful podman quadlet.

Renders /etc/prometheus/prometheus.yml + /etc/containers/systemd/prometheus.container
from host data, then ensures prometheus.service is running. The quadlet
generator converts the .container file into a runtime systemd unit at
daemon-reload.

Reload semantics:
- Quadlet unit changed   -> daemon-reload + restart (full container recreate).
- Config-only changed    -> SIGHUP via ExecReload (Prometheus reloads config +
                            rules, no container restart).

TSDB persists on a dedicated LV mounted at /var/lib/prometheus (provisioned by
tasks/storage.py). The distroless image runs as uid 65532 (the distroless
`nonroot` user, NOT `nobody` 65534), so the data dir is chowned to match before
the container starts.

Gated on `prometheus_enabled` host/group data so non-prometheus hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

CONFIG_DIR = "/etc/prometheus"
CONFIG_PATH = f"{CONFIG_DIR}/prometheus.yml"
UNIT_PATH = "/etc/containers/systemd/prometheus.container"

# TSDB data dir. Bind-mounted from a dedicated LV (tasks/storage.py mounts the
# LV here). The distroless prometheus image runs as uid:gid 65532:65532, so the
# host dir is chowned to match before first start.
DATA_DIR = "/var/lib/prometheus"
CONTAINER_DATA_DIR = "/prometheus"
DATA_UID = "65532"
DATA_GID = "65532"

# Prometheus listens on this port inside the container; the host mapping is
# prometheus_host_port (standard 9090).
CONTAINER_PORT = 9090


def _render_config(data: Mapping) -> str:
    """Render prometheus.yml from host data.

    Hand-rolled YAML (no PyYAML) because the shape is fixed and unit-tested.
    The bns and node-exporter scrape targets read their host ports from data so
    each port has a single source of truth.

    node-exporter is scraped over host.containers.internal (the only route from
    the Prometheus container to the host port), but that address is meaningless
    as an `instance` label, so we pin instance to the node's short hostname
    (data["node_name"]).
    """
    bns_target = f"host.containers.internal:{data['bns_host_port_admin']}"
    nodeexporter_target = f"host.containers.internal:{data['nodeexporter_host_port']}"
    node_name = data["node_name"]
    lines = [
        "# Rendered by pyinfra tasks/prometheus.py. Do not edit by hand.",
        "global:",
        f"  scrape_interval: {data['prometheus_scrape_interval']}",
        f"  evaluation_interval: {data['prometheus_scrape_interval']}",
        "",
        "scrape_configs:",
        "  - job_name: prometheus",
        "    static_configs:",
        f"      - targets: ['localhost:{CONTAINER_PORT}']",
        "",
        "  - job_name: bns",
        "    static_configs:",
        f"      - targets: ['{bns_target}']",
        "",
        "  - job_name: node-exporter",
        "    static_configs:",
        f"      - targets: ['{nodeexporter_target}']",
        f"        labels: {{instance: '{node_name}'}}",
    ]
    return "\n".join(lines) + "\n"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for Prometheus from host data."""
    image = f"{data['prometheus_image']}:{data['prometheus_image_tag']}"
    host_port = data["prometheus_host_port"]
    exec_args = " ".join(
        [
            f"--config.file={CONFIG_PATH}",
            f"--storage.tsdb.path={CONTAINER_DATA_DIR}",
            f"--storage.tsdb.retention.time={data['prometheus_retention_time']}",
            f"--storage.tsdb.retention.size={data['prometheus_retention_size']}",
            f"--web.listen-address=0.0.0.0:{CONTAINER_PORT}",
        ]
    )
    lines = [
        "# Rendered by pyinfra tasks/prometheus.py. Do not edit by hand.",
        "[Unit]",
        "Description=Prometheus monitoring server",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=prometheus",
        # Loopback-only: Prometheus is reached solely via the Tailscale service
        # (HTTPS at prometheus.marlin-tet.ts.net), whose proxy on the host hits
        # 127.0.0.1. No LAN or raw-Tailscale-IP exposure. See
        # tasks/tailscale_service.py.
        f"PublishPort=127.0.0.1:{host_port}:{CONTAINER_PORT}/tcp",
        f"Volume={CONFIG_PATH}:{CONFIG_PATH}:ro",
        f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}",
        # Exec= overrides the image CMD only; entrypoint /bin/prometheus stays,
        # so these flags are appended to it.
        f"Exec={exec_args}",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        "ExecReload=/usr/bin/podman kill --signal HUP %N",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['prometheus_memory_max']}",
        f"MemoryHigh={data['prometheus_memory_high']}",
        f"CPUQuota={data['prometheus_cpu_quota']}",
        f"TasksMax={data['prometheus_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "prometheus_image",
    "prometheus_image_tag",
    "prometheus_host_port",
    "prometheus_scrape_interval",
    "prometheus_retention_time",
    "prometheus_retention_size",
    "prometheus_memory_max",
    "prometheus_memory_high",
    "prometheus_cpu_quota",
    "prometheus_tasks_max",
    "bns_host_port_admin",
    "nodeexporter_host_port",
)


@deploy("Deploy Prometheus")
def prometheus() -> None:
    if not host.data.get("prometheus_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderers stay test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}
    # Short hostname for the node-exporter `instance` label (the inventory name
    # is the Tailscale FQDN; take the first label).
    data["node_name"] = host.name.split(".")[0]

    # Set ownership on the mounted LV root before the container starts. storage()
    # runs earlier in deploy.py and mounts the LV here (0700 root); chown to the
    # container uid so the distroless prometheus process can write the TSDB.
    files.directory(
        name="Ensure /var/lib/prometheus owned by container uid",
        path=DATA_DIR,
        present=True,
        user=DATA_UID,
        group=DATA_GID,
        mode="0700",
        _sudo=True,
    )

    files.directory(
        name="Ensure /etc/prometheus config dir",
        path=CONFIG_DIR,
        present=True,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
    )

    config = files.put(
        name="Render /etc/prometheus/prometheus.yml",
        src=StringIO(_render_config(data)),
        dest=CONFIG_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    unit = files.put(
        name="Render /etc/containers/systemd/prometheus.container",
        src=StringIO(_render_quadlet(data)),
        dest=UNIT_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # Boot-time start is handled by `[Install] WantedBy=multi-user.target` in the
    # quadlet file. systemctl enable does not apply to generator-produced units,
    # so we only manage running state here.

    systemd.service(
        name="Restart prometheus.service on quadlet change",
        service="prometheus.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="SIGHUP prometheus.service on config-only change",
        service="prometheus.service",
        reloaded=True,
        _if=lambda: config.did_change() and not unit.did_change(),
        _sudo=True,
    )

    systemd.service(
        name="Ensure prometheus.service running",
        service="prometheus.service",
        running=True,
        _sudo=True,
    )
