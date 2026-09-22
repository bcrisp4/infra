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

No active Kubernetes clusters. Terraform manages only cross-cluster resources (Tailscale tailnet `marlin-tet.ts.net`, Cloudflare DNS, 1Password items). pyinfra manages homelab host provisioning (currently `rpi5-4cpu-16gb-home-1`).

On `rpi5-4cpu-16gb-home-1`:
- The router supplies DHCP to `eth0`. `pyinfra/tasks/network.py` manages the Netplan profile and removes the old static NetworkManager keyfile.
- `pyinfra/tasks/remove_dnsmasq.py` stops and purges the Pi's former DHCP service and removes its old config.
- BNS remains in the repo but has no active DNS role while the Pi uses a dynamic lease. Its installed Quadlet still binds `192.168.1.2` and currently fails. Give the Pi a DHCP reservation before you restore the role. Keep BNS off wildcard port `:53`, which conflicts with aardvark-dns on Podman networks. The Pi must not use BNS as its own resolver.
- PCIe Gen 3.0 forced on the external connector (`pyinfra/tasks/pcie.py`): patches `config.txt` (`dtparam=pciex1`/`pciex1_gen=3`) via a surgical marked block + one-shot backup, manual reboot. Gated on `pcie_gen3_enabled`, gen configurable (`pcie_gen`, default 3). External x1 link → 8.0 GT/s; internal RP1 x4 link stays Gen 2 (not config-controlled).
- Metrics stack (all rootful podman quadlets): Prometheus (`pyinfra/tasks/prometheus.py`, loopback-only `127.0.0.1:9090`, TSDB in plain rootfs dir `/var/lib/prometheus`, distroless uid 65532), Grafana 13 (`pyinfra/tasks/grafana.py`, `docker.io/grafana/grafana-oss`, loopback-only `127.0.0.1:3000`, sqlite+WAL state in plain rootfs dir `/var/lib/grafana`, image uid 472, Prometheus auto-provisioned as default datasource), node-exporter (`pyinfra/tasks/nodeexporter.py`, `Network=host`+`--pid=host`+host rootfs for real host metrics, binds `0.0.0.0:9100`).
- grafana-image-renderer (`pyinfra/tasks/image_renderer.py`, `docker.io/grafana/grafana-image-renderer`): remote PNG rendering for Grafana. Own `rendering` podman network (Grafana joins it too; Prometheus does not), NO published port, reachable only by Grafana. Shared auth token generated on-host (root:0600 `EnvironmentFile`, not in git) since Grafana 13 mandates a non-default `renderer_token`.
- `monitoring` podman network (`pyinfra/tasks/podman_network.py`, quadlet `.network`): shared bridge so Prometheus + Grafana resolve each other by ContainerName via aardvark-dns (Grafana datasource = `http://prometheus:9090`). node-exporter is NOT on it (host-net). Prometheus scrapes node-exporter via `host.containers.internal:9100`. `podman_network.py` renders multiple networks (`monitoring` + `rendering`), each gated on its own `<name>_network_enabled`. Scrape jobs are data-driven via `prometheus_scrape_targets` in the Pi's host dict in `pyinfra/inventory.py`; group data is split into `group_data/all.py` defaults + per-role flip files.
- Tailscale services (`pyinfra/tasks/tailscale_service.py`, `tailscale serve`): `svc:prometheus` + `svc:grafana`, each HTTPS `:443` reverse-proxied to the loopback-bound container. MagicDNS `prometheus.marlin-tet.ts.net` / `grafana.marlin-tet.ts.net`. Service objects + ACL grants + auto-approval in `terraform/global/tailscale.tf`. Only exposure path for those UIs (no LAN bind).

`docker/metadata-action {{version}}` strips the leading `v` from semver tags, so git tag `vX.Y.Z` publishes image tag `X.Y.Z` (not `vX.Y.Z`). Pin accordingly in host data.

The Pi defines no unqualified-search registries in `/etc/containers/registries.conf`, so every container image in host data MUST be fully-qualified (`docker.io/...`, `ghcr.io/...`, `quay.io/...`). A short name like `grafana/grafana-oss` fails to pull.

## Conventions

- Cluster naming: `{provider}-{region}-{env}` (e.g. `htz-fsn1-prod`, `do-nyc1-dev`).
- Do not use em dashes in generated content.
- Keep configurations minimal.
- Prefer explicit configuration over clever automation.

## Decision log

Before you propose an architecture, dependency, ownership, security, or workflow change, search `docs/decisions.md` for related decisions and revisit conditions.

After the user approves a consequential decision, propose a short decision-log entry. Do not record a new project policy without human confirmation.

## Implementation Notes

- Importing Cloudflare zones: `cf-terraforming generate` + `cf-terraforming import --modern-import-block` (after `terraform init`). Pass `--terraform-binary-path "$(which terraform)"` to prevent stray `terraform` binary download into working dir.
- Cloudflare provider v5: resource is `cloudflare_dns_record` (renamed from `cloudflare_record` in v4).
- Grafana dashboards in the "Infrastructure" folder are git-synced (`grafana/` dir, repo `bcrisp4/infra`, `main`, ~60s pull). Git Sync `write`/`branch` workflows commit UI edits back to git (or open PRs) — edits there persist, not reverted. New dashboards: create in that folder via UI, or commit JSON to `grafana/`. Gotcha: an *unmanaged* dashboard (created via API/MCP in another folder) cannot be moved into the managed folder — API returns `403 folder is managed by repo ... resource is not managed`; recreate it as a synced JSON instead. Prometheus datasource UID = `PBFA97CFB590B2093` (for ad-hoc MCP queries only — committed dashboards must use the `${datasource}` variable, never the literal UID); filter dashboard queries on `job`/`instance` for multi-instance support.
