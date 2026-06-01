"""Unit tests for tasks.podman_network pure renderer."""

import pytest

from tasks.podman_network import _render_network


def test_network_sets_network_name() -> None:
    out = _render_network("monitoring")
    assert "NetworkName=monitoring" in out


@pytest.mark.parametrize("name", ["monitoring", "rendering", "obs"])
def test_network_name_tracks_arg(name: str) -> None:
    out = _render_network(name)
    assert f"NetworkName={name}" in out


def test_network_has_required_sections() -> None:
    out = _render_network("monitoring")
    assert "[Network]" in out
    assert "[Install]" in out


def test_network_section_order() -> None:
    """[Network] before [Install]."""
    out = _render_network("monitoring")
    positions = [out.index(s) for s in ("[Network]", "[Install]")]
    assert positions == sorted(positions), f"section order wrong: {positions}"


def test_network_install_target_is_multi_user() -> None:
    out = _render_network("monitoring")
    assert "WantedBy=multi-user.target" in out


def test_network_terminates_with_single_newline() -> None:
    out = _render_network("monitoring")
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_network_is_deterministic() -> None:
    assert _render_network("monitoring") == _render_network("monitoring")
