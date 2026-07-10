"""Unit tests for tasks.bscribe pure renderer."""

import pytest

from tasks.bscribe import (
    CONTAINER_DATA_DIR,
    CONTAINER_PORT,
    DATA_VOLUME,
    _render_quadlet,
)

BASE_DATA: dict = {
    "bscribe_image": "ghcr.io/bcrisp4/bscribe",
    "bscribe_image_tag": "0.3.0",
    "bscribe_host_port": 8000,
    "bscribe_metrics_port": 9090,
    "bscribe_worker_count": 4,
    "bscribe_memory_max": "2G",
    "bscribe_memory_high": "1536M",
    "bscribe_cpu_quota": "400%",
    "bscribe_tasks_max": 4096,
}


def test_quadlet_has_all_required_sections() -> None:
    out = _render_quadlet(BASE_DATA)
    for section in ("[Unit]", "[Container]", "[Service]", "[Install]"):
        assert section in out, f"missing section {section}"


def test_quadlet_section_order() -> None:
    out = _render_quadlet(BASE_DATA)
    positions = [
        out.index(s) for s in ("[Unit]", "[Container]", "[Service]", "[Install]")
    ]
    assert positions == sorted(positions), f"section order wrong: {positions}"


def test_quadlet_pins_image_with_tag() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Image=ghcr.io/bcrisp4/bscribe:0.3.0" in out


def test_quadlet_joins_monitoring_network() -> None:
    """bscribe shares the monitoring bridge so Prometheus scrapes it by name; a
    user-defined network still NATs outbound."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=monitoring.network" in out


def test_quadlet_publishes_host_port_loopback_only() -> None:
    """Loopback only: reachable solely via the Tailscale service. No LAN
    (0.0.0.0) or raw-Tailscale-IP ([::]) exposure."""
    out = _render_quadlet(BASE_DATA)
    assert f"PublishPort=127.0.0.1:8000:{CONTAINER_PORT}/tcp" in out
    assert f"PublishPort=8000:{CONTAINER_PORT}/tcp" not in out
    assert f"PublishPort=[::]:8000:{CONTAINER_PORT}/tcp" not in out


def test_quadlet_publishes_custom_host_port() -> None:
    out = _render_quadlet({**BASE_DATA, "bscribe_host_port": 18000})
    assert f"PublishPort=127.0.0.1:18000:{CONTAINER_PORT}/tcp" in out


def test_quadlet_mounts_named_volume_writable() -> None:
    """The SQLite DB lives in a named volume, mounted writable (no :ro)."""
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={DATA_VOLUME}:{CONTAINER_DATA_DIR}" in out
    assert f"Volume={DATA_VOLUME}:{CONTAINER_DATA_DIR}:ro" not in out


def test_quadlet_hardening_keys_present() -> None:
    """Hardened run contract: read-only rootfs + mandatory writable /tmp, no
    privilege escalation, all capabilities dropped."""
    out = _render_quadlet(BASE_DATA)
    assert "Tmpfs=/tmp" in out
    assert "ReadOnly=true" in out
    assert "NoNewPrivileges=true" in out
    assert "DropCapability=all" in out


def test_quadlet_sets_metrics_port() -> None:
    """Separate Prometheus metrics listener on the configured port."""
    out = _render_quadlet(BASE_DATA)
    assert "Environment=BSCRIBE_METRICS_PORT=9090" in out


@pytest.mark.parametrize("port", [9090, 19090])
def test_quadlet_metrics_port_tracks_data(port: int) -> None:
    out = _render_quadlet({**BASE_DATA, "bscribe_metrics_port": port})
    assert f"Environment=BSCRIBE_METRICS_PORT={port}" in out


def test_quadlet_does_not_publish_metrics_port() -> None:
    """The metrics port is reachable only over the monitoring bridge; it must
    never be published to the host (no LAN/Tailscale exposure)."""
    out = _render_quadlet(BASE_DATA)
    assert "PublishPort=127.0.0.1:9090" not in out
    assert ":9090:9090" not in out


def test_quadlet_sets_worker_count_and_log_level() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=BSCRIBE_WORKER_COUNT=4" in out
    assert "Environment=BSCRIBE_LOG_LEVEL=INFO" in out


@pytest.mark.parametrize("workers", [1, 4, 8])
def test_quadlet_worker_count_tracks_data(workers: int) -> None:
    out = _render_quadlet({**BASE_DATA, "bscribe_worker_count": workers})
    assert f"Environment=BSCRIBE_WORKER_COUNT={workers}" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=2G" in out
    assert "MemoryHigh=1536M" in out
    assert "CPUQuota=400%" in out
    assert "TasksMax=4096" in out
    for forbidden in ("Memory=", "MemoryReservation=", "CPUS=", "PidsLimit="):
        assert forbidden not in out, f"forbidden quadlet key emitted: {forbidden!r}"
    container_block = out.split("[Container]", 1)[1].split("[Service]", 1)[0]
    for key in ("MemoryMax", "MemoryHigh", "CPUQuota", "TasksMax"):
        assert key not in container_block, f"{key} should not be in [Container]"


def test_quadlet_install_target_is_multi_user() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "WantedBy=multi-user.target" in out
    assert "WantedBy=default.target" not in out


def test_quadlet_restart_policy_always() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Restart=always" in out
    assert "RestartSec=5s" in out


def test_quadlet_start_limits_present() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "StartLimitIntervalSec=60s" in out
    assert "StartLimitBurst=10" in out


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
        ("0.3.0", "Image=ghcr.io/bcrisp4/bscribe:0.3.0"),
        ("0.3", "Image=ghcr.io/bcrisp4/bscribe:0.3"),
        ("latest", "Image=ghcr.io/bcrisp4/bscribe:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "bscribe_image_tag": tag})
    assert expected in out
