# Architecture Overview

High-level overview of the infrastructure architecture.

## Overview

This is an infrastructure monorepo. Currently only cross-cluster resources are managed; per-cluster Kubernetes config will be reintroduced via Flux.

## Layers

### Terraform Layer

| Directory | Purpose |
|-----------|---------|
| `terraform/bootstrap/` | Provisions Terraform Cloud workspaces and variable sets (uses local state) |
| `terraform/global/` | Cross-cluster resources (Tailscale ACLs, OAuth clients, Cloudflare DNS, 1Password items) |
| `terraform/clusters/{cluster}/` | Per-cluster infrastructure (compute, storage, networking) |
| `terraform/modules/k8s-cluster/{provider}/` | Reusable provider-specific cluster modules |

TFC organization: `bc4`. One workspace per root module.

### Kubernetes Layer

Empty. Future Flux-based config and per-cluster manifests will be reintroduced here.

## Key Patterns

### Cluster Naming

Format: `{provider}-{region}-{env}`

| Provider | Abbreviation |
|----------|--------------|
| Hetzner | `htz` |
| DigitalOcean | `do` |
| AWS | `aws` |
| GCP | `gcp` |

Examples: `htz-fsn1-prod`, `do-nyc1-dev`, `aws-eu-west-1-stg`.

### Auth Key Flow

```
global terraform creates keys -> cluster terraform consumes via remote state
```
