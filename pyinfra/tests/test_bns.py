"""Unit tests for tasks.bns pure renderers."""

import pytest

from tasks.bns import (
    CACHE_BLOCKLISTS_DIR,
    CACHE_DIR,
    CACHE_VOLUME,
    CONFIG_PATH,
    CONTAINER_ADMIN_PORT,
    CONTAINER_DNS_PORT,
    _render_config,
    _render_quadlet,
)

BASE_DATA: dict = {
    "bns_image": "ghcr.io/bcrisp4/bns",
    "bns_image_tag": "v0.1.0",
    "bns_listen_address": "192.168.1.2",
    "bns_host_port_dns": 53,
    "bns_host_port_admin": 9090,
    "bns_upstreams": [
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
    ],
    "bns_blocklists": [
        {
            "name": "hagezi-pro",
            "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.txt",
        },
        {
            "name": "hagezi-tif",
            "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/tif.txt",
        },
    ],
    "bns_blocklist_refresh": "6h",
    "bns_log_level": "info",
    "bns_query_log_enabled": True,
    "bns_log_rate_interval": "30s",
    "bns_log_rate_burst": 5000,
    "bns_memory_max": "512M",
    "bns_memory_high": "256M",
    "bns_cpu_quota": "200%",
    "bns_tasks_max": 4096,
}


# ---------- _render_config ----------


def test_config_has_listen_block_with_container_dns_port() -> None:
    out = _render_config(BASE_DATA)
    assert "listen:" in out
    assert f'  udp: ":{CONTAINER_DNS_PORT}"' in out
    assert f'  tcp: ":{CONTAINER_DNS_PORT}"' in out


def test_config_admin_block_uses_container_admin_port() -> None:
    out = _render_config(BASE_DATA)
    assert "admin:" in out
    assert f'  listen: ":{CONTAINER_ADMIN_PORT}"' in out


def test_config_expands_doh_upstream_list() -> None:
    out = _render_config(BASE_DATA)
    assert "  - type: doh" in out
    assert "    url: https://cloudflare-dns.com/dns-query" in out
    assert "    endpoint_ips: [1.1.1.1, 1.0.0.1]" in out
    assert "    url: https://dns.quad9.net/dns-query" in out
    assert "    endpoint_ips: [9.9.9.9, 149.112.112.112]" in out
    assert "    timeout: 5s" in out


def test_config_supports_single_upstream() -> None:
    out = _render_config(
        {
            **BASE_DATA,
            "bns_upstreams": [
                {
                    "type": "doh",
                    "url": "https://dns.google/dns-query",
                    "endpoint_ips": ["8.8.8.8", "8.8.4.4"],
                    "timeout": "1s",
                },
            ],
        }
    )
    assert "    url: https://dns.google/dns-query" in out
    assert "    endpoint_ips: [8.8.8.8, 8.8.4.4]" in out
    assert "    timeout: 1s" in out
    assert "cloudflare-dns.com" not in out


def test_config_supports_many_upstreams() -> None:
    upstreams = [
        {
            "type": "doh",
            "url": f"https://ns{i}.example/dns-query",
            "endpoint_ips": [f"10.0.0.{i}"],
            "timeout": "2s",
        }
        for i in range(1, 6)
    ]
    out = _render_config({**BASE_DATA, "bns_upstreams": upstreams})
    for u in upstreams:
        assert f"    url: {u['url']}" in out
        assert f"    endpoint_ips: [{u['endpoint_ips'][0]}]" in out


def test_config_supports_udp_upstream() -> None:
    out = _render_config(
        {
            **BASE_DATA,
            "bns_upstreams": [{"type": "udp", "addr": "1.1.1.1:53", "timeout": "2s"}],
        }
    )
    assert "  - type: udp" in out
    assert '    addr: "1.1.1.1:53"' in out
    assert "    timeout: 2s" in out
    assert "endpoint_ips" not in out


@pytest.mark.parametrize("level", ["debug", "info", "warn", "error"])
def test_config_log_level_substituted(level: str) -> None:
    out = _render_config({**BASE_DATA, "bns_log_level": level})
    assert f"  level: {level}" in out


@pytest.mark.parametrize(("flag", "expected"), [(True, "true"), (False, "false")])
def test_config_query_log_toggle(flag: bool, expected: str) -> None:
    out = _render_config({**BASE_DATA, "bns_query_log_enabled": flag})
    assert f"    enabled: {expected}" in out


def test_config_terminates_with_single_newline() -> None:
    out = _render_config(BASE_DATA)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_config_renders_blocklist_sources_from_data() -> None:
    """Blocklist sources come from bns_blocklists, each an http source."""
    out = _render_config(BASE_DATA)
    assert "    - type: http" in out
    for b in BASE_DATA["bns_blocklists"]:
        assert f"      name: {b['name']}" in out
        assert f"      url: {b['url']}" in out
    # File source must not leak back in.
    assert "    - type: file" not in out


def test_config_supports_single_blocklist() -> None:
    out = _render_config(
        {
            **BASE_DATA,
            "bns_blocklists": [
                {"name": "hagezi-pro", "url": "https://example/pro.txt"},
            ],
        }
    )
    assert "      name: hagezi-pro" in out
    assert "      url: https://example/pro.txt" in out
    assert "hagezi-tif" not in out


def test_config_blocklists_refresh_and_cache_dir() -> None:
    out = _render_config(BASE_DATA)
    assert "  refresh_interval: 6h" in out
    assert f"  cache_dir: {CACHE_BLOCKLISTS_DIR}" in out


@pytest.mark.parametrize("interval", ["1h", "6h", "24h"])
def test_config_refresh_interval_tracks_data(interval: str) -> None:
    out = _render_config({**BASE_DATA, "bns_blocklist_refresh": interval})
    assert f"  refresh_interval: {interval}" in out


def test_config_is_deterministic() -> None:
    assert _render_config(BASE_DATA) == _render_config(BASE_DATA)


# ---------- _render_quadlet ----------


def test_quadlet_has_all_required_sections() -> None:
    out = _render_quadlet(BASE_DATA)
    for section in ("[Unit]", "[Container]", "[Service]", "[Install]"):
        assert section in out, f"missing section {section}"


def test_quadlet_pins_image_with_tag() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Image=ghcr.io/bcrisp4/bns:v0.1.0" in out


def test_quadlet_publishes_dns_and_admin_on_lan_ip_only() -> None:
    """Bound to the LAN IP only: not the wildcard (would collide with
    aardvark-dns on :53 of the bridge gateways) and not Tailscale."""
    out = _render_quadlet(BASE_DATA)
    assert f"PublishPort=192.168.1.2:53:{CONTAINER_DNS_PORT}/udp" in out
    assert f"PublishPort=192.168.1.2:53:{CONTAINER_DNS_PORT}/tcp" in out
    assert f"PublishPort=192.168.1.2:9090:{CONTAINER_ADMIN_PORT}/tcp" in out
    # Wildcard (host-IP-less) publishes must NOT appear.
    assert f"PublishPort=53:{CONTAINER_DNS_PORT}/udp" not in out
    assert f"PublishPort=9090:{CONTAINER_ADMIN_PORT}/tcp" not in out


def test_quadlet_does_not_publish_ipv6() -> None:
    """IPv6 is disabled host-wide; no [::] publishes."""
    out = _render_quadlet(BASE_DATA)
    assert "[::]" not in out


@pytest.mark.parametrize("address", ["192.168.1.2", "10.0.0.5"])
def test_quadlet_publish_address_tracks_data(address: str) -> None:
    out = _render_quadlet({**BASE_DATA, "bns_listen_address": address})
    assert f"PublishPort={address}:53:{CONTAINER_DNS_PORT}/udp" in out
    assert f"PublishPort={address}:9090:{CONTAINER_ADMIN_PORT}/tcp" in out


def test_quadlet_publishes_custom_host_ports() -> None:
    out = _render_quadlet({**BASE_DATA, "bns_host_port_dns": 5353, "bns_host_port_admin": 19090})
    assert f"PublishPort=192.168.1.2:5353:{CONTAINER_DNS_PORT}/udp" in out
    assert f"PublishPort=192.168.1.2:5353:{CONTAINER_DNS_PORT}/tcp" in out
    assert f"PublishPort=192.168.1.2:19090:{CONTAINER_ADMIN_PORT}/tcp" in out


def test_quadlet_bind_mounts_config_readonly() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={CONFIG_PATH}:{CONFIG_PATH}:ro" in out


def test_quadlet_mounts_named_volume_for_blocklist_cache() -> None:
    """Named volume (not bind mount) so podman seeds it from the image's
    pre-chowned /var/cache/bns on first run."""
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={CACHE_VOLUME}:{CACHE_DIR}" in out
    # Bind-mount form must not leak back in.
    assert f"Volume={CACHE_DIR}:{CACHE_DIR}" not in out


def test_quadlet_emits_resource_caps_in_service_section() -> None:
    """Cgroup ceilings live in [Service] (systemd-native), not [Container]
    (podman-native), so the unit works on podman < 5.5 too."""
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=512M" in out
    assert "MemoryHigh=256M" in out
    assert "CPUQuota=200%" in out
    assert "TasksMax=4096" in out
    # Old podman-native keys must NOT appear (would fail quadlet generator
    # on podman < 5.5 with "unsupported key" error).
    for forbidden in ("Memory=", "MemoryReservation=", "CPUS=", "PidsLimit="):
        assert forbidden not in out, f"forbidden quadlet key emitted: {forbidden!r}"
    # Caps must be in the [Service] block, not [Container].
    container_block = out.split("[Container]", 1)[1].split("[Service]", 1)[0]
    for key in ("MemoryMax", "MemoryHigh", "CPUQuota", "TasksMax"):
        assert key not in container_block, f"{key} should not be in [Container]"


def test_quadlet_sighup_exec_reload() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "ExecReload=/usr/bin/podman kill --signal HUP %N" in out


def test_quadlet_install_target_is_multi_user() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "WantedBy=multi-user.target" in out
    assert "WantedBy=default.target" not in out


def test_quadlet_restart_policy_always() -> None:
    """Restart=always covers crashes AND OOM-kill (SIGKILL from cgroup memory limit)."""
    out = _render_quadlet(BASE_DATA)
    assert "Restart=always" in out
    assert "Restart=on-failure" not in out
    assert "RestartSec=5s" in out


def test_quadlet_start_limits_present() -> None:
    """StartLimit* tolerate a startup loop without permanent give-up."""
    out = _render_quadlet(BASE_DATA)
    assert "StartLimitIntervalSec=60s" in out
    assert "StartLimitBurst=10" in out


def test_quadlet_journal_rate_limit_present() -> None:
    """Per-unit journal rate limit caps log volume from query storms."""
    out = _render_quadlet(BASE_DATA)
    assert "LogRateLimitIntervalSec=30s" in out
    assert "LogRateLimitBurst=5000" in out


def test_quadlet_network_online_ordering() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Wants=network-online.target" in out
    assert "After=network-online.target" in out


def test_quadlet_terminates_with_single_newline() -> None:
    out = _render_quadlet(BASE_DATA)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_quadlet_is_deterministic() -> None:
    assert _render_quadlet(BASE_DATA) == _render_quadlet(BASE_DATA)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.1.0", "Image=ghcr.io/bcrisp4/bns:v0.1.0"),
        ("latest", "Image=ghcr.io/bcrisp4/bns:latest"),
        ("v1.2.3-rc4", "Image=ghcr.io/bcrisp4/bns:v1.2.3-rc4"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "bns_image_tag": tag})
    assert expected in out


def test_quadlet_section_order() -> None:
    """[Unit] before [Container] before [Service] before [Install]."""
    out = _render_quadlet(BASE_DATA)
    positions = [out.index(s) for s in ("[Unit]", "[Container]", "[Service]", "[Install]")]
    assert positions == sorted(positions), f"section order wrong: {positions}"
