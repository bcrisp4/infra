"""Unit tests for tasks.grafana pure renderers."""

import pytest

from tasks.grafana import (
    DATA_DIR,
    DATASOURCE_PATH,
    CONTAINER_PORT,
    _render_datasource,
    _render_quadlet,
)

BASE_DATA: dict = {
    "grafana_image": "docker.io/grafana/grafana-oss",
    "grafana_image_tag": "13.0.1",
    "grafana_host_port": 3000,
    "grafana_root_url": "https://grafana.marlin-tet.ts.net",
    "grafana_memory_max": "512M",
    "grafana_memory_high": "384M",
    "grafana_cpu_quota": "150%",
    "grafana_tasks_max": 4096,
    "prometheus_host_port": 9090,
}


# ---------- _render_datasource ----------


def test_datasource_api_version() -> None:
    out = _render_datasource(BASE_DATA)
    assert "apiVersion: 1" in out


def test_datasource_is_prometheus_type() -> None:
    out = _render_datasource(BASE_DATA)
    assert "  - name: Prometheus" in out
    assert "    type: prometheus" in out
    assert "    access: proxy" in out


def test_datasource_targets_container_name_on_monitoring_net() -> None:
    """Grafana reaches Prometheus by ContainerName over the shared monitoring
    network (aardvark-dns), not via loopback or host.containers.internal."""
    out = _render_datasource(BASE_DATA)
    assert "    url: http://prometheus:9090" in out


@pytest.mark.parametrize("port", [9090, 19090])
def test_datasource_url_tracks_prometheus_host_port(port: int) -> None:
    out = _render_datasource({**BASE_DATA, "prometheus_host_port": port})
    assert f"    url: http://prometheus:{port}" in out


def test_datasource_is_default() -> None:
    out = _render_datasource(BASE_DATA)
    assert "    isDefault: true" in out


def test_datasource_terminates_with_single_newline() -> None:
    out = _render_datasource(BASE_DATA)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_datasource_is_deterministic() -> None:
    assert _render_datasource(BASE_DATA) == _render_datasource(BASE_DATA)


# ---------- _render_quadlet ----------


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
    assert "Image=docker.io/grafana/grafana-oss:13.0.1" in out


def test_quadlet_joins_monitoring_network() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Network=monitoring.network" in out


def test_quadlet_publishes_host_port_loopback_only() -> None:
    """Loopback only: reachable solely via the Tailscale service. No LAN
    (0.0.0.0) or raw-Tailscale-IP ([::]) exposure."""
    out = _render_quadlet(BASE_DATA)
    assert f"PublishPort=127.0.0.1:3000:{CONTAINER_PORT}/tcp" in out
    assert f"PublishPort=3000:{CONTAINER_PORT}/tcp" not in out
    assert f"PublishPort=[::]:3000:{CONTAINER_PORT}/tcp" not in out


def test_quadlet_publishes_custom_host_port() -> None:
    out = _render_quadlet({**BASE_DATA, "grafana_host_port": 13000})
    assert f"PublishPort=127.0.0.1:13000:{CONTAINER_PORT}/tcp" in out


def test_quadlet_bind_mounts_data_dir_writable() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={DATA_DIR}:{DATA_DIR}" in out
    assert f"Volume={DATA_DIR}:{DATA_DIR}:ro" not in out


def test_quadlet_bind_mounts_datasource_readonly() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={DATASOURCE_PATH}:" in out
    assert ":ro" in out.split(f"Volume={DATASOURCE_PATH}:", 1)[1].splitlines()[0]


def test_quadlet_sets_root_url() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=GF_SERVER_ROOT_URL=https://grafana.marlin-tet.ts.net" in out


def test_quadlet_sets_server_domain() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=GF_SERVER_DOMAIN=grafana.marlin-tet.ts.net" in out


def test_quadlet_enables_sqlite_wal() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=GF_DATABASE_WAL=true" in out


def test_quadlet_disables_phone_home() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Environment=GF_ANALYTICS_REPORTING_ENABLED=false" in out
    assert "Environment=GF_ANALYTICS_CHECK_FOR_UPDATES=false" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=512M" in out
    assert "MemoryHigh=384M" in out
    assert "CPUQuota=150%" in out
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
        ("13.0.1", "Image=docker.io/grafana/grafana-oss:13.0.1"),
        ("13.0.1-ubuntu", "Image=docker.io/grafana/grafana-oss:13.0.1-ubuntu"),
        ("latest", "Image=docker.io/grafana/grafana-oss:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "grafana_image_tag": tag})
    assert expected in out
