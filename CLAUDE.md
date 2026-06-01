# CLAUDE.md

Guidance for Claude Code when working with this infrastructure monorepo.

## CRITICAL: NEVER COMMIT SECRETS OR STATE FILES

**NEVER commit:**
- `*.tfstate` / `*.tfstate.backup` / `*.tfvars` / `.terraform/`
- API keys, tokens, passwords, credentials
- `kubeconfig` / `talosconfig` / private keys (`*.pem`, `*.key`)
- `.env` files with real values

**Before EVERY commit:**
```bash
git diff --cached --name-only | grep -E '\.(tfstate|tfvars)$'
git diff --cached -S"SECRET" -S"TOKEN" -S"PASSWORD" -S"API_KEY"
```

## Architecture

Infrastructure monorepo for multi-cluster Kubernetes with GitOps.

**Terraform:**
- `bootstrap/` provisions Terraform Cloud workspaces and variable sets (local state).
- `global/` holds cross-cluster resources (Tailscale ACLs, OAuth clients, Cloudflare DNS, 1Password items).
- `modules/` contains reusable provisioning modules.
- `clusters/{cluster}/` (currently empty) will hold per-cluster infrastructure.

**Kubernetes:**
- Currently empty. Future GitOps tooling (Flux) and per-cluster manifests will land here.

**pyinfra:**
- `pyinfra/` holds imperative host provisioning (apt, OS settings, services) for hosts outside Terraform/Kubernetes. See `pyinfra/README.md` for quick start and `pyinfra/CLAUDE.md` for conventions.

## Current State

No active Kubernetes clusters. Terraform manages only cross-cluster resources (Tailscale tailnet `marlin-tet.ts.net`, Cloudflare DNS, 1Password items). pyinfra manages homelab host provisioning (currently `rpi5-4cpu-16gb-home`).

On `rpi5-4cpu-16gb-home`:
- bns (caching DNS forwarder + adblock, image `ghcr.io/bcrisp4/bns`) runs as a rootful podman quadlet via `pyinfra/tasks/bns.py`. Publishes DNS (`:53` UDP+TCP) + admin (`:9053`) bound to the LAN IP `192.168.1.2` only (`bns_listen_address`) — NOT the wildcard, NOT IPv6, NOT Tailscale. Wildcard would occupy `:53` on every podman bridge gateway and collide with aardvark-dns on the `monitoring` network (breaks Prometheus/Grafana startup). Pi itself MUST NOT use bns as its resolver (circular dep on image pull + upstream forwarding) — NM keyfile pins Pi resolver to `1.1.1.1`/`9.9.9.9`.
- dnsmasq runs DHCP-only (`port=0`) via `pyinfra/tasks/dhcp.py`. Hands out bns (`192.168.1.2`) as DHCP option 6 to LAN clients. Range `192.168.1.11-254`, lease 24h. CR1000A built-in DHCP must stay disabled (its admin UI cannot set DHCP option 6 — only start/end IP, WINS, lease, router's own upstream forwarder — hence the standalone DHCP server).
- Static IPv4 `192.168.1.2/24` via NM keyfile (`pyinfra/tasks/network.py`). IPv6 disabled (router IPv6 also disabled).
- Metrics stack (all rootful podman quadlets): Prometheus (`pyinfra/tasks/prometheus.py`, loopback-only `127.0.0.1:9090`, TSDB on dedicated LV `/var/lib/prometheus`, distroless uid 65532), Grafana 13 (`pyinfra/tasks/grafana.py`, `docker.io/grafana/grafana-oss`, loopback-only `127.0.0.1:3000`, sqlite+WAL state on dedicated LV `/var/lib/grafana`, image uid 472, Prometheus auto-provisioned as default datasource), node-exporter (`pyinfra/tasks/nodeexporter.py`, `Network=host`+`--pid=host`+host rootfs for real host metrics, binds `0.0.0.0:9100`).
- grafana-image-renderer (`pyinfra/tasks/image_renderer.py`, `docker.io/grafana/grafana-image-renderer`): remote PNG rendering for Grafana. Own `rendering` podman network (Grafana joins it too; Prometheus does not), NO published port, reachable only by Grafana. Shared auth token generated on-host (root:0600 `EnvironmentFile`, not in git) since Grafana 13 mandates a non-default `renderer_token`.
- `monitoring` podman network (`pyinfra/tasks/podman_network.py`, quadlet `.network`): shared bridge so Prometheus + Grafana resolve each other by ContainerName via aardvark-dns (Grafana datasource = `http://prometheus:9090`). node-exporter is NOT on it (host-net); Prometheus scrapes node-exporter via `host.containers.internal:9100` and bns via `192.168.1.2:9053` (LAN IP, since bns left the wildcard). `podman_network.py` now renders multiple networks (`monitoring` + `rendering`), each gated on its own `<name>_network_enabled`.
- Tailscale services (`pyinfra/tasks/tailscale_service.py`, `tailscale serve`): `svc:prometheus` + `svc:grafana`, each HTTPS `:443` reverse-proxied to the loopback-bound container. MagicDNS `prometheus.marlin-tet.ts.net` / `grafana.marlin-tet.ts.net`. Service objects + ACL grants + auto-approval in `terraform/global/tailscale.tf`. Only exposure path for those UIs (no LAN bind).

`docker/metadata-action {{version}}` strips the leading `v` from semver tags, so git tag `vX.Y.Z` publishes image tag `X.Y.Z` (not `vX.Y.Z`). Pin accordingly in host data.

The Pi defines no unqualified-search registries in `/etc/containers/registries.conf`, so every container image in host data MUST be fully-qualified (`docker.io/...`, `ghcr.io/...`, `quay.io/...`). A short name like `grafana/grafana-oss` fails to pull.

## Conventions

- Cluster naming: `{provider}-{region}-{env}` (e.g. `htz-fsn1-prod`, `do-nyc1-dev`).
- Do not use em dashes in generated content.
- Keep configurations minimal.
- Prefer explicit configuration over clever automation.

## Implementation Notes

- Importing Cloudflare zones: `cf-terraforming generate` + `cf-terraforming import --modern-import-block` (after `terraform init`). Pass `--terraform-binary-path "$(which terraform)"` to prevent stray `terraform` binary download into working dir.
- Cloudflare provider v5: resource is `cloudflare_dns_record` (renamed from `cloudflare_record` in v4).
- Grafana dashboards in the "Infrastructure" folder are git-synced (`grafana/` dir, repo `bcrisp4/infra`, `main`, ~60s pull). Git Sync `write`/`branch` workflows commit UI edits back to git (or open PRs) — edits there persist, not reverted. New dashboards: create in that folder via UI, or commit JSON to `grafana/`. Gotcha: an *unmanaged* dashboard (created via API/MCP in another folder) cannot be moved into the managed folder — API returns `403 folder is managed by repo ... resource is not managed`; recreate it as a synced JSON instead. Prometheus datasource UID = `PBFA97CFB590B2093` (for ad-hoc MCP queries only — committed dashboards must use the `${datasource}` variable, never the literal UID); filter dashboard queries on `job`/`instance` for multi-instance support.
