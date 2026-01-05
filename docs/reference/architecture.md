# Architecture Overview

High-level overview of the infrastructure architecture.

## Overview

This is an infrastructure monorepo for multi-cluster Kubernetes deployments using GitOps.

## Layers

### Terraform Layer

| Directory | Purpose |
|-----------|---------|
| `terraform/bootstrap/` | Provisions Terraform Cloud workspaces and variable sets (uses local state) |
| `terraform/global/` | Cross-cluster resources (Tailscale ACLs, OAuth clients, 1Password items) |
| `terraform/clusters/{cluster}/` | Per-cluster infrastructure (compute, storage, networking) |
| `terraform/modules/k8s-cluster/{provider}/` | Reusable provider-specific cluster modules |

TFC organization: `bc4`. One workspace per root module.

### Kubernetes Layer

| Directory | Purpose |
|-----------|---------|
| `kubernetes/apps/{app}/` | Umbrella Helm charts wrapping upstream dependencies |
| `kubernetes/clusters/{cluster}/apps/{app}/` | Per-app cluster config (config.yaml + values.yaml) |
| `kubernetes/clusters/{cluster}/argocd/` | ArgoCD bootstrap and manifests |
| `kubernetes/base/` | Shared Helm values, common configs |

ArgoCD runs per-cluster and auto-discovers apps via Git files generator scanning `kubernetes/clusters/{cluster}/apps/*/config.yaml`.

## Key Patterns

### Cluster Naming

Format: `{provider}-{region}-{env}`

| Provider | Abbreviation |
|----------|--------------|
| Hetzner | `htz` |
| DigitalOcean | `do` |
| AWS | `aws` |
| GCP | `gcp` |

Examples: `do-nyc3-prod`, `htz-fsn1-prod`, `aws-eu-west-1-stg`

### Auth Key Flow

```
global terraform creates keys -> cluster terraform consumes via remote state
```

### App Deployment

Apps deploy by creating `config.yaml` + `values.yaml` in `kubernetes/clusters/{cluster}/apps/{app}/`

## Current State

- **Active cluster:** `do-nyc3-prod` (DigitalOcean NYC3)
- **Tailnet:** `marlin-tet.ts.net`
- **Object storage:** Spaces buckets for Loki, Mimir, Tempo, Pyroscope

## Component Architecture

See [Metrics Architecture](metrics-architecture.md) for the observability stack details.

## Related

- [Deploy First App](../tutorials/deploy-first-app.md)
- [Add New Cluster](../tutorials/add-new-cluster.md)
