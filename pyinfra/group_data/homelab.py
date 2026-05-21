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
bns_image_tag = "0.2.0"
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
