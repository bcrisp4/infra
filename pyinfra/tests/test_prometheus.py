"""Unit tests for tasks.prometheus pure renderers."""

import pytest

from tasks.prometheus import (
    CONFIG_PATH,
    CONTAINER_DATA_DIR,
    CONTAINER_PORT,
    DATA_DIR,
    _render_config,
    _render_quadlet,
)

BASE_DATA: dict = {
    "prometheus_image": "quay.io/prometheus/prometheus",
    "prometheus_image_tag": "v3.12.0-distroless",
    "prometheus_host_port": 9090,
    "prometheus_scrape_interval": "15s",
    "prometheus_retention_time": "30d",
    "prometheus_retention_size": "8GB",
    "prometheus_memory_max": "1G",
    "prometheus_memory_high": "768M",
    "prometheus_cpu_quota": "200%",
    "prometheus_tasks_max": 4096,
    "bns_listen_address": "192.168.1.2",
    "bns_host_port_admin": 9053,
    "nodeexporter_host_port": 9100,
    "node_name": "rpi5-4cpu-16gb-home-1",
}


# ---------- _render_config ----------


def test_config_global_uses_scrape_interval() -> None:
    out = _render_config(BASE_DATA)
    assert "global:" in out
    assert "  scrape_interval: 15s" in out
    assert "  evaluation_interval: 15s" in out


def test_config_has_self_scrape_job() -> None:
    out = _render_config(BASE_DATA)
    assert "  - job_name: prometheus" in out
    assert f"      - targets: ['localhost:{CONTAINER_PORT}']" in out


def test_config_bns_job_uses_lan_ip_and_admin_port() -> None:
    """bns binds its LAN IP only, so it is scraped there, not via the gateway."""
    out = _render_config(BASE_DATA)
    assert "  - job_name: bns" in out
    assert "      - targets: ['192.168.1.2:9053']" in out


@pytest.mark.parametrize("port", [9053, 9090, 19090])
def test_config_bns_target_tracks_admin_port(port: int) -> None:
    out = _render_config({**BASE_DATA, "bns_host_port_admin": port})
    assert f"      - targets: ['192.168.1.2:{port}']" in out


@pytest.mark.parametrize("address", ["192.168.1.2", "10.0.0.5"])
def test_config_bns_target_tracks_listen_address(address: str) -> None:
    out = _render_config({**BASE_DATA, "bns_listen_address": address})
    assert f"      - targets: ['{address}:9053']" in out


def test_config_nodeexporter_job_uses_host_containers_internal() -> None:
    out = _render_config(BASE_DATA)
    assert "  - job_name: node-exporter" in out
    assert "      - targets: ['host.containers.internal:9100']" in out


@pytest.mark.parametrize("port", [9100, 19100])
def test_config_nodeexporter_target_tracks_host_port(port: int) -> None:
    out = _render_config({**BASE_DATA, "nodeexporter_host_port": port})
    assert f"      - targets: ['host.containers.internal:{port}']" in out


def test_config_nodeexporter_instance_relabelled_to_node_name() -> None:
    """The scrape address is host.containers.internal, but instance should read
    as the node's short hostname."""
    out = _render_config(BASE_DATA)
    assert "        labels: {instance: 'rpi5-4cpu-16gb-home-1'}" in out


@pytest.mark.parametrize("name", ["rpi5-4cpu-16gb-home-1", "htz-fsn1-prod-1"])
def test_config_nodeexporter_instance_tracks_node_name(name: str) -> None:
    out = _render_config({**BASE_DATA, "node_name": name})
    assert f"        labels: {{instance: '{name}'}}" in out


def test_config_has_grafana_job() -> None:
    """Grafana is scraped over the monitoring bridge by ContainerName."""
    out = _render_config(BASE_DATA)
    assert "  - job_name: grafana" in out
    assert "      - targets: ['grafana:3000']" in out


def test_config_grafana_instance_relabelled_to_node_name() -> None:
    """The scrape address is the container name, but instance should read as the
    node's short hostname."""
    out = _render_config(BASE_DATA)
    grafana_block = out.split("  - job_name: grafana", 1)[1]
    assert "        labels: {instance: 'rpi5-4cpu-16gb-home-1'}" in grafana_block


@pytest.mark.parametrize("name", ["rpi5-4cpu-16gb-home-1", "htz-fsn1-prod-1"])
def test_config_grafana_instance_tracks_node_name(name: str) -> None:
    out = _render_config({**BASE_DATA, "node_name": name})
    grafana_block = out.split("  - job_name: grafana", 1)[1]
    assert f"        labels: {{instance: '{name}'}}" in grafana_block


@pytest.mark.parametrize("interval", ["10s", "15s", "1m"])
def test_config_scrape_interval_substituted(interval: str) -> None:
    out = _render_config({**BASE_DATA, "prometheus_scrape_interval": interval})
    assert f"  scrape_interval: {interval}" in out
    assert f"  evaluation_interval: {interval}" in out


def test_config_terminates_with_single_newline() -> None:
    out = _render_config(BASE_DATA)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_config_is_deterministic() -> None:
    assert _render_config(BASE_DATA) == _render_config(BASE_DATA)


# ---------- _render_quadlet ----------


def test_quadlet_has_all_required_sections() -> None:
    out = _render_quadlet(BASE_DATA)
    for section in ("[Unit]", "[Container]", "[Service]", "[Install]"):
        assert section in out, f"missing section {section}"


def test_quadlet_section_order() -> None:
    """[Unit] before [Container] before [Service] before [Install]."""
    out = _render_quadlet(BASE_DATA)
    positions = [out.index(s) for s in ("[Unit]", "[Container]", "[Service]", "[Install]")]
    assert positions == sorted(positions), f"section order wrong: {positions}"


def test_quadlet_pins_image_with_tag() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Image=quay.io/prometheus/prometheus:v3.12.0-distroless" in out


def test_quadlet_joins_monitoring_network() -> None:
    """Prometheus shares the monitoring bridge so Grafana resolves it by name."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=monitoring.network" in out


def test_quadlet_publishes_host_port_loopback_only() -> None:
    """Bound to 127.0.0.1 only: reachable solely via the Tailscale service.
    No LAN (0.0.0.0) or raw-Tailscale-IP ([::]) exposure."""
    out = _render_quadlet(BASE_DATA)
    assert f"PublishPort=127.0.0.1:9090:{CONTAINER_PORT}/tcp" in out
    assert f"PublishPort=9090:{CONTAINER_PORT}/tcp" not in out
    assert f"PublishPort=[::]:9090:{CONTAINER_PORT}/tcp" not in out


def test_quadlet_publishes_custom_host_port() -> None:
    out = _render_quadlet({**BASE_DATA, "prometheus_host_port": 19090})
    assert f"PublishPort=127.0.0.1:19090:{CONTAINER_PORT}/tcp" in out


def test_quadlet_bind_mounts_config_readonly() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={CONFIG_PATH}:{CONFIG_PATH}:ro" in out


def test_quadlet_bind_mounts_data_dir() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}" in out
    # Read-only must NOT be applied to the data dir.
    assert f"Volume={DATA_DIR}:{CONTAINER_DATA_DIR}:ro" not in out


def test_quadlet_exec_config_and_tsdb_path() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"--config.file={CONFIG_PATH}" in out
    assert f"--storage.tsdb.path={CONTAINER_DATA_DIR}" in out
    assert f"--web.listen-address=0.0.0.0:{CONTAINER_PORT}" in out


def test_quadlet_exec_carries_retention_flags() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--storage.tsdb.retention.time=30d" in out
    assert "--storage.tsdb.retention.size=8GB" in out


def test_quadlet_retention_flags_track_data() -> None:
    out = _render_quadlet(
        {**BASE_DATA, "prometheus_retention_time": "90d", "prometheus_retention_size": "16GB"}
    )
    assert "--storage.tsdb.retention.time=90d" in out
    assert "--storage.tsdb.retention.size=16GB" in out


def test_quadlet_does_not_enable_web_lifecycle() -> None:
    """Reload is via SIGHUP; the HTTP /-/reload endpoint stays disabled."""
    out = _render_quadlet(BASE_DATA)
    assert "--web.enable-lifecycle" not in out


def test_quadlet_resource_caps_in_service_section() -> None:
    """Cgroup ceilings live in [Service] (systemd-native), not [Container]
    (podman-native), so the unit works on podman < 5.5 too."""
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=1G" in out
    assert "MemoryHigh=768M" in out
    assert "CPUQuota=200%" in out
    assert "TasksMax=4096" in out
    for forbidden in ("Memory=", "MemoryReservation=", "CPUS=", "PidsLimit="):
        assert forbidden not in out, f"forbidden quadlet key emitted: {forbidden!r}"
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
    out = _render_quadlet(BASE_DATA)
    assert "Restart=always" in out
    assert "Restart=on-failure" not in out
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
        ("v3.12.0-distroless", "Image=quay.io/prometheus/prometheus:v3.12.0-distroless"),
        ("v3.12.0", "Image=quay.io/prometheus/prometheus:v3.12.0"),
        ("latest", "Image=quay.io/prometheus/prometheus:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "prometheus_image_tag": tag})
    assert expected in out
