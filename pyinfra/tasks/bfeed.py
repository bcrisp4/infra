"""Deploy bfeed (self-hosted RSS/Atom/JSON feed reader) as a rootful podman quadlet.

Renders /etc/containers/systemd/bfeed.container from host data, then ensures
bfeed.service is running. The quadlet generator converts the .container file
into a runtime systemd unit at daemon-reload.

Networking: bfeed joins no user-defined podman network -- it talks to nothing
else on the host, but it DOES poll feeds over the public internet, so it stays
on the default podman bridge (outbound NAT). The host port is published on the
loopback only (127.0.0.1); external access is solely through the Tailscale
service svc:bfeed (HTTPS at bfeed.marlin-tet.ts.net, see
tasks/tailscale_service.py). No LAN or raw-Tailscale-IP exposure.

State: bfeed's sqlite DB (BFEED_DATABASE_PATH defaults to /data/bfeed.db) lives
under /var/lib/bfeed, a plain dir on the rootfs bind-mounted at /data. The image
(gcr.io/distroless/static:nonroot) runs as uid:gid 65532:65532, so the data dir
is chowned to match before the container starts.

BFEED_BASE_URL is mandatory (bfeed exits at startup without it); it is the public
URL the app builds absolute links + cookies from, so it must be the MagicDNS name
behind the Tailscale TLS proxy, not the loopback bind.

Reload semantics: any change to the quadlet triggers a restart. There is no
separate config file or reload signal; all config is via environment.

Gated on `bfeed_enabled` host/group data so non-bfeed hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/bfeed.container"

# State dir. A plain dir on the rootfs (created + chowned below before first
# start), bind-mounted to /data inside the container (where BFEED_DATABASE_PATH
# points). The distroless image runs as uid:gid 65532:65532, so the host dir is
# chowned to match.
DATA_DIR = "/var/lib/bfeed"
DATA_UID = "65532"
DATA_GID = "65532"
CONTAINER_DATA_DIR = "/data"

# bfeed listens on this port inside the container; the host mapping is
# bfeed_host_port (standard 8080).
CONTAINER_PORT = 8080


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for bfeed from host data."""
    image = f"{data['bfeed_image']}:{data['bfeed_image_tag']}"
    host_port = data["bfeed_host_port"]
    base_url = data["bfeed_base_url"]
    lines = [
        "# Rendered by pyinfra tasks/bfeed.py. Do not edit by hand.",
        "[Unit]",
        "Description=bfeed RSS/Atom feed reader",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=bfeed",
        # No Network= line: bfeed stays on the default podman bridge, which gives
        # the outbound NAT it needs to poll feeds. It reaches no other container,
        # so it joins none of the user-defined networks.
        #
        # Loopback-only: bfeed is reached solely via the Tailscale service (HTTPS
        # at bfeed.marlin-tet.ts.net), whose proxy on the host hits 127.0.0.1. No
        # LAN or raw-Tailscale-IP exposure. See tasks/tailscale_service.py.
        f"PublishPort=127.0.0.1:{host_port}:{CONTAINER_PORT}/tcp",
        f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}",
        # Mandatory: bfeed refuses to start without BFEED_BASE_URL. Behind the
        # Tailscale serve TLS proxy, this must be the public MagicDNS URL so
        # absolute links + cookies resolve, not the loopback bind.
        f"Environment=BFEED_BASE_URL={base_url}",
        # Structured JSON logs to the journal (the image default, set explicitly).
        "Environment=BFEED_LOG_FORMAT=json",
        "Environment=BFEED_LOG_LEVEL=info",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['bfeed_memory_max']}",
        f"MemoryHigh={data['bfeed_memory_high']}",
        f"CPUQuota={data['bfeed_cpu_quota']}",
        f"TasksMax={data['bfeed_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "bfeed_image",
    "bfeed_image_tag",
    "bfeed_host_port",
    "bfeed_base_url",
    "bfeed_memory_max",
    "bfeed_memory_high",
    "bfeed_cpu_quota",
    "bfeed_tasks_max",
)


@deploy("Deploy bfeed")
def bfeed() -> None:
    if not host.data.get("bfeed_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    # Create the rootfs data dir (if absent) and chown to the container uid
    # before the container starts, so bfeed can write its sqlite DB. Idempotent:
    # a dir pre-populated by a data restore is left intact.
    files.directory(
        name="Ensure /var/lib/bfeed owned by container uid",
        path=DATA_DIR,
        present=True,
        user=DATA_UID,
        group=DATA_GID,
        mode="0700",
        _sudo=True,
    )

    unit = files.put(
        name="Render /etc/containers/systemd/bfeed.container",
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
        name="Restart bfeed.service on quadlet change",
        service="bfeed.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure bfeed.service running",
        service="bfeed.service",
        running=True,
        _sudo=True,
    )
