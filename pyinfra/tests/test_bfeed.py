"""Unit tests for tasks.bfeed pure renderer."""

import pytest

from tasks.bfeed import (
    CONTAINER_DATA_DIR,
    CONTAINER_PORT,
    DATA_DIR,
    _render_quadlet,
)

BASE_DATA: dict = {
    "bfeed_image": "ghcr.io/bcrisp4/bfeed",
    "bfeed_image_tag": "0.1.0",
    "bfeed_host_port": 8080,
    "bfeed_base_url": "https://bfeed.marlin-tet.ts.net",
    "bfeed_memory_max": "256M",
    "bfeed_memory_high": "192M",
    "bfeed_cpu_quota": "100%",
    "bfeed_tasks_max": 1024,
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
    assert "Image=ghcr.io/bcrisp4/bfeed:0.1.0" in out


def test_quadlet_joins_no_user_defined_network() -> None:
    """bfeed stays on the default podman bridge (outbound NAT for feed polling);
    it reaches no other container, so it joins none of the named networks."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=" not in out


def test_quadlet_publishes_host_port_loopback_only() -> None:
    """Loopback only: reachable solely via the Tailscale service. No LAN
    (0.0.0.0) or raw-Tailscale-IP ([::]) exposure."""
    out = _render_quadlet(BASE_DATA)
    assert f"PublishPort=127.0.0.1:8080:{CONTAINER_PORT}/tcp" in out
    assert f"PublishPort=8080:{CONTAINER_PORT}/tcp" not in out
    assert f"PublishPort=[::]:8080:{CONTAINER_PORT}/tcp" not in out


def test_quadlet_publishes_custom_host_port() -> None:
    out = _render_quadlet({**BASE_DATA, "bfeed_host_port": 18080})
    assert f"PublishPort=127.0.0.1:18080:{CONTAINER_PORT}/tcp" in out


def test_quadlet_bind_mounts_data_dir_writable() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}" in out
    assert f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}:ro" not in out


def test_quadlet_sets_mandatory_base_url() -> None:
    """BFEED_BASE_URL must be the public MagicDNS URL (bfeed exits without it)."""
    out = _render_quadlet(BASE_DATA)
    assert "Environment=BFEED_BASE_URL=https://bfeed.marlin-tet.ts.net" in out


@pytest.mark.parametrize(
    "base_url",
    ["https://bfeed.marlin-tet.ts.net", "https://feeds.example.test"],
)
def test_quadlet_base_url_tracks_host_data(base_url: str) -> None:
    out = _render_quadlet({**BASE_DATA, "bfeed_base_url": base_url})
    assert f"Environment=BFEED_BASE_URL={base_url}" in out


def test_quadlet_sets_json_logging() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=BFEED_LOG_FORMAT=json" in out
    assert "Environment=BFEED_LOG_LEVEL=info" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=256M" in out
    assert "MemoryHigh=192M" in out
    assert "CPUQuota=100%" in out
    assert "TasksMax=1024" in out
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
        ("0.1.0", "Image=ghcr.io/bcrisp4/bfeed:0.1.0"),
        ("0.1", "Image=ghcr.io/bcrisp4/bfeed:0.1"),
        ("latest", "Image=ghcr.io/bcrisp4/bfeed:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "bfeed_image_tag": tag})
    assert expected in out
