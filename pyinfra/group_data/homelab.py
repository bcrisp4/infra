"""Shared data for the `homelab` group.

Override per host by setting the same key in inventory.py host tuple.
"""

timezone = "UTC"

base_packages = [
    "vim",
    "git",
    "htop",
    "tmux",
    "curl",
]

install_podman = True

# Force PCIe Gen 3.0 on the Pi 5 via /boot/firmware/config.txt (tasks/pcie.py).
# Gen 3 is NOT certified on the Pi 5 and may be unstable; opt-in here, reversible
# by setting pcie_gen = 2 (or disabling) + reboot. Requires a manual reboot.
pcie_gen3_enabled = True
pcie_gen = 3

bns_enabled = True
bns_image = "ghcr.io/bcrisp4/bns"
bns_image_tag = "0.5.1"
# LAN IPv4 the bns container publishes on (DNS + admin). Bound to this address
# only -- not the wildcard -- so it does not occupy :53 on the podman bridge
# gateways (which would collide with aardvark-dns on the monitoring network) and
# does not listen on Tailscale. Matches the Pi's static LAN IP (static_network).
bns_listen_address = "192.168.1.2"
bns_host_port_dns = 53
bns_host_port_admin = 9053  # moved off 9090; Prometheus owns the standard port
bns_upstreams = [
    {
        "type": "doh",
        "url": "https://cloudflare-dns.com/dns-query",
        "endpoint_ips": ["1.1.1.1", "1.0.0.1"],
        "timeout": "5s",
    },
    {
        "type": "doh",
        "url": "https://dns.quad9.net/dns-query",
        "endpoint_ips": ["9.9.9.9", "149.112.112.112"],
        "timeout": "5s",
    },
]
# Blocklist sources (all http type) fetched + refreshed by bns. hagezi pro =
# balanced general blocklist; tif = "threat intelligence feeds" (malware,
# phishing, scam domains).
bns_blocklists = [
    {
        "name": "hagezi-pro",
        "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.txt",
    },
    {
        "name": "hagezi-tif",
        "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/tif.txt",
    },
]
# How often bns refetches the blocklist sources.
bns_blocklist_refresh = "6h"
bns_log_level = "info"
bns_query_log_enabled = True
# Per-unit journal rate limit. Drops bns log lines above the burst within
# interval. systemd default = 10000/30s; tighten to keep journal usage modest.
bns_log_rate_interval = "30s"
bns_log_rate_burst = 5000
# systemd-native cgroup ceilings (applied in [Service] section of the quadlet).
# Values use systemd unit syntax (uppercase suffix, percentage for CPUQuota).
bns_memory_max = "512M"
bns_memory_high = "256M"
bns_cpu_quota = "200%"
bns_tasks_max = 4096

# Prometheus runs as a rootful podman quadlet (tasks/prometheus.py). Scrapes
# itself + bns (via host.containers.internal:bns_host_port_admin). TSDB in a
# plain rootfs dir at /var/lib/prometheus. Distroless image runs as uid 65532.
prometheus_enabled = True
prometheus_image = "quay.io/prometheus/prometheus"
prometheus_image_tag = "v3.12.0-distroless"
prometheus_host_port = 9090
prometheus_scrape_interval = "15s"
prometheus_retention_time = "30d"
prometheus_retention_size = "8GB"
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
prometheus_memory_max = "1G"
prometheus_memory_high = "768M"
prometheus_cpu_quota = "200%"
prometheus_tasks_max = 4096

# node-exporter runs as a rootful podman quadlet (tasks/nodeexporter.py). Host
# namespaces + rootfs (Network=host, PidMode=host, /:/host:ro) so metrics
# describe the Pi, not the container. Binds 0.0.0.0:9100 (Network=host removes
# the loopback restriction Prometheus uses; matches bns admin's trusted-LAN
# exposure). Prometheus scrapes it via host.containers.internal:9100. Stateless,
# so ceilings are small.
nodeexporter_enabled = True
nodeexporter_image = "quay.io/prometheus/node-exporter"
nodeexporter_image_tag = "v1.11.1"
nodeexporter_host_port = 9100
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
nodeexporter_memory_max = "128M"
nodeexporter_memory_high = "96M"
nodeexporter_cpu_quota = "50%"
nodeexporter_tasks_max = 1024

# prometheus-podman-exporter runs as a rootful podman quadlet
# (tasks/podman_exporter.py). Exports podman container/pod/image/system metrics.
# Talks to podman over the rootful API socket (/run/podman/podman.sock), so it
# needs NO host networking: it joins the monitoring network and Prometheus
# scrapes it by ContainerName (podman-exporter:9882), like Grafana. No published
# port. Runs as root (socket access); --collector.enhance-metrics adds
# per-container CPU/memory/network usage. Stateless, so ceilings are small.
podman_exporter_enabled = True
podman_exporter_image = "quay.io/navidys/prometheus-podman-exporter"
podman_exporter_image_tag = "v1.21.0"
podman_exporter_port = 9882
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
podman_exporter_memory_max = "128M"
podman_exporter_memory_high = "96M"
podman_exporter_cpu_quota = "50%"
podman_exporter_tasks_max = 256

# pi5_exporter runs as a rootful podman quadlet (tasks/pi5_exporter.py). Exposes
# Pi 5 firmware/mailbox telemetry node-exporter cannot reach (PMIC per-rail
# power, sticky throttle/under-voltage flags, firmware voltages/clocks, SoC/PMIC
# temperature, RTC backup cell). Joins the monitoring network; Prometheus scrapes
# it by ContainerName (pi5-exporter:2712), like podman-exporter. No published
# port. Needs /dev/vcio (AddDevice) + the host `video` GID (GroupAdd) so the
# non-root image user (uid 65532) can open the firmware mailbox; without the
# group it silently skips all firmware collectors. Port 2712 = BCM2712 mnemonic.
# Stateless, so ceilings are small.
pi5_exporter_enabled = True
pi5_exporter_image = "ghcr.io/bcrisp4/pi5_exporter"
# git tag vX.Y.Z publishes image tag X.Y.Z (metadata-action strips the v).
pi5_exporter_image_tag = "0.1.1"
pi5_exporter_port = 2712
# Internal collection ticker. /metrics serves the latest cached snapshot, so keep
# this BELOW prometheus_scrape_interval (15s) so a scrape rarely re-reads the same
# cached collection. The exporter default equals 15s -- this lowers it.
pi5_exporter_collection_interval = "10s"
# Numeric host `video` GID (getent group video). 44 on Debian / Raspberry Pi OS.
# Rootful podman keeps no useful supplementary groups, so it is passed explicitly.
pi5_exporter_video_gid = 44
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
pi5_exporter_memory_max = "64M"
pi5_exporter_memory_high = "48M"
pi5_exporter_cpu_quota = "50%"
pi5_exporter_tasks_max = 64

# Shared podman network for the metrics stack (tasks/podman_network.py).
# Prometheus + Grafana attach to it and resolve each other by ContainerName via
# aardvark-dns. node-exporter stays Network=host (real host metrics) and is
# scraped via host.containers.internal instead.
monitoring_network_enabled = True
monitoring_network_name = "monitoring"

# Dedicated podman network for Grafana <-> image renderer only. Grafana joins
# both this and monitoring; the renderer joins only this and publishes no host
# port, so it is reachable by Grafana but not Prometheus, the LAN or Tailscale.
rendering_network_enabled = True
rendering_network_name = "rendering"

# Grafana image renderer runs as a rootful podman quadlet (tasks/image_renderer.py).
# Standalone remote rendering service (Node + headless Chromium) that turns panels
# into PNGs. Joins the rendering network only; no published port. Grafana reaches
# it at http://grafana-image-renderer:8081/render. Stateless (snapshots to /tmp),
# so no volume. Chromium is memory-hungry, so ceilings are roomier than node-exporter.
# Auth token is generated on the host (never committed) and shared with Grafana via
# an EnvironmentFile; Grafana 13 refuses to start with the default renderer token.
grafana_image_renderer_enabled = True
grafana_image_renderer_image = "docker.io/grafana/grafana-image-renderer"
grafana_image_renderer_image_tag = "v5.8.8"
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
grafana_image_renderer_memory_max = "1G"
grafana_image_renderer_memory_high = "768M"
grafana_image_renderer_cpu_quota = "150%"
grafana_image_renderer_tasks_max = 4096

# Grafana runs as a rootful podman quadlet (tasks/grafana.py). Joins the
# monitoring network and queries Prometheus by name (http://prometheus:9090).
# Loopback-only host port; exposed on the tailnet via svc:grafana. sqlite state
# (WAL enabled) in a plain rootfs dir at /var/lib/grafana.
# Image runs as uid 472. Ships default admin; password change is forced on first
# login (access is already gated by the tailnet).
grafana_enabled = True
grafana_image = "docker.io/grafana/grafana-oss"
grafana_image_tag = "13.0.1"
grafana_host_port = 3000
grafana_root_url = "https://grafana.marlin-tet.ts.net"
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
grafana_memory_max = "512M"
grafana_memory_high = "384M"
grafana_cpu_quota = "150%"
grafana_tasks_max = 4096

# bfeed (self-hosted RSS/Atom/JSON feed reader) runs as a rootful podman quadlet
# (tasks/bfeed.py). Single Go binary + sqlite at /var/lib/bfeed (image runs as
# uid 65532). No podman network -- it talks to nothing else on the host but polls
# feeds over the internet, so it stays on the default bridge for outbound NAT.
# Loopback-only host port; exposed on the tailnet via svc:bfeed. BFEED_BASE_URL is
# mandatory (bfeed exits without it) and must be the public MagicDNS URL.
bfeed_enabled = True
bfeed_image = "ghcr.io/bcrisp4/bfeed"
# git tag vX.Y.Z publishes image tag X.Y.Z (goreleaser strips the v).
bfeed_image_tag = "0.6.0"
bfeed_host_port = 8080
bfeed_base_url = "https://bfeed.marlin-tet.ts.net"
# systemd-native cgroup ceilings (applied in [Service] of the quadlet).
bfeed_memory_max = "256M"
bfeed_memory_high = "192M"
bfeed_cpu_quota = "100%"
bfeed_tasks_max = 1024

# Expose services as Tailscale Services (tasks/tailscale_service.py). The Pi
# advertises each via `tailscale serve`; tailscaled terminates TLS on :443 and
# reverse-proxies to the loopback-bound container. MagicDNS:
# <name>.marlin-tet.ts.net. Service objects + ACL grants + auto-approval live in
# terraform/global/tailscale.tf.
tailscale_serve_enabled = True
tailscale_serve_services = [
    {"name": "svc:prometheus", "backend_port": prometheus_host_port, "https_port": 443},
    {"name": "svc:grafana", "backend_port": grafana_host_port, "https_port": 443},
    {"name": "svc:bfeed", "backend_port": bfeed_host_port, "https_port": 443},
]

# Static network config rendered into a NetworkManager keyfile. The Pi
# moves off router-issued DHCP because it now runs its own DHCP server
# (dnsmasq below); a host cannot safely lease from itself.
static_network_enabled = True
static_network = {
    "connection_id": "Wired connection 1",
    # Preserve the existing in-memory UUID so NM updates the connection
    # rather than creating a duplicate alongside it.
    "connection_uuid": "3c612036-b566-3434-8ac8-5d5b45b2d446",
    "interface": "eth0",
    "ipv4_address": "192.168.1.2/24",
    "ipv4_gateway": "192.168.1.1",
    "ipv4_dns": ["1.1.1.1", "9.9.9.9"],
    # Router IPv6 disabled by user; turn it off on the host too so the
    # stale SLAAC address falls off and nothing tries DHCPv6.
    "ipv6_method": "disabled",
}

# dnsmasq runs DHCP-only (port=0; bns owns :53). Hands out bns directly
# as DHCP option 6 so LAN clients stop going through the router as a DNS
# forwarder. Range/lease match the previous CR1000A settings.
dnsmasq_enabled = True
dnsmasq_interface = "eth0"
dnsmasq_dhcp_range_start = "192.168.1.11"
dnsmasq_dhcp_range_end = "192.168.1.254"
dnsmasq_dhcp_netmask = "255.255.255.0"
dnsmasq_dhcp_lease = "24h"
dnsmasq_gateway = "192.168.1.1"
dnsmasq_dns = "192.168.1.2"
