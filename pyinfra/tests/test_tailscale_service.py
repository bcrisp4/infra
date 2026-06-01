"""Unit tests for tasks.tailscale_service pure renderer + helpers."""

import json

import pytest

from tasks.tailscale_service import (
    CONFIG_VERSION,
    _config_path,
    _render_serve_config,
)


def test_config_is_valid_json() -> None:
    json.loads(_render_serve_config(443, 9090))


def test_config_version() -> None:
    parsed = json.loads(_render_serve_config(443, 9090))
    assert parsed["version"] == CONFIG_VERSION


def test_config_is_flattened_single_service_form() -> None:
    """set-config --service consumes the flattened form: version + endpoints,
    no `services` wrapper (the service is named by the CLI flag)."""
    parsed = json.loads(_render_serve_config(443, 9090))
    assert "services" not in parsed
    assert set(parsed) == {"version", "endpoints"}


def test_config_tcp_endpoint_targets_loopback_backend() -> None:
    parsed = json.loads(_render_serve_config(443, 9090))
    assert parsed["endpoints"]["tcp:443"] == "http://127.0.0.1:9090"


@pytest.mark.parametrize("backend_port", [9090, 3000, 19090])
def test_config_backend_tracks_backend_port(backend_port: int) -> None:
    parsed = json.loads(_render_serve_config(443, backend_port))
    assert parsed["endpoints"]["tcp:443"] == f"http://127.0.0.1:{backend_port}"


def test_config_https_port_substituted() -> None:
    parsed = json.loads(_render_serve_config(8443, 9090))
    assert "tcp:8443" in parsed["endpoints"]


def test_config_backend_is_plain_http() -> None:
    """tailscaled terminates TLS; the backend must be plain HTTP."""
    parsed = json.loads(_render_serve_config(443, 9090))
    assert next(iter(parsed["endpoints"].values())).startswith("http://")


def test_config_terminates_with_single_newline() -> None:
    out = _render_serve_config(443, 9090)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_config_is_deterministic() -> None:
    assert _render_serve_config(443, 9090) == _render_serve_config(443, 9090)


@pytest.mark.parametrize(
    ("service_name", "expected"),
    [
        ("svc:prometheus", "/etc/tailscale/serve-prometheus.json"),
        ("svc:grafana", "/etc/tailscale/serve-grafana.json"),
    ],
)
def test_config_path_per_service(service_name: str, expected: str) -> None:
    assert _config_path(service_name) == expected
