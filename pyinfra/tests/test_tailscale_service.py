"""Unit tests for tasks.tailscale_service pure renderer."""

import json

from tasks.tailscale_service import CONFIG_VERSION, _render_serve_config

BASE_DATA: dict = {
    "tailscale_serve_service_name": "svc:prometheus",
    "tailscale_serve_https_port": 443,
    "prometheus_host_port": 9090,
}


def test_config_is_valid_json() -> None:
    json.loads(_render_serve_config(BASE_DATA))


def test_config_version() -> None:
    parsed = json.loads(_render_serve_config(BASE_DATA))
    assert parsed["version"] == CONFIG_VERSION


def test_config_is_flattened_single_service_form() -> None:
    """set-config --service consumes the flattened form: version + endpoints,
    no `services` wrapper (the service is named by the CLI flag)."""
    parsed = json.loads(_render_serve_config(BASE_DATA))
    assert "services" not in parsed
    assert set(parsed) == {"version", "endpoints"}


def test_config_tcp_endpoint_targets_loopback_backend() -> None:
    parsed = json.loads(_render_serve_config(BASE_DATA))
    assert parsed["endpoints"]["tcp:443"] == "http://127.0.0.1:9090"


def test_config_backend_tracks_prometheus_host_port() -> None:
    parsed = json.loads(_render_serve_config({**BASE_DATA, "prometheus_host_port": 19090}))
    assert parsed["endpoints"]["tcp:443"] == "http://127.0.0.1:19090"


def test_config_https_port_substituted() -> None:
    parsed = json.loads(_render_serve_config({**BASE_DATA, "tailscale_serve_https_port": 8443}))
    assert "tcp:8443" in parsed["endpoints"]


def test_config_backend_is_plain_http() -> None:
    """tailscaled terminates TLS; the backend must be plain HTTP."""
    parsed = json.loads(_render_serve_config(BASE_DATA))
    assert list(parsed["endpoints"].values())[0].startswith("http://")


def test_config_terminates_with_single_newline() -> None:
    out = _render_serve_config(BASE_DATA)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_config_is_deterministic() -> None:
    assert _render_serve_config(BASE_DATA) == _render_serve_config(BASE_DATA)
