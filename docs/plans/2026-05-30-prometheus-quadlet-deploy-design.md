# Prometheus quadlet deploy (homelab Pi) - design

Date: 2026-05-30

## Summary

Deploy Prometheus to `rpi5-4cpu-16gb-home` using pyinfra, following the same
rootful podman quadlet pattern already used for bns (`pyinfra/tasks/bns.py`).
Prometheus scrapes itself and the bns admin endpoint, stores its TSDB on a
dedicated LVM logical volume, and is reachable on host `:9090` over LAN and
Tailscale.

This is a standalone homelab service. It is unrelated to the Kubernetes
`kube-prometheus-stack` + Thanos design in
`docs/reference/metrics-architecture.md`, which targets future clusters and is
not deployed today.

## Goals

- Reuse the bns quadlet pattern (pure renderers, data-driven, `_if` lifecycle).
- Scrape Prometheus self and bns `/metrics`.
- Persist TSDB on a dedicated LV with bounded retention (time and size).
- No new abstraction. A little duplication of the quadlet lifecycle block is
  accepted; a generic container deploy is deferred until a third app exists and
  the real variation is visible.

## Non-goals (future deploys)

- node_exporter (host metrics).
- Alertmanager, alerting and recording rule files.
- Grafana.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Reach from Prometheus to bns | `host.containers.internal:<bns_admin_port>` | No shared network, no hardcoded IP. bns deploy changes only its host port. Confirmed present rootful (`10.88.0.1`) and rootless (`169.254.1.2`). |
| bns admin host port | `9090` -> `9053` | Frees `:9090` for Prometheus. `9053` avoids the Prometheus exporter port cluster (9090/9091/9093/9100/9115). Container side stays `9090`. |
| Prometheus host port | `9090` (standard) | Prometheus owns the conventional port. |
| Image | `quay.io/prometheus/prometheus:v3.12.0-distroless` | Latest stable, distroless for smaller surface. |
| Container user | `65532:65532` | Distroless image runs as the distroless `nonroot` uid `65532`, NOT `nobody` `65534`. Confirmed via `podman inspect`. |
| TSDB LV | 10G usable, mounted at `/var/lib/prometheus` | RAID10 `-i2 -m1` = ~20G raw; VG `data` has >100G free. |
| Data dir permissions | owner `65532:65532`, mode `0700` | Prometheus is the sole writer. |
| Retention | `--storage.tsdb.retention.time=30d` and `--storage.tsdb.retention.size=8GB` | Whichever limit hits first; size cap protects the LV. |
| Reload | SIGHUP via `ExecReload` | Reloads config and rules without a restart. No `--web.enable-lifecycle`, so `/-/reload` stays disabled. |
| Access | publish on all interfaces (`0.0.0.0` + `[::]`) | Reachable on LAN (`192.168.1.2:9090`) and Tailscale (including Tailscale IPv6). Matches bns. eth0 IPv6 is disabled, so no LAN v6. |

## Architecture

```
                        rpi5-4cpu-16gb-home
  +-------------------------------------------------------------+
  |                                                             |
  |  prometheus container (rootful quadlet, uid 65532)          |
  |    listens :9090 -> published host :9090 (v4 + [::])        |
  |    config  /etc/prometheus/prometheus.yml (ro bind)         |
  |    tsdb    /prometheus -> /var/lib/prometheus (LV bind)     |
  |        |                                                    |
  |        | scrape host.containers.internal:9053               |
  |        v                                                    |
  |  podman bridge gateway (10.88.0.1) -> host :9053 published  |
  |        |                                                    |
  |        v                                                    |
  |  bns container  admin :9090 -> published host :9053         |
  |                                                             |
  +-------------------------------------------------------------+
```

Scrape traffic hairpins out to the host gateway and back to the bns published
port. Volume is trivial (one HTTP GET per scrape interval).

## Files touched

| File | Change |
|------|--------|
| `pyinfra/tasks/prometheus.py` | New. `@deploy` plus pure `_render_config` and `_render_quadlet`, modelled on `tasks/bns.py`. |
| `pyinfra/tests/test_prometheus.py` | New. Unit tests for both renderers. |
| `pyinfra/deploy.py` | Add `from tasks.prometheus import prometheus`; call `prometheus()` after `bns()`. |
| `pyinfra/group_data/homelab.py` | Add `prometheus_*` keys; change `bns_host_port_admin` to `9053`. |
| `pyinfra/inventory.py` | Add a `prometheus` LV to the host `storage["lvs"]`. |

`tasks/bns.py` is not edited. It already reads `bns_host_port_admin`, so moving
the data value re-renders the bns quadlet (`PublishPort=9053:9090`) on the next
apply, triggering a daemon-reload and restart.

## Data model (`group_data/homelab.py`)

```python
# --- changed ---
bns_host_port_admin = 9053   # was 9090; freed for Prometheus. Container side stays 9090.

# --- new ---
prometheus_enabled = True
prometheus_image = "quay.io/prometheus/prometheus"
prometheus_image_tag = "v3.12.0-distroless"
prometheus_host_port = 9090
prometheus_scrape_interval = "15s"
prometheus_retention_time = "30d"
prometheus_retention_size = "8GB"
# systemd cgroup ceilings (Prometheus is heavier than bns)
prometheus_memory_max = "1G"
prometheus_memory_high = "768M"
prometheus_cpu_quota = "200%"
prometheus_tasks_max = 4096
```

The bns scrape target port is read from `bns_host_port_admin` so there is a
single source of truth for the port.

## Storage LV (`inventory.py`)

Append to the host `storage["lvs"]` list:

```python
{
    "name": "prometheus",
    "size": "10G",
    "stripes": 2,
    "mirrors": 1,
    "stripesize": "64k",
    "fs": "xfs",
    "mkfs_opts": "-n ftype=1 -m reflink=1,crc=1 -d su=64k,sw=2",
    "mount": "/var/lib/prometheus",
    "mount_opts": "noatime",
},
```

`storage()` runs before `prometheus()` in `deploy.py`, so the LV is mounted at
`/var/lib/prometheus` before the container starts. `storage()` creates the
mount point at `0700 root`; the Prometheus deploy then chowns the mounted LV
root to the container uid (below).

## `tasks/prometheus.py`

Structure copies `tasks/bns.py`: module constants, two pure renderers, a
`_DATA_KEYS` tuple, and a gated `@deploy`.

### Rendered `prometheus.yml`

Hand-rolled YAML (no PyYAML), matching the bns convention and unit-tested.

```yaml
# Rendered by pyinfra tasks/prometheus.py. Do not edit by hand.
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: bns
    static_configs:
      - targets: ['host.containers.internal:9053']
```

`scrape_interval` comes from `prometheus_scrape_interval`; the bns target port
comes from `bns_host_port_admin`.

### Rendered `prometheus.container`

```ini
# Rendered by pyinfra tasks/prometheus.py. Do not edit by hand.
[Unit]
Description=Prometheus monitoring server
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=60s
StartLimitBurst=10

[Container]
Image=quay.io/prometheus/prometheus:v3.12.0-distroless
ContainerName=prometheus
PublishPort=9090:9090/tcp
PublishPort=[::]:9090:9090/tcp
Volume=/etc/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
Volume=/var/lib/prometheus:/prometheus
Exec=--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=30d --storage.tsdb.retention.size=8GB --web.listen-address=0.0.0.0:9090

[Service]
Restart=always
RestartSec=5s
ExecReload=/usr/bin/podman kill --signal HUP %N
MemoryMax=1G
MemoryHigh=768M
CPUQuota=200%
TasksMax=4096

[Install]
WantedBy=multi-user.target
```

Notes:

- `Exec=` overrides the image CMD only; the entrypoint `/bin/prometheus`
  remains, so the flags are appended to it.
- cgroup ceilings live in `[Service]` (portable across podman versions; podman
  on Debian 13 is 5.4.2), same rationale as bns.
- `[::]` publish is for Tailscale IPv6. eth0 IPv6 is disabled, so there is no
  LAN v6.
- SIGHUP reload does not require `--web.enable-lifecycle`, so the HTTP
  `/-/reload` and `/-/quit` endpoints stay disabled.

### Deploy body

Mirrors `tasks/bns.py`:

1. Gate on `prometheus_enabled`; early return if false.
2. Materialize `host.data` to a plain dict over `_DATA_KEYS`.
3. `files.directory(/var/lib/prometheus, user="65532", group="65532", mode="0700", _sudo=True)`
   to set ownership on the mounted LV before the container starts. This is
   sequenced before the container-start op in the same apply, so there is no
   race and no need for the `:U` volume flag.
4. `files.directory(/etc/prometheus, ...)` and `files.put` the rendered config.
5. `files.put` the rendered quadlet to `/etc/containers/systemd/prometheus.container`.
6. Three `systemd.service` ops gated by `_if`:
   - unit changed -> `restarted=True, daemon_reload=True`
   - config-only changed -> `reloaded=True` (SIGHUP)
   - always -> ensure `running=True`

## Testing (`tests/test_prometheus.py`)

pytest over the pure renderers, like `tests/test_bns.py`:

- `_render_config`: both jobs present; bns target uses the configured admin
  port; valid structure; single trailing newline.
- `_render_quadlet`: image pinned as `name:tag`; both publish lines present;
  both volumes present; `Exec=` carries the retention time and size flags;
  `ExecReload` is the SIGHUP line; cgroup limits present; `[Install]` present.

## Rollout

One pyinfra apply does everything in `deploy.py` order: `storage()` creates and
mounts the LV, `bns()` re-renders on the new admin port and restarts,
`prometheus()` chowns the data dir, renders config and unit, and starts.

The Pi has no passwordless sudo and the Bash tool has no TTY, so the user runs
the apply via the `!` prefix:

```
cd pyinfra && uv run pyinfra inventory.py deploy.py \
  --limit rpi5-4cpu-16gb-home.marlin-tet.ts.net --dry      # review diff first
# then re-run with -y to apply
```

## Verification

After apply, from the Pi host (distroless has no in-container shell):

```
# Prometheus up and its own targets healthy (proves the bns scrape works)
curl -s localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
# expect prometheus + bns both health="up"

# bns admin moved correctly
curl -s localhost:9053/metrics | head

# data dir ownership
stat -c '%u:%g %a' /var/lib/prometheus    # expect 65532:65532 700
```

## Risks and mitigations

| Risk | Status / mitigation |
|------|---------------------|
| VG free space for the LV | Resolved. `data` VG has >100G free; 10G usable (~20G raw) fits. |
| bns admin port move breaks consumers | Resolved. The bns admin port is not currently consumed by anything external. |
| `host.containers.internal` not available | Resolved. Confirmed injected rootful (`10.88.0.1`) and rootless (`169.254.1.2`). |
| Wrong container uid | Resolved. Distroless image runs as `65532`; the data dir is chowned to match. |
| Distroless has no shell for reload | Not an issue. `ExecReload` runs `podman kill` on the host; SIGHUP is delivered to the container PID 1. |

## Open items

- Confirm `v3.12.0-distroless` is the intended pin at apply time (bump if a
  newer stable has shipped).
