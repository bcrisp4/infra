# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Scaffold new cluster (creates both terraform and kubernetes directories)
./scripts/new-cluster.sh <cluster-name>

# Scaffold new app
./scripts/new-app.sh <app-name> [cluster-name]

# Bootstrap ArgoCD on a cluster
./scripts/bootstrap-argocd.sh <cluster-name>

# Terraform operations
cd terraform/<dir> && terraform init && terraform plan && terraform apply

# Update Helm dependencies for an app
cd kubernetes/apps/<app> && helm dependency update

# Get full values for a Helm chart
helm show values <chart>  # e.g., helm show values oci://registry/chart
```

## Architecture

This is an infrastructure monorepo for multi-cluster Kubernetes deployments using GitOps.

### Terraform Layer

- **terraform/bootstrap/** - Provisions Terraform Cloud workspaces and variable sets (uses local state)
- **terraform/global/** - Cross-cluster resources (Tailscale ACLs, auth keys). Clusters consume auth keys via `terraform_remote_state`
- **terraform/clusters/{cluster}/** - Per-cluster infrastructure (compute, storage, networking)
- **terraform/modules/k8s-cluster/{provider}/** - Reusable provider-specific cluster modules

TFC organization: `bc4`. One workspace per root module.

### Kubernetes Layer

- **kubernetes/apps/{app}/** - Umbrella Helm charts wrapping upstream dependencies. Values namespaced under dependency name.
- **kubernetes/clusters/{cluster}/apps/{app}/values.yaml** - Cluster-specific overrides
- **kubernetes/clusters/{cluster}/argocd/** - ArgoCD bootstrap and ApplicationSets

ArgoCD runs per-cluster and auto-discovers apps via Git generator scanning `kubernetes/clusters/{cluster}/apps/*`.

### Key Patterns

- Cluster naming: `{provider}-{region}-{env}` (e.g., `do-nyc3-prod`, `htz-fsn1-prod`)
- Provider abbreviations: `htz` (Hetzner), `do` (DigitalOcean), `aws`, `gcp`
- Tailscale auth keys flow: global terraform creates keys -> cluster terraform consumes via remote state
- Apps deploy by creating a values.yaml in `kubernetes/clusters/{cluster}/apps/{app}/`

## Current State

- Active cluster: `do-nyc3-prod` (DigitalOcean NYC3)
- Tailnet: `marlin-tet.ts.net`
- Spaces buckets configured for: Loki, Mimir, Tempo, Pyroscope

## Updating Terraform Provider Versions

To check and update provider versions to the latest, query the Terraform Registry API:

```
# Provider version lookup URLs
https://registry.terraform.io/v1/providers/digitalocean/digitalocean
https://registry.terraform.io/v1/providers/1Password/onepassword
https://registry.terraform.io/v1/providers/tailscale/tailscale
https://registry.terraform.io/v1/providers/hashicorp/tfe

# Terraform releases
https://releases.hashicorp.com/terraform/
```

Files to update when changing versions:
- `.terraform-version` - tfenv version (should match required_version)
- `terraform/bootstrap/main.tf` - tfe provider
- `terraform/global/main.tf` - tailscale provider
- `terraform/clusters/do-nyc3-prod/main.tf` - digitalocean, onepassword providers
- `terraform/clusters/_template/main.tf` - required_version only
- `README.md` - prerequisites section

Use pessimistic constraints (`~> X.Y`) pinned to minor version for stability while allowing patches.

## Implementation Notes

- Do not use em dashes in generated content
- Keep configurations minimal - avoid over-engineering
- Prefer explicit configuration over clever automation
- Templates use `_template` naming and are copied when creating new clusters/apps
