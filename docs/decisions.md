## 2026-09-23: Use router DHCP on eth0

**Context:** The Pi moved to a network where the router supplies DHCP.

**Decision:** Netplan configures `eth0` for DHCP. Pyinfra purges `dnsmasq`. The BNS role stays inactive while the Pi uses a dynamic lease.

**Rejected:** Static IPv4 settings on the Pi and `dnsmasq` as the LAN DHCP server.

**Why:** The router supplies DHCP. The Pi's lease can change. BNS needs a stable LAN address.

**Revisit when:** The router reserves a stable address for the Pi and BNS must serve LAN clients.

**Links:** `pyinfra/tasks/network.py`, `pyinfra/tasks/remove_dnsmasq.py`, `pyinfra/inventory.py`.
