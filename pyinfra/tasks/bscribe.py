"""Deploy bscribe (self-hosted document -> text/markdown conversion service) as a
rootful podman quadlet.

Renders /etc/containers/systemd/bscribe.container from host data, then ensures
bscribe.service is running. The quadlet generator converts the .container file
into a runtime systemd unit at daemon-reload.

Networking: bscribe joins the `monitoring` podman network so Prometheus can
scrape its metrics listener by ContainerName (bscribe:<bscribe_metrics_port>)
via aardvark-dns, like Grafana/bfeed. A user-defined network still provides
outbound NAT. The app host port is published on the loopback only (127.0.0.1);
external access is solely through the Tailscale service svc:bscribe (HTTPS at
bscribe.marlin-tet.ts.net, see tasks/tailscale_service.py). No LAN or
raw-Tailscale-IP exposure. The metrics listener (BSCRIBE_METRICS_PORT) is NOT
published to the host, so it is reachable only by Prometheus over the monitoring
bridge.

Hardening: the image ships a read-only-rootfs contract (docs/deployment.md).
The quadlet drops all capabilities (DropCapability=all), forbids privilege
escalation (NoNewPrivileges=true) and mounts the rootfs read-only
(ReadOnly=true). A writable tmpfs at /tmp is MANDATORY: all conversion scratch
(LibreOffice profiles, ImageMagick scratch, liteparse temp PDFs) lives under
/tmp, so every conversion fails on a read-only root without it.

State: bscribe's sqlite DB (BSCRIBE_DB_PATH=/data/bscribe.db, set in the image)
holds bearer-token hashes + async jobs. It lives in the `bscribe-data` named
volume. The image runs as a non-root `useradd --system` user whose numeric uid
is not fixed, so a host-dir chown (as bfeed does) is not possible; instead
podman auto-creates the named volume on first run and copy-up seeds it from the
image's /data (already chowned to the service user at build time), so the
process can write. Bearer tokens are provisioned manually post-deploy via
`podman exec bscribe bscribe token add <label>` (never over HTTP, not in git).

Reload semantics: any change to the quadlet triggers a restart. There is no
separate config file or reload signal; all config is via environment.

Gated on `bscribe_enabled` host/group data so non-bscribe hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/bscribe.container"

# Named volume for the SQLite DB (bind-mounted to /data inside the container,
# where BSCRIBE_DB_PATH points). Podman auto-creates it on first run and
# copy-up seeds ownership from the image's /data, so no host chown is needed
# (the image's service user is a nondeterministic system uid).
DATA_VOLUME = "bscribe-data"
CONTAINER_DATA_DIR = "/data"

# bscribe's API listens on this port inside the container; the host mapping is
# bscribe_host_port (standard 8000). The image sets BSCRIBE_HOST=0.0.0.0.
CONTAINER_PORT = 8000


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for bscribe from host data."""
    image = f"{data['bscribe_image']}:{data['bscribe_image_tag']}"
    host_port = data["bscribe_host_port"]
    metrics_port = data["bscribe_metrics_port"]
    worker_count = data["bscribe_worker_count"]
    lines = [
        "# Rendered by pyinfra tasks/bscribe.py. Do not edit by hand.",
        "[Unit]",
        "Description=bscribe document conversion service",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=bscribe",
        # Shared bridge with Prometheus (tasks/podman_network.py): Prometheus
        # resolves this container as `bscribe` via aardvark-dns and scrapes its
        # metrics port. A user-defined network still provides outbound NAT.
        "Network=monitoring.network",
        # Loopback-only app port: bscribe's API is reached solely via the
        # Tailscale service (HTTPS at bscribe.marlin-tet.ts.net), whose proxy on
        # the host hits 127.0.0.1. No LAN or raw-Tailscale-IP exposure. The
        # metrics port below is NOT published, so it stays reachable only over
        # the monitoring bridge. See tasks/tailscale_service.py.
        f"PublishPort=127.0.0.1:{host_port}:{CONTAINER_PORT}/tcp",
        # Named volume for the SQLite DB. Podman auto-creates on first run and
        # copy-up seeds it from the image's /data (already chowned to the
        # service user at build time), so bscribe can write.
        f"Volume={DATA_VOLUME}:{CONTAINER_DATA_DIR}",
        # Writable tmpfs is MANDATORY on the read-only rootfs: all conversion
        # scratch (LibreOffice/ImageMagick/liteparse temp files) lives under
        # /tmp, so every job fails without it.
        "Tmpfs=/tmp",
        # Hardened run contract (docs/deployment.md): read-only rootfs, no
        # privilege escalation, drop every capability.
        "ReadOnly=true",
        "NoNewPrivileges=true",
        "DropCapability=all",
        # Separate Prometheus metrics listener (binds all container interfaces;
        # unpublished, so only Prometheus on the monitoring bridge reaches it).
        f"Environment=BSCRIBE_METRICS_PORT={metrics_port}",
        # Parse worker processes = max parse concurrency.
        f"Environment=BSCRIBE_WORKER_COUNT={worker_count}",
        "Environment=BSCRIBE_LOG_LEVEL=INFO",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['bscribe_memory_max']}",
        f"MemoryHigh={data['bscribe_memory_high']}",
        f"CPUQuota={data['bscribe_cpu_quota']}",
        f"TasksMax={data['bscribe_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "bscribe_image",
    "bscribe_image_tag",
    "bscribe_host_port",
    "bscribe_metrics_port",
    "bscribe_worker_count",
    "bscribe_memory_max",
    "bscribe_memory_high",
    "bscribe_cpu_quota",
    "bscribe_tasks_max",
)


@deploy("Deploy bscribe")
def bscribe() -> None:
    if not host.data.get("bscribe_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    # No host data dir to create/chown: the SQLite DB lives in the bscribe-data
    # named volume, which podman auto-creates and seeds from the image on first
    # run (the image's service user is a nondeterministic system uid, so a
    # host-side chown is not possible).

    unit = files.put(
        name="Render /etc/containers/systemd/bscribe.container",
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
        name="Restart bscribe.service on quadlet change",
        service="bscribe.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure bscribe.service running",
        service="bscribe.service",
        running=True,
        _sudo=True,
    )
