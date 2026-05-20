# pyinfra

Imperative host provisioning for the homelab. Used for host-level setup that lives outside Terraform and Kubernetes — package installs, OS settings, system services, anything that needs to happen on a real machine.

See `CLAUDE.md` in this directory for pyinfra concepts and project conventions. The notes below cover only how *this* config is wired up.

## Layout

```
pyinfra/
├── pyproject.toml           # uv project, declares pyinfra dep
├── .python-version          # pinned Python (3.12)
├── inventory.py             # hosts + groups
├── deploy.py                # top-level entry, wires tasks together
├── group_data/
│   └── homelab.py           # shared data for the `homelab` group
├── tasks/
│   ├── base.py              # apt update/upgrade, packages, timezone
│   └── unattended_upgrades.py
└── files/
    └── 20auto-upgrades      # static config files copied to hosts
```

Tasks are `@deploy`-decorated functions that compose pyinfra built-in operations. `deploy.py` is intentionally thin: it just calls each task in order.

### How inventory and data fit together

`inventory.py` defines groups. The variable name *is* the group name:

```python
homelab = [
    ("rpi5-4cpu-16gb-home.marlin-tet.ts.net", {"ssh_user": "ben"}),
]
```

`group_data/homelab.py` provides defaults for every host in `homelab`:

```python
timezone = "UTC"
base_packages = ["vim", "git", "htop", "tmux", "curl"]
```

Per-host overrides go in the host tuple in `inventory.py`. Tasks read values via `host.data.get("key", default)`, so missing keys fall back cleanly.

Resolution order: host data → group data → defaults baked into the task.

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
uv run pyinfra inventory.py deploy.py --limit rpi5-4cpu-16gb-home.marlin-tet.ts.net

# Ad-hoc command instead of a deploy
uv run pyinfra inventory.py exec -- uptime
```

## What gets applied

Currently `deploy.py` runs two task modules against every host in the inventory:

- **`tasks/base.py`** — refresh apt cache, upgrade installed packages, install `base_packages`, set timezone (idempotent via a `timedatectl show` fact check).
- **`tasks/unattended_upgrades.py`** — install `unattended-upgrades`, drop `/etc/apt/apt.conf.d/20auto-upgrades` to enable periodic security updates.

All operations are idempotent: a re-run on an unchanged host should report zero changes.

## Adding a host

1. Append a tuple to the appropriate group in `inventory.py`:

   ```python
   homelab = [
       ("rpi5-4cpu-16gb-home.marlin-tet.ts.net", {"ssh_user": "ben"}),
       ("new-host.marlin-tet.ts.net", {"ssh_user": "ben"}),
   ]
   ```

2. Confirm with a dry-run, then apply.

Per-host overrides go in the data dict:

```python
("special-host.marlin-tet.ts.net", {
    "ssh_user": "ben",
    "timezone": "Europe/London",
    "base_packages": ["vim", "git", "tmux"],
}),
```

## Adding a new group

1. Add a new top-level list in `inventory.py`, e.g. `kube_nodes = [...]`.
2. Optionally create `group_data/kube_nodes.py` for shared data.
3. In tasks, gate behaviour by group membership:

   ```python
   from pyinfra import host

   if "kube_nodes" in host.groups:
       ...
   ```

A host can belong to multiple groups; just include it in multiple lists.

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
