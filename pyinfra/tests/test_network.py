from tasks.network import _render_netplan

BASE_DATA = {
    "interface": "eth0",
    "connection_uuid": "75a1216a-9d1a-30cd-8aca-ace5526ec021",
    "connection_name": "netplan-eth0",
}


def test_render_netplan_uses_dhcp_and_keeps_networkmanager_identity() -> None:
    assert _render_netplan(BASE_DATA) == (
        "network:\n"
        "  version: 2\n"
        "  ethernets:\n"
        "    eth0:\n"
        "      renderer: NetworkManager\n"
        "      match: {}\n"
        "      dhcp4: true\n"
        "      networkmanager:\n"
        '        uuid: "75a1216a-9d1a-30cd-8aca-ace5526ec021"\n'
        '        name: "netplan-eth0"\n'
        "        passthrough:\n"
        '          proxy._: ""\n'
    )


def test_render_netplan_has_no_static_ipv4_settings() -> None:
    rendered = _render_netplan(BASE_DATA)

    assert "dhcp4: true" in rendered
    assert "addresses:" not in rendered
    assert "nameservers:" not in rendered
    assert "routes:" not in rendered
    assert "192.168.1.2" not in rendered
