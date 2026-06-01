"""Deploy Prometheus node-exporter as a rootful podman quadlet.

Renders /etc/containers/systemd/node-exporter.container from host data, then
ensures node-exporter.service is running. The quadlet generator converts the
.container file into a runtime systemd unit at daemon-reload.

node-exporter is stateless: no config file, no persistent volume. So unlike
bns/prometheus there is only a quadlet renderer (no _render_config) and no
SIGHUP reload path -- a quadlet change just recreates the container.

Container caveat: node-exporter measures the *host*, not the container. To do
that it must share the host namespaces and read the host filesystem:
- Network=host  -> real interface/network metrics (not the container netns).
- PidMode=host  -> host PID namespace.
- Volume=/:/host:ro,rslave + --path.rootfs=/host -> host rootfs, read-only;
  rslave stops submount propagation leaking back to the host. The filesystem,
  hwmon and thermal_zone collectors resolve their paths under /host.
The filesystem collector excludes are widened to drop the /host-prefixed and
container-internal mounts so disk series are not duplicated/garbage.

Because Network=host shares the host net namespace, the listen address cannot be
restricted with PublishPort the way Prometheus is; the bind is controlled only
by --web.listen-address. We bind :9100 (0.0.0.0), matching the trusted-LAN
exposure of the bns admin port. Prometheus scrapes host.containers.internal:9100.

Gated on `nodeexporter_enabled` host/group data so non-exporter hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/node-exporter.container"

# Host rootfs is bind-mounted here read-only; --path.rootfs points the
# filesystem/hwmon/thermal collectors at this prefix.
HOST_ROOTFS_MOUNT = "/host"

# node-exporter's default listen port. Host mapping is nodeexporter_host_port.
CONTAINER_PORT = 9100

# Filesystem collector excludes, widened from upstream defaults to also drop the
# /host-prefixed view and podman's container storage so disk series aren't
# duplicated under --path.rootfs.
FS_MOUNT_POINTS_EXCLUDE = (
    "^/(host/)?(dev|proc|sys|run/credentials/.+|var/lib/containers/.+|var/lib/docker/.+)($|/)"
)
FS_TYPES_EXCLUDE = (
    "^(autofs|binfmt_misc|bpf|cgroup2?|configfs|debugfs|devpts|devtmpfs|fusectl|"
    "hugetlbfs|iso9660|mqueue|nsfs|overlay|proc|procfs|pstore|rpc_pipefs|"
    "securityfs|selinuxfs|squashfs|sysfs|tracefs)$"
)


def _systemd_escape_exec(value: str) -> str:
    """Escape a value for a systemd Exec*= line.

    systemd expands environment variables in Exec lines, so a literal `$` must be
    written `$$` (else the regex anchors `$`/`$|` would be eaten as bogus variable
    expansions). Our exclude regexes are the only args containing `$`.
    """
    return value.replace("$", "$$")


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for node-exporter from host data."""
    image = f"{data['nodeexporter_image']}:{data['nodeexporter_image_tag']}"
    host_port = data["nodeexporter_host_port"]
    exec_args = " ".join(
        [
            f"--path.rootfs={HOST_ROOTFS_MOUNT}",
            f"--web.listen-address=:{host_port}",
            "--collector.filesystem.mount-points-exclude="
            f"{_systemd_escape_exec(FS_MOUNT_POINTS_EXCLUDE)}",
            f"--collector.filesystem.fs-types-exclude={_systemd_escape_exec(FS_TYPES_EXCLUDE)}",
        ]
    )
    lines = [
        "# Rendered by pyinfra tasks/nodeexporter.py. Do not edit by hand.",
        "[Unit]",
        "Description=Prometheus node-exporter - host metrics",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=node-exporter",
        # Host namespaces + rootfs so metrics describe the Pi, not the container.
        # Network has a dedicated quadlet key; PID namespace does not (podman
        # 5.4 quadlet has no PidMode key), so --pid=host goes via PodmanArgs.
        "Network=host",
        "PodmanArgs=--pid=host",
        f"Volume=/:{HOST_ROOTFS_MOUNT}:ro,rslave",
        # Exec= overrides the image CMD only; the /bin/node_exporter entrypoint
        # stays, so these flags are appended to it.
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
        f"MemoryMax={data['nodeexporter_memory_max']}",
        f"MemoryHigh={data['nodeexporter_memory_high']}",
        f"CPUQuota={data['nodeexporter_cpu_quota']}",
        f"TasksMax={data['nodeexporter_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "nodeexporter_image",
    "nodeexporter_image_tag",
    "nodeexporter_host_port",
    "nodeexporter_memory_max",
    "nodeexporter_memory_high",
    "nodeexporter_cpu_quota",
    "nodeexporter_tasks_max",
)


@deploy("Deploy node-exporter")
def node_exporter() -> None:
    if not host.data.get("nodeexporter_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    unit = files.put(
        name="Render /etc/containers/systemd/node-exporter.container",
        src=StringIO(_render_quadlet(data)),
        dest=UNIT_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # Boot-time start is handled by `[Install] WantedBy=multi-user.target` in the
    # quadlet file. systemctl enable does not apply to generator-produced units,
    # so we only manage running state here. node-exporter is stateless, so a
    # quadlet change just recreates the container (no config-reload path).

    systemd.service(
        name="Restart node-exporter.service on quadlet change",
        service="node-exporter.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure node-exporter.service running",
        service="node-exporter.service",
        running=True,
        _sudo=True,
    )
