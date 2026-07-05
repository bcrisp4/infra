# pyinfra

Imperative host provisioning for the homelab. Used for host-level setup that lives outside Terraform and Kubernetes — package installs, OS settings, system services, anything that needs to happen on a real machine.

See `CLAUDE.md` in this directory for pyinfra concepts and project conventions. The notes below cover only how *this* config is wired up.

## Layout

```
pyinfra/
├── pyproject.toml           # uv project, declares pyinfra dep
├── .python-version          # pinned Python (3.12)
├── inventory.py             # hosts (in `all`, with per-host data) + role groups
├── deploy.py                # top-level entry, wires tasks together
├── group_data/
│   ├── all.py               # project-wide defaults, every service disabled
│   ├── dns_servers.py       # role flip file: bns
│   ├── dhcp_servers.py      # role flip file: dnsmasq
│   ├── monitoring_servers.py # role flip file: prometheus/grafana/renderer
│   ├── metrics_agents.py    # role flip file: node-exporter/podman-exporter
│   └── feed_hosts.py        # role flip file: bfeed
├── tasks/
│   ├── base.py              # apt update/upgrade, packages, timezone
│   ├── podman.py            # install podman + Pi cmdline patch
│   └── unattended_upgrades.py
├── tests/
│   └── test_podman.py       # pytest unit tests for cmdline rewrite logic
└── files/
    └── 20auto-upgrades      # static config files copied to hosts
```

Tasks are `@deploy`-decorated functions that compose pyinfra built-in operations. `deploy.py` is intentionally thin: it just calls each task in order.

### How inventory and data fit together

`inventory.py` declares every host ONCE in the `all` list, together with its
per-host data dict (machine facts: addresses, UUIDs, GIDs, serve lists, scrape
targets). Role groups are bare-FQDN membership lists:

```python
all = [("rpi5-4cpu-16gb-home-1.marlin-tet.ts.net", _pi_data)]

dns_servers = [_PI]
monitoring_servers = [_PI]
metrics_agents = [_PI]
```

Data resolution, first match wins:

1. host dict in `inventory.py` (machine facts)
2. `group_data/<role>.py` (enable flags + role policy)
3. `group_data/all.py` (project-wide defaults; every `<name>_enabled = False`)

Keep role-file keys disjoint (each role owns its services' key prefixes) so
group merge order never matters. pyinfra creates hosts only from the explicit
`all` list; a guard at the bottom of `inventory.py` raises if a role names an
undeclared host. Inspect the resolved data with:

```bash
uv run pyinfra inventory.py debug-inventory
```

**Prometheus scrape targets are explicit.** Enabling a service does not add a
scrape job. Add an entry to `prometheus_scrape_targets` in the monitoring
server's host dict (`{"job": ..., "target": ..., "labels": {...}}`). Cross-host
targets use the Tailscale FQDN (`cloud1.marlin-tet.ts.net:9100`).

## Prerequisites

- `uv` installed locally.
- SSH access to the target host as the user named in inventory (`ben`), with that user already in `sudo` (passwordless or agent-cached). SSH key auth via `~/.ssh/config` or `ssh-agent`.
- Tailscale up locally — hosts are addressed by their `*.marlin-tet.ts.net` FQDN.

## Quick start

```bash
cd pyinfra

# Install pyinfra into a local .venv
uv sync

# Preview changes without touching the host
uv run pyinfra inventory.py deploy.py --dry

# Apply (interactive prompt before execution)
uv run pyinfra inventory.py deploy.py

# Apply non-interactively
uv run pyinfra -y inventory.py deploy.py
```

Useful flags:

| Flag                       | Effect                                                 |
|----------------------------|--------------------------------------------------------|
| `--dry`                    | Run Prepare stage only, print diff, no remote changes. |
| `-v` / `-vv` / `-vvv`      | Bump verbosity (`-vvv` shows raw shell output).        |
| `--limit <pattern>`        | Restrict to a host or group.                           |
| `--data key=value`         | Inject inventory data at the CLI.                      |

Examples:

```bash
# Run against just one host
uv run pyinfra inventory.py deploy.py --limit rpi5-4cpu-16gb-home-1.marlin-tet.ts.net

# Ad-hoc command instead of a deploy
uv run pyinfra inventory.py exec -- uptime
```

## What gets applied

`deploy.py` calls every task module in dependency order; each task gates itself
on its `<name>_enabled` host/group data, so what actually runs on a host is
decided by its role groups and host dict. The foundational tasks:

- **`tasks/base.py`** — refresh apt cache, upgrade installed packages, install `base_packages`, set timezone (idempotent via a `timedatectl show` fact check).
- **`tasks/unattended_upgrades.py`** — install `unattended-upgrades`, drop `/etc/apt/apt.conf.d/20auto-upgrades` to enable periodic security updates.
- **`tasks/podman.py`** — install Podman (rootful) and its container runtime deps; on Raspberry Pi hosts, patch `/boot/firmware/cmdline.txt` to append `cgroup_enable=memory` (a Pi downstream-only kernel param that overrides the firmware-injected `cgroup_disable=memory`) so the memory cgroup controller is available to containers. Gated on `install_podman = True` in host/group data. Cmdline changes require a manual reboot.

All operations are idempotent: a re-run on an unchanged host should report zero changes.

## Tests

Pure-Python helpers (e.g. cmdline rewrite logic in `tasks/podman.py`) have pytest coverage.

```bash
cd pyinfra
uv sync --dev
uv run pytest -v
```

## Adding a host

1. Declare it once in `all` with its data dict, then add it to role lists:

   ```python
   _cloud1 = {"ssh_user": "debian"}

   all = [(_PI, _pi_data), ("cloud1.marlin-tet.ts.net", _cloud1)]
   metrics_agents = [_PI, "cloud1.marlin-tet.ts.net"]
   ```

2. If the central Prometheus should scrape it, append to
   `prometheus_scrape_targets` in `_pi_data` (and set
   `nodeexporter_listen_address` to the host's Tailscale IP if it has a
   public interface).
3. `uv run pyinfra inventory.py debug-inventory` to check resolved data, then
   dry-run and apply.

Per-host overrides (timezone, package list, any `all.py` key) go in the host's
data dict.

## Adding a role

1. Add a membership list in `inventory.py` (and extend the guard's `_roles`
   dict), e.g. `queue_servers = [_PI]`.
2. Create `group_data/queue_servers.py` flipping that role's `<name>_enabled`
   keys (defaults belong in `group_data/all.py`).
3. Singleton roles (DHCP, DNS on the LAN): keep membership to exactly one
   host; nothing enforces this beyond the list you write.

A host can belong to multiple roles; include it in multiple lists.

## Adding a new task

1. Create `tasks/<name>.py` exporting a `@deploy("<description>")` function.
2. Compose built-in operations from `pyinfra.operations.*`. Pull per-host config from `host.data.get(...)` so the task stays reusable.
3. Import and call it from `deploy.py`.
4. If the task needs to ship a static file, drop it under `files/` and reference via `Path(__file__).resolve().parent.parent / "files" / "<name>"`.

Prefer built-in operations and facts over `server.shell`. Use `server.shell` only when no built-in fits, and guard it with a fact check so the operation stays idempotent.

## Troubleshooting

- **`EOFError` on apply**: pyinfra wants confirmation on a TTY. Either run from an interactive shell, or pass `-y`.
- **`Permission denied` on sudo**: target user must be in `sudo`. Either configure passwordless sudo on the host or run with `--sudo-password` / `SUDO_PASSWORD` env var.
- **Connection hang**: confirm `tailscale status` shows the host online and that you can `ssh ben@<fqdn>` manually first.
- **Stale facts after a manual change**: pyinfra caches facts per run. Just re-run — caches are fresh each invocation.
