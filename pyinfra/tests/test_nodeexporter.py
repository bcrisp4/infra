"""Unit tests for tasks.nodeexporter pure renderer."""

import pytest

from tasks.nodeexporter import (
    CONTAINER_PORT,
    HOST_ROOTFS_MOUNT,
    _render_quadlet,
)

BASE_DATA: dict = {
    "nodeexporter_image": "quay.io/prometheus/node-exporter",
    "nodeexporter_image_tag": "v1.11.1",
    "nodeexporter_host_port": 9100,
    "nodeexporter_memory_max": "128M",
    "nodeexporter_memory_high": "96M",
    "nodeexporter_cpu_quota": "50%",
    "nodeexporter_tasks_max": 1024,
}


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
    assert "Image=quay.io/prometheus/node-exporter:v1.11.1" in out


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.11.1", "Image=quay.io/prometheus/node-exporter:v1.11.1"),
        ("v1.9.1", "Image=quay.io/prometheus/node-exporter:v1.9.1"),
        ("latest", "Image=quay.io/prometheus/node-exporter:latest"),
    ],
)
def test_quadlet_image_tag_variants(tag: str, expected: str) -> None:
    out = _render_quadlet({**BASE_DATA, "nodeexporter_image_tag": tag})
    assert expected in out


def test_quadlet_uses_host_namespaces() -> None:
    """Host net + pid so metrics describe the Pi, not the container. PID has no
    dedicated quadlet key on podman 5.4, so it goes via PodmanArgs."""
    out = _render_quadlet(BASE_DATA)
    assert "Network=host" in out
    assert "PodmanArgs=--pid=host" in out
    assert "PidMode=" not in out


def test_quadlet_mounts_host_rootfs_readonly() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"Volume=/:{HOST_ROOTFS_MOUNT}:ro,rslave" in out


def test_quadlet_exec_sets_path_rootfs() -> None:
    out = _render_quadlet(BASE_DATA)
    assert f"--path.rootfs={HOST_ROOTFS_MOUNT}" in out


def test_quadlet_binds_all_interfaces_on_host_port() -> None:
    """Network=host removes PublishPort; bind is via --web.listen-address. We
    bind :<port> (0.0.0.0), matching bns admin's trusted-LAN exposure."""
    out = _render_quadlet(BASE_DATA)
    assert f"--web.listen-address=:{CONTAINER_PORT}" in out
    assert "PublishPort" not in out


@pytest.mark.parametrize("port", [9100, 19100])
def test_quadlet_listen_address_tracks_host_port(port: int) -> None:
    out = _render_quadlet({**BASE_DATA, "nodeexporter_host_port": port})
    assert f"--web.listen-address=:{port}" in out


def test_quadlet_filesystem_collector_excludes_present() -> None:
    out = _render_quadlet(BASE_DATA)
    assert "--collector.filesystem.mount-points-exclude=" in out
    assert "--collector.filesystem.fs-types-exclude=" in out
    # /host-prefixed and container storage must be excluded to avoid dupes.
    assert "host/" in out
    assert "var/lib/containers" in out


def test_quadlet_dollar_anchors_escaped_for_systemd() -> None:
    """systemd expands $ in Exec lines, so regex anchors must be written $$.
    A bare `$|`, `$/` or trailing `$` would be eaten as a bogus var expansion."""
    out = _render_quadlet(BASE_DATA)
    exec_line = next(line for line in out.splitlines() if line.startswith("Exec="))
    assert "($$|/)" in exec_line
    assert "tracefs)$$" in exec_line
    # No un-escaped single `$` should survive (every `$` must be part of `$$`).
    assert "$" not in exec_line.replace("$$", "")


def test_quadlet_resource_caps_in_service_section() -> None:
    """Cgroup ceilings live in [Service] (systemd-native), not [Container]
    (podman-native), so the unit works on podman < 5.5 too."""
    out = _render_quadlet(BASE_DATA)
    assert "MemoryMax=128M" in out
    assert "MemoryHigh=96M" in out
    assert "CPUQuota=50%" in out
    assert "TasksMax=1024" in out
    for forbidden in ("Memory=", "MemoryReservation=", "CPUS=", "PidsLimit="):
        assert forbidden not in out, f"forbidden quadlet key emitted: {forbidden!r}"
    container_block = out.split("[Container]", 1)[1].split("[Service]", 1)[0]
    for key in ("MemoryMax", "MemoryHigh", "CPUQuota", "TasksMax"):
        assert key not in container_block, f"{key} should not be in [Container]"


def test_quadlet_has_no_exec_reload() -> None:
    """node-exporter is stateless; nothing to SIGHUP-reload."""
    out = _render_quadlet(BASE_DATA)
    assert "ExecReload" not in out


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
