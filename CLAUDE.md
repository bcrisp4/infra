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

## Conventions

- Cluster naming: `{provider}-{region}-{env}` (e.g. `htz-fsn1-prod`, `do-nyc1-dev`).
- Do not use em dashes in generated content.
- Keep configurations minimal.
- Prefer explicit configuration over clever automation.

## Implementation Notes

- Importing Cloudflare zones: `cf-terraforming generate` + `cf-terraforming import --modern-import-block` (after `terraform init`). Pass `--terraform-binary-path "$(which terraform)"` to prevent stray `terraform` binary download into working dir.
- Cloudflare provider v5: resource is `cloudflare_dns_record` (renamed from `cloudflare_record` in v4).
