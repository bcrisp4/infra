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
- bns (caching DNS forwarder + adblock, image `ghcr.io/bcrisp4/bns`) runs as a rootful podman quadlet via `pyinfra/tasks/bns.py`. Listens on host `:53` (UDP+TCP) and admin `:9090`. Pi itself MUST NOT use bns as its resolver (circular dep on image pull + upstream forwarding) — NM keyfile pins Pi resolver to `1.1.1.1`/`9.9.9.9`.
- dnsmasq runs DHCP-only (`port=0`) via `pyinfra/tasks/dhcp.py`. Hands out bns (`192.168.1.2`) as DHCP option 6 to LAN clients. Range `192.168.1.11-254`, lease 24h. CR1000A built-in DHCP must stay disabled (its admin UI cannot set DHCP option 6 — only start/end IP, WINS, lease, router's own upstream forwarder — hence the standalone DHCP server).
- Static IPv4 `192.168.1.2/24` via NM keyfile (`pyinfra/tasks/network.py`). IPv6 disabled (router IPv6 also disabled).

`docker/metadata-action {{version}}` strips the leading `v` from semver tags, so git tag `vX.Y.Z` publishes image tag `X.Y.Z` (not `vX.Y.Z`). Pin accordingly in host data.

## Conventions

- Cluster naming: `{provider}-{region}-{env}` (e.g. `htz-fsn1-prod`, `do-nyc1-dev`).
- Do not use em dashes in generated content.
- Keep configurations minimal.
- Prefer explicit configuration over clever automation.

## Implementation Notes

- Importing Cloudflare zones: `cf-terraforming generate` + `cf-terraforming import --modern-import-block` (after `terraform init`). Pass `--terraform-binary-path "$(which terraform)"` to prevent stray `terraform` binary download into working dir.
- Cloudflare provider v5: resource is `cloudflare_dns_record` (renamed from `cloudflare_record` in v4).
