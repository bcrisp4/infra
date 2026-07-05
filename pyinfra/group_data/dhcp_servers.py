"""dhcp_servers role: dnsmasq in DHCP-only mode (bns owns :53).

All dnsmasq_* settings are LAN-specific and live in the host dict in
inventory.py; this file only flips the gate.
"""

dnsmasq_enabled = True
