"""Deploy pi5_exporter as a rootful podman quadlet.

Renders /etc/containers/systemd/pi5-exporter.container from host data, then
ensures pi5-exporter.service is running. The quadlet generator converts the
.container file into a runtime systemd unit at daemon-reload.

pi5_exporter (ghcr.io/bcrisp4/pi5_exporter) is a Prometheus exporter that runs
ON the Pi 5 and exposes firmware/mailbox telemetry node-exporter cannot reach
(PMIC per-rail power, sticky throttle/under-voltage flags, firmware voltages and
clocks, SoC/PMIC temperature, RTC backup cell). It complements node-exporter;
run both.

Firmware access needs THREE things (all native quadlet [Container] keys, no
PodmanArgs):
- AddDevice=/dev/vcio    -> the firmware mailbox char device into the container.
  The exporter reaches the VideoCore firmware via ioctl() on it.
- GroupAdd=<video gid>   -> /dev/vcio is `crw-rw---- root:video` and the image
  runs as a non-root user (uid 65532), so it needs the host `video` group to open
  it. Rootful podman keeps NO useful supplementary groups (keep-groups would keep
  root's, not video), so the numeric host GID is passed explicitly
  (pi5_exporter_video_gid, 44 on Debian/RPi OS). Without it: EACCES on /dev/vcio.
- Unmask=/sys/firmware   -> OPTIONAL since v0.1.1; only the pi5_board_info
  identity metric (board model/serial/SoC) needs it. It reads
  /proc/device-tree/compatible (a symlink to /sys/firmware/devicetree/base), which
  podman MASKS by default (an empty tmpfs that also shadows any bind-mount there),
  so the symlink dangles -> ENOENT. Unmasking reveals the host's read-only
  firmware sysfs; no volume works. We keep it for the full collector set.
  (Pre-0.1.1 the exporter fail-closed ALL firmware collectors on this read, so it
  was mandatory; v0.1.1 made the other collectors tolerate a missing device-tree.)

Missing device/group -> a quietly empty set of pi5_* firmware metrics. The sysfs
collectors (rtc, watchdog) run regardless.

Networking: the exporter joins the shared `monitoring` podman network (see
tasks/podman_network.py) and publishes NO host port. Prometheus is on the same
network and scrapes it by ContainerName via aardvark-dns (pi5-exporter:2712),
exactly as it reaches Grafana / podman-exporter. No host, LAN or Tailscale
exposure. Port 2712 is the BCM2712 mnemonic (the exporter's default).

State: the exporter is stateless. Like node-exporter / podman-exporter there is
no _render_config, data dir or uid chown, and no SIGHUP reload path; a quadlet
change just recreates the container.

Gated on `pi5_exporter_enabled` host/group data so non-Pi-5 hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

UNIT_PATH = "/etc/containers/systemd/pi5-exporter.container"

# The firmware mailbox char device. `crw-rw---- root:video`; the exporter opens
# it via ioctl() to reach the VideoCore firmware.
VCIO_DEVICE = "/dev/vcio"

# Firmware sysfs tree, masked by podman default. Unmasked so the pi5_board_info
# metric can read /proc/device-tree/compatible (-> /sys/firmware/devicetree/base).
FIRMWARE_SYSFS = "/sys/firmware"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for pi5_exporter from host data."""
    image = f"{data['pi5_exporter_image']}:{data['pi5_exporter_image_tag']}"
    exec_args = " ".join(
        [
            f"--web.listen-address=:{data['pi5_exporter_port']}",
            # Internal collection ticker. /metrics serves the latest cached
            # snapshot, so this is kept BELOW the Prometheus scrape_interval to cut
            # the odds of two scrapes returning the same cached collection.
            f"--collection.interval={data['pi5_exporter_collection_interval']}",
        ]
    )
    lines = [
        "# Rendered by pyinfra tasks/pi5_exporter.py. Do not edit by hand.",
        "[Unit]",
        "Description=pi5_exporter - Raspberry Pi 5 firmware metrics",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=pi5-exporter",
        # Shared bridge with Prometheus (tasks/podman_network.py): Prometheus
        # resolves this container as `pi5-exporter` via aardvark-dns. NO
        # PublishPort: reachable solely by Prometheus over this network.
        "Network=monitoring.network",
        # Firmware access: the mailbox device + the host `video` GID so the
        # non-root image user (uid 65532) can open it. Without the group the
        # exporter silently skips every firmware collector (EACCES).
        f"AddDevice={VCIO_DEVICE}",
        f"GroupAdd={data['pi5_exporter_video_gid']}",
        # Reveal /sys/firmware (podman masks it with an empty tmpfs by default) so
        # the pi5_board_info metric can read the device tree. Optional since
        # v0.1.1 (other firmware collectors no longer need it); kept for the full
        # collector set. -> --security-opt unmask=/sys/firmware.
        f"Unmask={FIRMWARE_SYSFS}",
        # Exec= overrides the image CMD only; the /usr/local/bin/pi5_exporter
        # entrypoint stays, so this flag is appended to it.
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
        f"MemoryMax={data['pi5_exporter_memory_max']}",
        f"MemoryHigh={data['pi5_exporter_memory_high']}",
        f"CPUQuota={data['pi5_exporter_cpu_quota']}",
        f"TasksMax={data['pi5_exporter_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "pi5_exporter_image",
    "pi5_exporter_image_tag",
    "pi5_exporter_port",
    "pi5_exporter_collection_interval",
    "pi5_exporter_video_gid",
    "pi5_exporter_memory_max",
    "pi5_exporter_memory_high",
    "pi5_exporter_cpu_quota",
    "pi5_exporter_tasks_max",
)


@deploy("Deploy pi5_exporter")
def pi5_exporter() -> None:
    if not host.data.get("pi5_exporter_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    unit = files.put(
        name="Render /etc/containers/systemd/pi5-exporter.container",
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
        name="Restart pi5-exporter.service on quadlet change",
        service="pi5-exporter.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="Ensure pi5-exporter.service running",
        service="pi5-exporter.service",
        running=True,
        _sudo=True,
    )
