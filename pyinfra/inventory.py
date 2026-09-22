"""pyinfra inventory.

Hosts are declared ONCE in `all` with their per-host data dict; role groups
are bare-FQDN membership lists. pyinfra creates hosts only from an explicit
`all` group, so the guard at the bottom fails fast if a role names a host
missing from `all`.

Data resolution (first match wins): host dict here > group_data/<role>.py >
group_data/all.py. Keep role-file keys disjoint so group merge order never
matters. Verify with: uv run pyinfra inventory.py debug-inventory
"""

_PI = "rpi5-4cpu-16gb-home-1.marlin-tet.ts.net"
_PI_SHORT = "rpi5-4cpu-16gb-home-1"

_pi_data = {
    "ssh_user": "ben",
    # --- machine facts ------------------------------------------------------
    # The router supplies IPv4 settings to eth0 through DHCP.
    "netplan": {
        "interface": "eth0",
        "connection_uuid": "75a1216a-9d1a-30cd-8aca-ace5526ec021",
        "connection_name": "netplan-eth0",
    },
    # Remove the former LAN DHCP service from this host.
    "remove_dnsmasq_enabled": True,
    # Pi 5 firmware telemetry exporter; hardware-bound, so enabled per host.
    # GID 44 = `getent group video` on Raspberry Pi OS / Debian.
    "pi5_exporter_enabled": True,
    "pi5_exporter_video_gid": 44,
    # Force PCIe Gen 3 on the external connector (not certified; manual
    # reboot; reversible via pcie_gen = 2).
    "pcie_gen3_enabled": True,
    # Tailscale Services THIS host advertises. Service objects, ACL grants,
    # auto-approval live in terraform/global/tailscale.tf.
    "tailscale_serve_services": [
        {"name": "svc:prometheus", "backend_port": 9090, "https_port": 443},
        {"name": "svc:grafana", "backend_port": 3000, "https_port": 443},
        {"name": "svc:bfeed", "backend_port": 8080, "https_port": 443},
        {"name": "svc:bscribe", "backend_port": 8000, "https_port": 443},
    ],
    # Everything the central Prometheus scrapes (tasks/prometheus.py loops
    # over this). Enabling a service does NOT auto-add its job: add the entry
    # here. Same-host container targets use ContainerName over the monitoring
    # bridge; node-exporter is host-net (host.containers.internal). Future cloud
    # hosts: <host>.marlin-tet.ts.net:<port>.
    "prometheus_scrape_targets": [
        {
            "job": "node-exporter",
            "target": "host.containers.internal:9100",
            "labels": {"instance": _PI_SHORT},
        },
        {
            "job": "grafana",
            "target": "grafana:3000",
            "labels": {"instance": _PI_SHORT},
        },
        {
            "job": "podman-exporter",
            "target": "podman-exporter:9882",
            "labels": {"instance": _PI_SHORT},
        },
        {
            "job": "pi5-exporter",
            "target": "pi5-exporter:2712",
            "labels": {"instance": _PI_SHORT},
        },
        {
            "job": "bfeed",
            "target": "bfeed:9091",
            "labels": {"instance": _PI_SHORT},
        },
        {
            "job": "bscribe",
            "target": "bscribe:9090",
            "labels": {"instance": _PI_SHORT},
        },
    ],
}

all = [(_PI, _pi_data)]

# --- roles -------------------------------------------------------------------
# Enable BNS after the router reserves a stable address for the Pi.
dns_servers = []
monitoring_servers = [_PI]
metrics_agents = [_PI]
feed_hosts = [_PI]
scribe_hosts = [_PI]

# --- guard ---------------------------------------------------------------
# pyinfra creates hosts only from `all` when it is defined explicitly; a host
# named only in a role group is silently dropped. Fail loud instead.
_known = {h[0] if isinstance(h, tuple) else h for h in all}
_roles = {
    "dns_servers": dns_servers,
    "monitoring_servers": monitoring_servers,
    "metrics_agents": metrics_agents,
    "feed_hosts": feed_hosts,
    "scribe_hosts": scribe_hosts,
}
for _role_name, _members in _roles.items():
    for _member in _members:
        if _member not in _known:
            raise ValueError(f"{_member} is in {_role_name} but not in `all`")
