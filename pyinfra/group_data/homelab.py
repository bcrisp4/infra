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

bns_enabled = True
bns_image = "ghcr.io/bcrisp4/bns"
bns_image_tag = "0.1.0"
bns_host_port_dns = 53
bns_host_port_admin = 9090
bns_upstreams = [
    {"addr": "1.1.1.1:53", "timeout": "2s"},
    {"addr": "9.9.9.9:53", "timeout": "2s"},
]
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
