"""Unit tests for tasks.podman_exporter pure renderer."""

import pytest

from tasks.podman_exporter import SOCKET_PATH, _render_quadlet

BASE_DATA: dict = {
    "podman_exporter_image": "quay.io/navidys/prometheus-podman-exporter",
    "podman_exporter_image_tag": "v1.21.0",
    "podman_exporter_port": 9882,
    "podman_exporter_memory_max": "128M",
    "podman_exporter_memory_high": "96M",
    "podman_exporter_cpu_quota": "50%",
    "podman_exporter_tasks_max": 256,
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
    assert "Image=quay.io/navidys/prometheus-podman-exporter:v1.21.0" in out


def test_quadlet_sets_container_name() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "ContainerName=podman-exporter" in out


def test_quadlet_joins_monitoring_network_only() -> None:
    """Scraped by Prometheus over the monitoring network by ContainerName; no
    host networking is needed because podman is reached over its unix socket."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=monitoring.network" in out
    assert "Network=host" not in out
    assert "Network=rendering.network" not in out


def test_quadlet_publishes_no_host_port() -> None:
    """No PublishPort: the exporter is reachable only by Prometheus over the
    monitoring network, never the host, LAN or Tailscale."""
    out = _render_quadlet(BASE_DATA)
    assert "PublishPort" not in out


def test_quadlet_mounts_podman_socket() -> None:
    """The exporter talks to podman over its rootful unix socket, not the net."""
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={SOCKET_PATH}:{SOCKET_PATH}" in out


def test_quadlet_sets_container_host_env() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Environment=CONTAINER_HOST=unix://{SOCKET_PATH}" in out


def test_quadlet_runs_as_root() -> None:
    """Rootful socket access requires the container to run as root (-u root)."""
    out = _render_quadlet(BASE_DATA)
    assert "User=root" in out


def test_quadlet_requires_podman_socket() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Requires=podman.socket" in out
    assert "After=podman.socket" in out


def test_quadlet_enables_enhanced_metrics() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--collector.enhance-metrics" in out


def test_quadlet_sets_listen_address_from_port() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--web.listen-address=:9882" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=128M" in out
    assert "MemoryHigh=96M" in out
    assert "CPUQuota=50%" in out
    assert "TasksMax=256" in out
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
    ("port", "expected"),
    [
        (9882, "--web.listen-address=:9882"),
        (19882, "--web.listen-address=:19882"),
    ],
)
def test_quadlet_port_variants(port: int, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "podman_exporter_port": port})
    assert expected in out
