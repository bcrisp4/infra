"""Unit tests for tasks.tailscale_service pure renderers + helpers."""

import pytest

from tasks.tailscale_service import (
    _backend_url,
    _legacy_config_path,
    _render_state,
    _state_path,
)


@pytest.mark.parametrize("port", [9090, 3000, 19090])
def test_backend_url_is_loopback_http(port: int) -> None:
    assert _backend_url(port) == f"http://127.0.0.1:{port}"


@pytest.mark.parametrize(
    ("service_name", "expected"),
    [
        ("svc:prometheus", "/etc/tailscale/serve-prometheus.state"),
        ("svc:grafana", "/etc/tailscale/serve-grafana.state"),
    ],
)
def test_state_path_per_service(service_name: str, expected: str) -> None:
    assert _state_path(service_name) == expected


@pytest.mark.parametrize(
    ("service_name", "expected"),
    [
        ("svc:prometheus", "/etc/tailscale/serve-prometheus.json"),
        ("svc:grafana", "/etc/tailscale/serve-grafana.json"),
    ],
)
def test_legacy_config_path_per_service(service_name: str, expected: str) -> None:
    assert _legacy_config_path(service_name) == expected


def test_state_records_service_https_port_and_backend() -> None:
    out = _render_state("svc:grafana", 443, 3000)
    assert "service=svc:grafana" in out
    assert "https_port=443" in out
    assert "backend=http://127.0.0.1:3000" in out


@pytest.mark.parametrize("backend_port", [9090, 3000])
def test_state_backend_tracks_backend_port(backend_port: int) -> None:
    out = _render_state("svc:prometheus", 443, backend_port)
    assert f"backend=http://127.0.0.1:{backend_port}" in out


@pytest.mark.parametrize("https_port", [443, 8443])
def test_state_https_port_substituted(https_port: int) -> None:
    out = _render_state("svc:grafana", https_port, 3000)
    assert f"https_port={https_port}" in out


def test_state_terminates_with_single_newline() -> None:
    out = _render_state("svc:grafana", 443, 3000)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_state_is_deterministic() -> None:
    assert _render_state("svc:grafana", 443, 3000) == _render_state("svc:grafana", 443, 3000)
