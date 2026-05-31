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
    The bns scrape target reads bns_host_port_admin so the port has a single
    source of truth.
    """
    bns_target = f"host.containers.internal:{data['bns_host_port_admin']}"
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
    ]
    return "\n".join(lines) + "\n"
