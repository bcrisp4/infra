"""Unit tests for tasks.pi5_exporter pure renderer."""

import pytest

from tasks.pi5_exporter import FIRMWARE_SYSFS, VCIO_DEVICE, _render_quadlet

BASE_DATA: dict = {
    "pi5_exporter_image": "ghcr.io/bcrisp4/pi5_exporter",
    "pi5_exporter_image_tag": "0.1.0",
    "pi5_exporter_port": 2712,
    "pi5_exporter_collection_interval": "10s",
    "pi5_exporter_video_gid": 44,
    "pi5_exporter_memory_max": "64M",
    "pi5_exporter_memory_high": "48M",
    "pi5_exporter_cpu_quota": "50%",
    "pi5_exporter_tasks_max": 64,
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
    assert "Image=ghcr.io/bcrisp4/pi5_exporter:0.1.0" in out


def test_quadlet_sets_container_name() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "ContainerName=pi5-exporter" in out


def test_quadlet_joins_monitoring_network_only() -> None:
    """Scraped by Prometheus over the monitoring network by ContainerName; no
    host networking and no published port."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=monitoring.network" in out
    assert "Network=host" not in out
    assert "Network=rendering.network" not in out


def test_quadlet_publishes_no_host_port() -> None:
    """No PublishPort: reachable only by Prometheus over the monitoring network,
    never the host, LAN or Tailscale."""
    out = _render_quadlet(BASE_DATA)
    assert "PublishPort" not in out


def test_quadlet_adds_vcio_device() -> None:
    """Firmware mailbox device must be passed in for the firmware collectors."""
    out = _render_quadlet(BASE_DATA)
    assert f"AddDevice={VCIO_DEVICE}" in out


def test_quadlet_adds_video_group() -> None:
    """The non-root image user needs the host `video` GID to open /dev/vcio."""
    out = _render_quadlet(BASE_DATA)
    assert "GroupAdd=44" in out


@pytest.mark.parametrize("gid", [44, 39])
def test_quadlet_video_gid_tracks_data(gid: int) -> None:
    out = _render_quadlet({**BASE_DATA, "pi5_exporter_video_gid": gid})
    assert f"GroupAdd={gid}" in out


def test_quadlet_unmasks_firmware_sysfs() -> None:
    """podman masks /sys/firmware by default; unmasked so the pi5_board_info
    metric can read the device tree (kept for the full collector set)."""
    out = _render_quadlet(BASE_DATA)
    assert f"Unmask={FIRMWARE_SYSFS}" in out


def test_quadlet_device_and_group_are_native_keys() -> None:
    """AddDevice/GroupAdd are native quadlet keys; they must not be smuggled
    through PodmanArgs."""
    out = _render_quadlet(BASE_DATA)
    assert "PodmanArgs" not in out


def test_quadlet_sets_listen_address_from_port() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--web.listen-address=:2712" in out


@pytest.mark.parametrize(
    ("port", "expected"),
    [
        (2712, "--web.listen-address=:2712"),
        (12712, "--web.listen-address=:12712"),
    ],
)
def test_quadlet_port_variants(port: int, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "pi5_exporter_port": port})
    assert expected in out


def test_quadlet_sets_collection_interval() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--collection.interval=10s" in out


@pytest.mark.parametrize("interval", ["5s", "10s", "12s"])
def test_quadlet_collection_interval_tracks_data(interval: str) -> None:
    out = _render_quadlet({**BASE_DATA, "pi5_exporter_collection_interval": interval})
    assert f"--collection.interval={interval}" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=64M" in out
    assert "MemoryHigh=48M" in out
    assert "CPUQuota=50%" in out
    assert "TasksMax=64" in out
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
