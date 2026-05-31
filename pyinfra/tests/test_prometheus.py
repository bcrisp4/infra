"""Unit tests for tasks.prometheus pure renderers."""

import pytest

from tasks.prometheus import (
    CONFIG_PATH,
    CONTAINER_DATA_DIR,
    CONTAINER_PORT,
    _render_config,
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
    "bns_host_port_admin": 9053,
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


def test_config_bns_job_uses_host_containers_internal_and_admin_port() -> None:
    out = _render_config(BASE_DATA)
    assert "  - job_name: bns" in out
    assert "      - targets: ['host.containers.internal:9053']" in out


@pytest.mark.parametrize("port", [9053, 9090, 19090])
def test_config_bns_target_tracks_admin_port(port: int) -> None:
    out = _render_config({**BASE_DATA, "bns_host_port_admin": port})
    assert f"      - targets: ['host.containers.internal:{port}']" in out


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
