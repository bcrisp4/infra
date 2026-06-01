# CLAUDE.md — pyinfra

Guide Claude Code when working pyinfra in infra monorepo.

## What pyinfra is

pyinfra = Python infra automation tool. Turn Python into shell commands, execute on target hosts via connectors (SSH, Docker, local, chroot, etc.). Agentless, idempotent, supports dry-run with diffs.

- Upstream repo: https://github.com/pyinfra-dev/pyinfra
- Docs: https://docs.pyinfra.com/en/3.x/
- Vendored read-only copy: `~/vendor/pyinfra/`
- **context7 MCP** indexes pyinfra docs. Use `mcp__plugin_context7_context7__resolve-library-id` + `mcp__plugin_context7_context7__query-docs` for current API + usage info before web search or guessing.

## Execution model

Every deploy moves five stages (`src/pyinfra/api/state.py`):

1. **Setup** — load inventory + data.
2. **Connect** — open host connections.
3. **Prepare** — call operation functions, detect changes. Facts gathered here. No remote mutation.
4. **Execute** — run commands generated during Prepare.
5. **Disconnect** — close connections.

Two-pass design (Prepare then Execute) enables `--dry`, change diffs, safe previews. Operations = Python generators yielding shell commands. Prepare consumes generator to determine `will_change`; Execute consumes same generator to run commands.

Parallelism via gevent greenlets, not threads. Stdlib monkey-patched in `pyinfra_cli/main.py`. Max parallelism bounded by file descriptor limit.

## Core concepts

### Operations
- Decorated `@operation` (see `src/pyinfra/api/operation.py`).
- Return generator of commands (strings or `StringCommand` objects).
- Idempotency = query facts, conditionally yield commands.
- `host` + `state` accessed via thread-local context (`from pyinfra import context`), not params.

Minimal example:
```python
from pyinfra.api import operation

@operation()
def install_nginx(update=False):
    if update:
        yield "apt-get update"
    yield "apt-get install -y nginx"
```

### Facts
- Subclass `FactBase` (see `src/pyinfra/api/facts.py`).
- Define `command` (string or method returning shell command) + `process(output)` to parse result.
- Optional `requires_command()` skips fact if binary missing.
- Facts cached per host, re-fetchable mid-operation for change detection.

Minimal example:
```python
from pyinfra.api import FactBase

class NginxRunning(FactBase):
    command = "pgrep -x nginx >/dev/null && echo yes || echo no"
    def process(self, output):
        return output[0] == "yes"
```

### Hosts and inventory
- Inventory = Python file (usually `inventory.py`) listing targets.
- Top-level list variable name becomes the group name. `group_data/<group>.py` (alongside `inventory.py`) is auto-discovered and supplies shared data.
- Per-host data goes in the host tuple `(fqdn, {key: value})` and overrides group data. Tasks read values via `host.data.get("key", default)`.
- Plain hostnames default SSH connector. Connector-specific targets use `@connector/args` syntax.
- Examples: `web1.example.net`, `@docker/ubuntu:latest`, `@local`, `@ssh/jump-host/target-host`.
- Groups = dicts mapping group name → `(host_list, group_data)`. Data resolves global → group → host.

### Connectors
- Live `src/pyinfra/connectors/`.
- Built-in: `ssh`, `local`, `docker`, `dockerssh`, `chroot`, `terraform`, `vagrant`.
- All extend `BaseConnector`, implement `make_names_data`, `connect`, `run_shell_command`, file transfer methods.
- Custom connectors ship as separate packages, register via entry points; do not add to pyinfra core repo.

### Deploys
- `deploy.py` file holds operations to run against inventory.
- `@deploy` decorator (`src/pyinfra/api/deploy.py`) wraps function for reuse across CLI + direct API.

## Usage modes

1. **Ad-hoc**: `pyinfra inventory.py exec -- uptime`
2. **Declarative deploy**: `pyinfra inventory.py deploy.py`
3. **Programmatic API**: import `pyinfra.api`, drive `State` directly.

Common CLI flags:
- `--dry` — Prepare only, show diff, no execute.
- `--debug` / `-v` / `-vv` / `-vvv` — bump verbosity (raw shell output at `-vvv`).
- `--limit pattern` — restrict to host subset.
- `--data key=value` — inject inventory data.

## Project conventions for this repo

- Monorepo GitOps-first (see top-level `CLAUDE.md`). pyinfra here = imperative bootstrap + host-level provisioning outside Terraform + Kubernetes/Flux.
- Cluster naming: `{provider}-{region}-{env}` (e.g. `htz-fsn1-prod`).
- Hosts live on Tailscale tailnet `marlin-tet.ts.net`. Prefer Tailscale hostnames/IPs over public DNS for remote SSH.
- Never commit secrets, kubeconfigs, talosconfigs, private keys. Run pre-commit checks in root `CLAUDE.md` before commit.
- See `pyinfra/README.md` for quick-start, host-add recipe, and troubleshooting.

## Best practices

- **Be boring.** Use built-in operations + facts before custom.
- **Keep operations idempotent.** Check current state via fact, yield commands only when change required.
- **Use type hints** on new operation + fact code.
- **Default optional params to `None`**, not `""` or `0`. Check `if x is not None:` not truthiness.
- **No `assert` in operations.** `python -O` strips them. Raise explicit exceptions.
- **Use `QuoteString` / `MaskString`** from `pyinfra.api.command` when interpolating user-supplied values into shell commands. Handles escaping, keeps secrets out of logs.
- **Pull `host` / `state` from `pyinfra.context`**, don't thread through function signatures.
- **Reuse helpers** in `pyinfra.operations.util.file_utils` + friends before adding new utilities.
- **Test operations + facts via fixtures**, not Python unit tests. Fixtures live under `tests/operations/<module>.<op>/` + `tests/facts/<module>.<Fact>/` in upstream repo, auto-discovered.

## Gotchas

- `host.data["key"]` raises `TypeError` — `HostData` is not subscriptable. Use `host.data.get("key")` (or materialize a plain dict at the `@deploy` boundary) before passing to pure renderers.
- Apply a deploy: `cd pyinfra && uv run pyinfra -y inventory.py deploy.py --limit <fqdn>`. `-y` skips the interactive change-confirm prompt (required in non-TTY runs; otherwise pyinfra raises `EOFError`).
- Podman quadlet: `Memory=` / `CPUS=` / `PidsLimit=` in `[Container]` need podman ≥5.5 (quadlet rejects them with "unsupported key" on 5.4.x — Debian 13 ships 5.4.2). For portability put cgroup ceilings in `[Service]` as `MemoryMax=` / `CPUQuota=` / `TasksMax=` — quadlet passes `[Service]` through unchanged.
- Quadlet boot start = `[Install] WantedBy=multi-user.target` in the `.container`. Do NOT pass `enabled=True` to `systemd.service` — generator-produced units cannot be `systemctl enable`d ("Unit file does not exist").
- Quadlet rejects unknown `[Container]` keys silently: the generator skips the whole unit, so `daemon-reload` produces no `<name>.service` and `systemd.service` restart fails with "Unit <name>.service not found". `Network=` has a dedicated key but there is NO `PidMode=` key (podman 5.4) — share the host PID namespace via `PodmanArgs=--pid=host`. Anything the generator doesn't support goes through `PodmanArgs=`. Diagnose with `/usr/lib/podman/quadlet -dryrun` on the host.
- Quadlet `Exec=` is parsed by systemd, which expands env vars: a literal `$` must be written `$$` or regex anchors (`($|/)`, trailing `$`) get eaten as bogus expansions (see `tasks/nodeexporter.py` filesystem-collector excludes).
- `podman stats` LIMIT column reports host RAM (not the cgroup max) under `--cgroups=split` (quadlet default). Authoritative sources: `systemctl status <unit>` and `/sys/fs/cgroup/system.slice/<unit>/memory.{current,peak,max,events}`.
- `pyinfra -y` skips the "Detected changes:" diff preview entirely. Run `--dry` *without* `-y` to see the diff; add `-y` back for the apply (non-TTY runs still need it).
- Homelab Pi (`ben@rpi5-4cpu-16gb-home`) has no passwordless sudo. `pyinfra` apply needs an interactive TTY for the sudo prompt, or set `PYINFRA_SUDO_PASSWORD` before invocation. Claude Code Bash tool has no TTY → user must run apply via `!` prefix.
- NetworkManager keyfile renders (`tasks/network.py`): the `uuid=` value must match the existing in-memory connection's UUID, or NM creates a duplicate connection alongside it and two profiles fight for the interface. Read existing UUID via `nmcli -t -f connection.uuid con show '<id>'` and pin in host data.
- User-defined podman network = aardvark-dns binds `<bridge-gateway>:53`. Any host process bound to the wildcard `:53` (e.g. a DNS server published as `PublishPort=53:...` with no host IP) occupies `:53` on every bridge gateway and blocks aardvark, so the FIRST container on the network fails to start (`aardvark-dns failed to start: ... Address already in use`). Fix: bind the host DNS server to a specific IP, not the wildcard.
- `host.containers.internal` resolves to the bridge GATEWAY, not host loopback. A container CANNOT reach a host port bound to `127.0.0.1` via it. For container-to-container by name, put both on a user-defined network (aardvark-dns); to reach a host service, that service must bind the gateway/wildcard or a routable host IP.
- Lint/format: `uv run ruff check` / `uv run ruff format` (ruff is a dev dependency). Tests: `uv run pytest`.
- `tailscale serve` HTTPS for a Service: use the CLI form `tailscale serve --service=<svc> --https=<port> http://<backend>`, NOT `serve set-config <huJSON>`. The flattened set-config schema has one per-endpoint protocol field that conflates listener vs backend, so `{"tcp:443":"http://..."}` configures a PLAINTEXT http listener (no TLS) and `serve get-config` round-trips lossily. Symptom: browser TLS error / `curl: wrong version number`; `tailscale serve get-config` looks identical to a working service but the listener is http. Verified in vendored `ipn/conffile/serveconf.go` + `cmd/tailscale/cli/serve_v2.go`. Re-applying the same `--https` config is idempotent (tailscaled only rejects a serve-TYPE change on a port).

## When extending pyinfra

Missing operation or fact:
1. Check `~/vendor/pyinfra/src/pyinfra/operations/` + `.../facts/` for close match.
2. Prefer composing existing operations in `@deploy` wrapper before writing new `@operation`.
3. New operation unavoidable → model on similar built-in (e.g. `apt.packages`, `files.file`) for argument naming + idempotency style.
4. Custom connectors belong separate package, not this monorepo.

## Quick reference — key paths in the vendored upstream

- Deploy lifecycle + stages: `~/vendor/pyinfra/src/pyinfra/api/state.py`
- `@operation` decorator: `~/vendor/pyinfra/src/pyinfra/api/operation.py`
- Facts execution: `~/vendor/pyinfra/src/pyinfra/api/facts.py`
- Thread-local context (`host`, `state`, `config`, `inventory`): `~/vendor/pyinfra/src/pyinfra/context.py`
- Command types + shell-safety primitives: `~/vendor/pyinfra/src/pyinfra/api/command.py`
- Connector base class: `~/vendor/pyinfra/src/pyinfra/connectors/base.py`
- CLI entrypoint + gevent monkey-patch: `~/vendor/pyinfra/src/pyinfra_cli/main.py`
- Upstream contributor + AI usage policies: `~/vendor/pyinfra/AGENTS.md`, `~/vendor/pyinfra/AI_POLICY.md`