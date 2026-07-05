# pyinfra group data split: role groups + per-host data

**Date:** 2026-07-04
**Status:** Approved
**Issues:** [#115](https://github.com/bcrisp4/infra/issues/115), [#116](https://github.com/bcrisp4/infra/issues/116), [#117](https://github.com/bcrisp4/infra/issues/117)

## Problem

`pyinfra/group_data/homelab.py` is one host's entire configuration masquerading as group data. Every `<name>_enabled` flag sits at group level, and machine-specific facts (static IP, NetworkManager UUID, DHCP range, `video` GID) are inherited by any host that joins the group. Adding a cloud instance to the current layout would give it a DNS server, a DHCP server, and another machine's static LAN IP.

Additionally, `tasks/prometheus.py` hardcodes a scrape job for every service and reaches into six other services' data keys. A host running Prometheus without those services would render broken targets (`bfeed:None`), and cross-host scraping (central Prometheus scraping cloud exporters) cannot be expressed at all.

Goal: 1-2 cloud instances land soon with profiles that differ from the Pi. Adding them should be data-only work.

## Grounding: pyinfra data semantics (verified in source)

- Data resolution, first match wins (`api/host.py:169-172`): deploy-time override, CLI `--data`, host tuple data, merged group data, `all` data.
- `group_data/all.py` attaches to the auto-generated `all` group and is the lowest-priority data source. Officially documented as the place for project-wide defaults.
- A host in multiple groups gets group data merged in group definition order; on key conflict the last group wins (`Inventory.get_groups_data`). The design avoids relying on this by keeping keys disjoint between group files.
- If the inventory defines an explicit `all` group, hosts are created only from that list. A host named only in a role group is silently dropped (`make_inventory_from_files`). The inventory therefore carries a load-time guard assert.
- Underscore-prefixed module-level variables in the inventory file are ignored by the group loader (`_is_inventory_group`), so private host-data dicts are safe to define there.
- `pyinfra inventory.py debug-inventory` dumps resolved per-host data; used to verify the migration.

## Decisions

| Decision | Choice |
|---|---|
| Cloud host roles | Unknown; optimize for cheap role creation |
| Monitoring topology | Central Prometheus on the Pi, scraping cloud exporters over the tailnet |
| Defaults home | `group_data/all.py` (single mechanism; `@deploy(data_defaults=...)` deliberately not adopted) |
| Per-host data home | Underscore-prefixed dicts in `inventory.py`, referenced from host tuples |
| Group meaning | Roles only (`dns_servers`, `metrics_agents`, ...), no location groups |
| Inventory style | Explicit `all` list with host data, bare-string role lists, guard assert |

## Design

### inventory.py

```python
_PI = "rpi5-4cpu-16gb-home-1.marlin-tet.ts.net"

_pi_data = {
    "ssh_user": "ben",
    # machine facts
    "bns_listen_address": "192.168.1.2",
    "pi5_exporter_video_gid": 44,
    "static_network_enabled": True,
    "static_network": {...},            # connection UUID, IP, gateway, DNS
    "pcie_gen3_enabled": True,
    "pi5_exporter_enabled": True,       # hardware-bound, so host data not role data
    "dnsmasq_interface": "eth0",        # LAN-specific DHCP keys
    # ... other dnsmasq_* keys
    "tailscale_serve_services": [...],  # what this host advertises
    "prometheus_scrape_targets": [...], # see prometheus change below
}

all = [(_PI, _pi_data)]

dns_servers = [_PI]
dhcp_servers = [_PI]
monitoring_servers = [_PI]
metrics_agents = [_PI]
feed_hosts = [_PI]

# Guard: a role member missing from `all` is silently dropped by pyinfra.
_known = {h[0] if isinstance(h, tuple) else h for h in all}
for _g in (dns_servers, dhcp_servers, monitoring_servers, metrics_agents, feed_hosts):
    for _h in _g:
        assert _h in _known, f"{_h} in a role group but not in all"
```

Notes:

- `all` shadows the Python builtin inside this module. Required by pyinfra, harmless at module scope.
- Hosts also land in the auto-generated `inventory` group (filename quirk). Unused.
- New host: one tuple in `all` plus role membership lines. New role: one list here plus one flip file in `group_data/`.
- A cloud host with undecided workload joins `metrics_agents` only on day one.

### group_data/all.py

Replaces most of `homelab.py`. Contains every configuration key with its current value as the default: image names and tags, ports, cgroup ceilings, timezone, `base_packages`, and so on. Service policy that belongs to a role (for example bns upstreams and blocklists) lives in that role's file, not here. All `<name>_enabled` flags default to `False`, except `install_podman = True` (all current and planned hosts run podman; hosts can override it off in their data dict). `prometheus_scrape_targets` defaults to `[]`.

### `group_data/<role>.py` flip files

| File | Content |
|---|---|
| `dns_servers.py` | `bns_enabled = True`, bns upstreams/blocklists (shared policy, not machine facts) |
| `dhcp_servers.py` | `dnsmasq_enabled = True` |
| `monitoring_servers.py` | `prometheus_enabled`, `grafana_enabled`, `grafana_image_renderer_enabled`, `monitoring_network_enabled`, `rendering_network_enabled`, `tailscale_serve_enabled = True` |
| `metrics_agents.py` | `nodeexporter_enabled = True`, `podman_exporter_enabled = True` |
| `feed_hosts.py` | `bfeed_enabled = True` |

`group_data/homelab.py` is deleted. Convention: each role file owns its services' key prefixes; no key appears in two role files, so last-group-wins precedence never fires.

## Task code changes

Only two tasks change. `deploy.py`, the quadlet pattern, reload semantics, and secret handling are untouched; all other tasks already gate on data.

### tasks/prometheus.py (issue #115)

The scrape config becomes a loop over an explicit target list from host data:

```python
"prometheus_scrape_targets": [
    {"job": "bns", "target": "192.168.1.2:9053"},
    {"job": "node-exporter", "target": "host.containers.internal:9100",
     "labels": {"instance": "rpi5-4cpu-16gb-home-1"}},
    {"job": "grafana", "target": "grafana:3000",
     "labels": {"instance": "rpi5-4cpu-16gb-home-1"}},
    {"job": "podman-exporter", "target": "podman-exporter:9882",
     "labels": {"instance": "rpi5-4cpu-16gb-home-1"}},
    {"job": "pi5-exporter", "target": "pi5-exporter:2712",
     "labels": {"instance": "rpi5-4cpu-16gb-home-1"}},
    {"job": "bfeed", "target": "bfeed:9091",
     "labels": {"instance": "rpi5-4cpu-16gb-home-1"}},
],
```

- The Prometheus self-scrape job stays built into the renderer; every other job is one YAML block per list entry (`job`, `target`, optional `labels`).
- `_DATA_KEYS` shrinks to Prometheus-own keys plus `prometheus_scrape_targets`. The cross-service coupling (`bns_listen_address`, `bfeed_metrics_port`, `nodeexporter_host_port`, `podman_exporter_port`, `pi5_exporter_port`) is removed from the task.
- A future cloud host is scraped by appending `{"job": "node-exporter", "target": "cloud1.marlin-tet.ts.net:9100", "labels": {"instance": "cloud1"}}`. No code change.

Accepted trade-offs: enabling a service no longer auto-adds its scrape job (the operator adds the target entry; README documents this), and ports appear both in the service's own key and in the target string. Explicitness over clever automation, per repo convention.

### tasks/nodeexporter.py

New key `nodeexporter_listen_address`, default `""` (empty string = all interfaces, so the rendered `--web.listen-address=:9100` and therefore the quadlet unit are byte-identical on the Pi; `0.0.0.0` would have identical semantics but force a pointless container restart). Cloud hosts set their Tailscale IP in their host data dict so `Network=host` on a machine with a public interface does not expose `:9100` to the internet. One-line renderer change to `--web.listen-address`.

## Migration plan

One PR; no on-host changes expected beyond a possible cosmetic prometheus.yml rewrite.

1. Write `group_data/all.py` (current `homelab.py` values as defaults, enabled flags off).
2. Write the five role flip files.
3. Rewrite `inventory.py` (explicit `all`, `_pi_data`, role lists, guard).
4. Delete `group_data/homelab.py`. No task code references group names (verified: no `host.groups` checks exist).
5. Update `tasks/prometheus.py` and `tasks/nodeexporter.py`.
6. Update `pyinfra/README.md` (layout, add-a-host recipe, add-a-role recipe, scrape-target note) and `pyinfra/CLAUDE.md`.

## Verification

Acceptance test is zero drift on the Pi:

1. Before the refactor: `uv run pyinfra inventory.py debug-inventory > before.json`.
2. After: run `debug-inventory` again and diff resolved per-host data. Expected differences: key additions only (`prometheus_scrape_targets`, `nodeexporter_listen_address`), no changed values.
3. `uv run pyinfra inventory.py deploy.py --dry` must show zero changes, except a possible prometheus.yml rewrite if the rendered YAML differs cosmetically (config-only SIGHUP, harmless).
4. The inventory guard assert self-tests on every pyinfra invocation.

Tests (same plain-pytest-on-renderers pattern):

- `tests/test_prometheus.py` rewritten for the target-list renderer: empty list (self-scrape only), entry without labels, entry with labels, determinism, single trailing newline. Cross-service key tests deleted.
- `tests/test_nodeexporter.py`: listen-address default and override.

Rollback: revert the commit. Rendered on-host files regenerate from either version; no host state is involved.

## Out of scope

- Tailscale ACL grant for Pi-to-cloud scraping (`terraform/global/tailscale.tf`, when the first cloud host lands).
- Cloud instance bootstrap/day-0 (Terraform + tailscale join).
- Quadlet boilerplate dedup across container tasks.
