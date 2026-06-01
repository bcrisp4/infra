"""Deploy Grafana as a rootful podman quadlet.

Renders the Prometheus datasource provisioning file +
/etc/containers/systemd/grafana.container from host data, then ensures
grafana.service is running. The quadlet generator converts the .container file
into a runtime systemd unit at daemon-reload.

Networking: Grafana joins the shared `monitoring` podman network (see
tasks/podman_network.py) and reaches the colocated Prometheus by ContainerName
(http://prometheus:9090) via aardvark-dns. The host port is published on the
loopback only (127.0.0.1); external access is solely through the Tailscale
service svc:grafana (HTTPS at grafana.marlin-tet.ts.net, see
tasks/tailscale_service.py). No LAN or raw-Tailscale-IP exposure.

State: Grafana's sqlite DB, dashboards and plugins live under /var/lib/grafana,
bind-mounted from a dedicated LV (provisioned by tasks/storage.py). The image
runs as uid:gid 472:472, so the data dir is chowned to match before the
container starts. sqlite WAL journal mode is enabled (GF_DATABASE_WAL) for
better concurrency/durability.

Reload semantics: any change to the quadlet OR the datasource file triggers a
restart. Grafana loads provisioning at startup, so a restart applies datasource
changes; there is no separate config-reload signal as with Prometheus.

Gated on `grafana_enabled` host/group data so non-grafana hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/grafana.container"

# Provisioning datasource file. Grafana reads /etc/grafana/provisioning by
# default; the datasources subdir is loaded at startup. The rendered file is
# bind-mounted read-only at the same path inside the container.
PROVISIONING_DIR = "/etc/grafana/provisioning/datasources"
DATASOURCE_PATH = f"{PROVISIONING_DIR}/prometheus.yaml"

# State dir. Bind-mounted from a dedicated LV (tasks/storage.py mounts the LV
# here). The grafana image runs as uid:gid 472:472, so the host dir is chowned
# to match before first start.
DATA_DIR = "/var/lib/grafana"
DATA_UID = "472"
DATA_GID = "472"

# Grafana listens on this port inside the container; the host mapping is
# grafana_host_port (standard 3000).
CONTAINER_PORT = 3000

# Prometheus is reached by its ContainerName on the shared monitoring network.
PROMETHEUS_CONTAINER_NAME = "prometheus"


def _render_datasource(data: Mapping) -> str:
    """Render the Prometheus datasource provisioning YAML from host data.

    Hand-rolled YAML (no PyYAML) because the shape is fixed and unit-tested. The
    url targets the Prometheus ContainerName over the monitoring network so the
    backend port is the single source of truth shared with tasks/prometheus.py.
    """
    url = f"http://{PROMETHEUS_CONTAINER_NAME}:{data['prometheus_host_port']}"
    lines = [
        "# Rendered by pyinfra tasks/grafana.py. Do not edit by hand.",
        "apiVersion: 1",
        "datasources:",
        "  - name: Prometheus",
        "    type: prometheus",
        "    access: proxy",
        f"    url: {url}",
        "    isDefault: true",
    ]
    return "\n".join(lines) + "\n"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for Grafana from host data."""
    image = f"{data['grafana_image']}:{data['grafana_image_tag']}"
    host_port = data["grafana_host_port"]
    root_url = data["grafana_root_url"]
    # Domain Grafana uses to build absolute links; derive from the root URL host.
    domain = root_url.split("://", 1)[-1].split("/", 1)[0]
    lines = [
        "# Rendered by pyinfra tasks/grafana.py. Do not edit by hand.",
        "[Unit]",
        "Description=Grafana visualization + dashboards",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=grafana",
        # Shared bridge with Prometheus; resolves `prometheus` via aardvark-dns.
        "Network=monitoring.network",
        # Loopback-only: Grafana is reached solely via the Tailscale service
        # (HTTPS at grafana.marlin-tet.ts.net), whose proxy on the host hits
        # 127.0.0.1. No LAN or raw-Tailscale-IP exposure. See
        # tasks/tailscale_service.py.
        f"PublishPort=127.0.0.1:{host_port}:{CONTAINER_PORT}/tcp",
        f"Volume={DATA_DIR}:{DATA_DIR}",
        f"Volume={DATASOURCE_PATH}:{DATASOURCE_PATH}:ro",
        # Behind the Tailscale serve TLS proxy: tell Grafana its public URL so
        # redirects and absolute links resolve to the MagicDNS name.
        f"Environment=GF_SERVER_ROOT_URL={root_url}",
        f"Environment=GF_SERVER_DOMAIN={domain}",
        # sqlite WAL journal mode: better read/write concurrency + durability.
        "Environment=GF_DATABASE_WAL=true",
        # Homelab: no telemetry, no update nag.
        "Environment=GF_ANALYTICS_REPORTING_ENABLED=false",
        "Environment=GF_ANALYTICS_CHECK_FOR_UPDATES=false",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['grafana_memory_max']}",
        f"MemoryHigh={data['grafana_memory_high']}",
        f"CPUQuota={data['grafana_cpu_quota']}",
        f"TasksMax={data['grafana_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "grafana_image",
    "grafana_image_tag",
    "grafana_host_port",
    "grafana_root_url",
    "grafana_memory_max",
    "grafana_memory_high",
    "grafana_cpu_quota",
    "grafana_tasks_max",
    "prometheus_host_port",
)


@deploy("Deploy Grafana")
def grafana() -> None:
    if not host.data.get("grafana_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderers stay test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    # Set ownership on the mounted LV root before the container starts. storage()
    # runs earlier in deploy.py and mounts the LV here (0700 root); chown to the
    # container uid so the grafana process can write its sqlite DB + plugins.
    files.directory(
        name="Ensure /var/lib/grafana owned by container uid",
        path=DATA_DIR,
        present=True,
        user=DATA_UID,
        group=DATA_GID,
        mode="0700",
        _sudo=True,
    )

    files.directory(
        name="Ensure grafana datasource provisioning dir",
        path=PROVISIONING_DIR,
        present=True,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
    )

    datasource = files.put(
        name=f"Render {DATASOURCE_PATH}",
        src=StringIO(_render_datasource(data)),
        dest=DATASOURCE_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    unit = files.put(
        name="Render /etc/containers/systemd/grafana.container",
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
        name="Restart grafana.service on quadlet or datasource change",
        service="grafana.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=lambda: unit.did_change() or datasource.did_change(),
        _sudo=True,
    )

    systemd.service(
        name="Ensure grafana.service running",
        service="grafana.service",
        running=True,
        _sudo=True,
    )
