"""Project-wide defaults for every host (pyinfra auto `all` group).

Lowest-priority data source: role group_data files and the per-host dicts in
inventory.py override anything here. Every service is disabled by default and
role groups flip the switches. Machine facts (addresses, UUIDs, GIDs, DHCP
ranges) do NOT belong here - they live in the host dicts in inventory.py.
"""

timezone = "UTC"

base_packages = [
    "vim",
    "git",
    "htop",
    "tmux",
    "curl",
]

# All current and planned hosts run rootful podman; override off per host.
install_podman = True

# --- service enable flags: all off; role groups / host dicts opt in --------
bns_enabled = False
dnsmasq_enabled = False
static_network_enabled = False
pcie_gen3_enabled = False
pi5_exporter_enabled = False
prometheus_enabled = False
grafana_enabled = False
grafana_image_renderer_enabled = False
nodeexporter_enabled = False
podman_exporter_enabled = False
bfeed_enabled = False
monitoring_network_enabled = False
rendering_network_enabled = False
tailscale_serve_enabled = False

# --- pcie (Pi 5 only; enabled per host in inventory.py) ---------------------
# Gen 3 is NOT certified on the Pi 5; reversible via pcie_gen = 2 + reboot.
pcie_gen = 3

# --- bns (caching DNS forwarder + adblock; policy lists in dns_servers.py) --
bns_image = "ghcr.io/bcrisp4/bns"
bns_image_tag = "0.5.1"
bns_host_port_dns = 53
bns_host_port_admin = 9053  # moved off 9090; Prometheus owns the standard port
bns_blocklist_refresh = "6h"
bns_log_level = "info"
bns_query_log_enabled = True
# Per-unit journal rate limit (systemd default 10000/30s; keep journal modest).
bns_log_rate_interval = "30s"
bns_log_rate_burst = 5000
bns_memory_max = "512M"
bns_memory_high = "256M"
bns_cpu_quota = "200%"
bns_tasks_max = 4096

# --- prometheus (rootful quadlet; TSDB in /var/lib/prometheus, uid 65532) ---
prometheus_image = "quay.io/prometheus/prometheus"
prometheus_image_tag = "v3.12.0-distroless"
prometheus_host_port = 9090
prometheus_scrape_interval = "15s"
prometheus_retention_time = "30d"
prometheus_retention_size = "8GB"
# Scrape jobs beyond the built-in self-scrape. Entries: {job, target, labels?}.
# Enabling a service does NOT auto-add its job; the monitoring server's host
# dict in inventory.py carries the full explicit list.
prometheus_scrape_targets = []
prometheus_memory_max = "1G"
prometheus_memory_high = "768M"
prometheus_cpu_quota = "200%"
prometheus_tasks_max = 4096

# --- node-exporter (host namespaces + rootfs for real host metrics) ---------
nodeexporter_image = "quay.io/prometheus/node-exporter"
nodeexporter_image_tag = "v1.11.1"
nodeexporter_host_port = 9100
# Bind address for --web.listen-address ("" = all interfaces). Hosts with a
# public interface set their Tailscale IP here so :9100 stays off the internet.
nodeexporter_listen_address = ""
nodeexporter_memory_max = "128M"
nodeexporter_memory_high = "96M"
nodeexporter_cpu_quota = "50%"
nodeexporter_tasks_max = 1024

# --- podman-exporter (podman API socket; scraped by ContainerName) ----------
podman_exporter_image = "quay.io/navidys/prometheus-podman-exporter"
podman_exporter_image_tag = "v1.21.0"
podman_exporter_port = 9882
podman_exporter_memory_max = "128M"
podman_exporter_memory_high = "96M"
podman_exporter_cpu_quota = "50%"
podman_exporter_tasks_max = 256

# --- pi5-exporter (Pi 5 firmware telemetry; enabled per host, hardware) -----
pi5_exporter_image = "ghcr.io/bcrisp4/pi5_exporter"
# git tag vX.Y.Z publishes image tag X.Y.Z (metadata-action strips the v).
pi5_exporter_image_tag = "0.1.1"
pi5_exporter_port = 2712  # BCM2712 mnemonic
# Keep BELOW prometheus_scrape_interval so scrapes rarely re-read a cached
# collection.
pi5_exporter_collection_interval = "10s"
pi5_exporter_memory_max = "64M"
pi5_exporter_memory_high = "48M"
pi5_exporter_cpu_quota = "50%"
pi5_exporter_tasks_max = 64

# --- podman networks (aardvark-dns name resolution between containers) ------
monitoring_network_name = "monitoring"
rendering_network_name = "rendering"

# --- grafana image renderer (rendering network only, no published port) -----
grafana_image_renderer_image = "docker.io/grafana/grafana-image-renderer"
grafana_image_renderer_image_tag = "v5.8.8"
grafana_image_renderer_memory_max = "1G"
grafana_image_renderer_memory_high = "768M"
grafana_image_renderer_cpu_quota = "150%"
grafana_image_renderer_tasks_max = 4096

# --- grafana (loopback host port; exposed via svc:grafana on the tailnet) ---
grafana_image = "docker.io/grafana/grafana-oss"
grafana_image_tag = "13.0.1"
grafana_host_port = 3000
grafana_root_url = "https://grafana.marlin-tet.ts.net"
grafana_memory_max = "512M"
grafana_memory_high = "384M"
grafana_cpu_quota = "150%"
grafana_tasks_max = 4096

# --- bfeed (feed reader; loopback app port, container-only metrics port) ----
bfeed_image = "ghcr.io/bcrisp4/bfeed"
# git tag vX.Y.Z publishes image tag X.Y.Z (goreleaser strips the v).
bfeed_image_tag = "0.8.0"
bfeed_host_port = 8080
bfeed_metrics_port = 9091
bfeed_base_url = "https://bfeed.marlin-tet.ts.net"
bfeed_memory_max = "256M"
bfeed_memory_high = "192M"
bfeed_cpu_quota = "100%"
bfeed_tasks_max = 1024

# --- tailscale serve (per-host service list lives in the host dict) ---------
tailscale_serve_services = []
