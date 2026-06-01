"""Unit tests for tasks.image_renderer pure renderer."""

import pytest

from tasks.image_renderer import TOKEN_FILE, _render_quadlet

BASE_DATA: dict = {
    "grafana_image_renderer_image": "docker.io/grafana/grafana-image-renderer",
    "grafana_image_renderer_image_tag": "v5.8.8",
    "grafana_image_renderer_memory_max": "1G",
    "grafana_image_renderer_memory_high": "768M",
    "grafana_image_renderer_cpu_quota": "150%",
    "grafana_image_renderer_tasks_max": 4096,
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
    assert "Image=docker.io/grafana/grafana-image-renderer:v5.8.8" in out


def test_quadlet_sets_container_name() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "ContainerName=grafana-image-renderer" in out


def test_quadlet_joins_rendering_network_only() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "Network=rendering.network" in out
    assert "Network=monitoring.network" not in out


def test_quadlet_publishes_no_host_port() -> None:
    """No PublishPort: the renderer is reachable only by Grafana over the
    rendering network, never the host, LAN or Tailscale."""
    out = _render_quadlet(BASE_DATA)
    assert "PublishPort" not in out


def test_quadlet_loads_token_env_file() -> None:
    """Auth token (AUTH_TOKEN) comes from the shared host-generated env file."""
    out = _render_quadlet(BASE_DATA)
    assert f"EnvironmentFile={TOKEN_FILE}" in out


def test_quadlet_resource_caps_in_service_section() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=1G" in out
    assert "MemoryHigh=768M" in out
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


def test_quadlet_extends_start_timeout_for_image_pull() -> None:
    """First start pulls the large image inline; the default 90s is too short."""
    out = _render_quadlet(BASE_DATA)
    assert "TimeoutStartSec=600s" in out


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
        ("v5.8.8", "Image=docker.io/grafana/grafana-image-renderer:v5.8.8"),
        ("latest", "Image=docker.io/grafana/grafana-image-renderer:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "grafana_image_renderer_image_tag": tag})
    assert expected in out
