"""Deploy bns (caching DNS forwarder + adblock) as a rootful podman quadlet.

Renders /etc/bns/config.yaml + /etc/containers/systemd/bns.container from host
data, then ensures bns.service is running + enabled. The quadlet generator
converts the .container file into a runtime systemd unit at daemon-reload.

Reload semantics:
- Quadlet unit changed   -> daemon-reload + restart (full container recreate).
- Config-only changed    -> SIGHUP via ExecReload (blocklist + upstream reload,
                            no container restart).

Gated on `bns_enabled` host/group data so non-bns hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, systemd

CONFIG_DIR = "/etc/bns"
CONFIG_PATH = f"{CONFIG_DIR}/config.yaml"
UNIT_PATH = "/etc/containers/systemd/bns.container"

# Persistent blocklist cache. Backed by a podman named volume so first-run
# init copies the image's pre-chowned /var/cache/bns (nonroot:nonroot) into
# the volume — no host-side uid wrangling needed. Volume survives quadlet
# recreate (lives in /var/lib/containers/storage/volumes/).
CACHE_DIR = "/var/cache/bns"
CACHE_BLOCKLISTS_DIR = f"{CACHE_DIR}/blocklists"
CACHE_VOLUME = "bns-cache"

# Nonroot uid inside the distroless image cannot bind privileged ports, so the
# binary always listens on these non-privileged ports inside the container.
# Host-side port mapping is set per-host via bns_host_port_*.
CONTAINER_DNS_PORT = 5354
CONTAINER_ADMIN_PORT = 9090

# Canonical hagezi pro blocklist (http source). Refreshed on the cadence below.
BLOCKLIST_URL = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.txt"
BLOCKLIST_REFRESH = "24h"


def _render_config(data: Mapping) -> str:
    """Render bns YAML config from host data.

    Hand-rolled YAML (no PyYAML dependency) because the shape is fixed and the
    output is unit-tested. Strings holding ':' are quoted; lists indented 2 sp.
    """
    upstream_lines: list[str] = []
    for u in data["bns_upstreams"]:
        upstream_lines.append(f"  - type: {u['type']}")
        if u["type"] == "doh":
            upstream_lines.append(f"    url: {u['url']}")
            ips = ", ".join(u["endpoint_ips"])
            upstream_lines.append(f"    endpoint_ips: [{ips}]")
        else:
            upstream_lines.append(f'    addr: "{u["addr"]}"')
        upstream_lines.append(f"    timeout: {u['timeout']}")

    lines = [
        "# Rendered by pyinfra tasks/bns.py. Do not edit by hand.",
        "listen:",
        f'  udp: ":{CONTAINER_DNS_PORT}"',
        f'  tcp: ":{CONTAINER_DNS_PORT}"',
        "  query_timeout: 5s",
        "",
        "upstreams:",
        *upstream_lines,
        "",
        "cache:",
        "  capacity: 10000",
        "  min_ttl: 0s",
        "  max_ttl: 86400s",
        "  negative_ttl_max: 900s",
        "",
        "blocklists:",
        f"  refresh_interval: {BLOCKLIST_REFRESH}",
        f"  cache_dir: {CACHE_BLOCKLISTS_DIR}",
        "  sources:",
        "    - type: http",
        "      name: hagezi-pro",
        f"      url: {BLOCKLIST_URL}",
        "",
        "admin:",
        f'  listen: ":{CONTAINER_ADMIN_PORT}"',
        "",
        "logging:",
        f"  level: {data['bns_log_level']}",
        "  format: json",
        "  query_log:",
        f"    enabled: {str(data['bns_query_log_enabled']).lower()}",
        "",
        "shutdown_timeout: 5s",
        "startup_probe_timeout: 3s",
    ]
    return "\n".join(lines) + "\n"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for bns from host data."""
    image = f"{data['bns_image']}:{data['bns_image_tag']}"
    dns_port = data["bns_host_port_dns"]
    admin_port = data["bns_host_port_admin"]

    lines = [
        "# Rendered by pyinfra tasks/bns.py. Do not edit by hand.",
        "[Unit]",
        "Description=bns - caching DNS forwarder with adblock",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=bns",
        # Dual-stack bind: linux defaults IPV6_V6ONLY=1 on AF_INET6 sockets, so
        # a single PublishPort=53:... only catches IPv4. Add explicit [::]
        # lines to also listen on IPv6 (LAN + Tailscale v6).
        f"PublishPort={dns_port}:{CONTAINER_DNS_PORT}/udp",
        f"PublishPort={dns_port}:{CONTAINER_DNS_PORT}/tcp",
        f"PublishPort={admin_port}:{CONTAINER_ADMIN_PORT}/tcp",
        f"PublishPort=[::]:{dns_port}:{CONTAINER_DNS_PORT}/udp",
        f"PublishPort=[::]:{dns_port}:{CONTAINER_DNS_PORT}/tcp",
        f"PublishPort=[::]:{admin_port}:{CONTAINER_ADMIN_PORT}/tcp",
        f"Volume={CONFIG_PATH}:{CONFIG_PATH}:ro",
        # Named volume for blocklist cache. Podman auto-creates on first run
        # and seeds it from the image's /var/cache/bns (already chowned to
        # nonroot:nonroot at build time), so the bns process can write.
        f"Volume={CACHE_VOLUME}:{CACHE_DIR}",
        "",
        "[Service]",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # kernel when cgroup memory ceiling hit), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        "ExecReload=/usr/bin/podman kill --signal HUP %N",
        # Per-unit journal rate limit: drops bns log lines above burst within
        # interval so a query storm cannot flood journald.
        f"LogRateLimitIntervalSec={data['bns_log_rate_interval']}",
        f"LogRateLimitBurst={data['bns_log_rate_burst']}",
        # Cgroup ceilings applied at the systemd unit level. Quadlet passes
        # [Service] through unchanged, so these work across podman versions
        # (vs Memory=/CPUS= in [Container] which requires podman >= 5.5).
        f"MemoryMax={data['bns_memory_max']}",
        f"MemoryHigh={data['bns_memory_high']}",
        f"CPUQuota={data['bns_cpu_quota']}",
        f"TasksMax={data['bns_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "bns_image",
    "bns_image_tag",
    "bns_host_port_dns",
    "bns_host_port_admin",
    "bns_upstreams",
    "bns_log_level",
    "bns_query_log_enabled",
    "bns_log_rate_interval",
    "bns_log_rate_burst",
    "bns_memory_max",
    "bns_memory_high",
    "bns_cpu_quota",
    "bns_tasks_max",
)


@deploy("Deploy bns")
def bns() -> None:
    if not host.data.get("bns_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the
    # pure renderers stay test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    files.directory(
        name="Ensure /etc/bns config dir",
        path=CONFIG_DIR,
        present=True,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
    )

    config = files.put(
        name="Render /etc/bns/config.yaml",
        src=StringIO(_render_config(data)),
        dest=CONFIG_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    unit = files.put(
        name="Render /etc/containers/systemd/bns.container",
        src=StringIO(_render_quadlet(data)),
        dest=UNIT_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # Boot-time start is handled by `[Install] WantedBy=multi-user.target` in
    # the quadlet file (quadlet generator wires the wants symlink). systemctl
    # enable does not apply to generator-produced units, so we only manage the
    # running state here.

    systemd.service(
        name="Restart bns.service on quadlet change",
        service="bns.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=unit.did_change,
        _sudo=True,
    )

    systemd.service(
        name="SIGHUP bns.service on config-only change",
        service="bns.service",
        reloaded=True,
        _if=lambda: config.did_change() and not unit.did_change(),
        _sudo=True,
    )

    systemd.service(
        name="Ensure bns.service running",
        service="bns.service",
        running=True,
        _sudo=True,
    )
