# Infrastructure Monorepo

Personal infrastructure configuration for self-hosted applications across multiple Kubernetes clusters.

## Repository Structure

```
infra/
├── terraform/
│   ├── bootstrap/                # TFC workspace/variable set provisioning
│   ├── modules/
│   │   └── k8s-cluster/          # Reusable cluster provisioning modules
│   ├── clusters/
│   │   └── {cluster-name}/       # Per-cluster Terraform configs
│   └── global/                   # Cross-cluster resources (Tailscale)
│
├── kubernetes/
│   ├── base/                     # Shared Helm values, common configs
│   ├── clusters/
│   │   └── {cluster-name}/
│   │       ├── argocd/           # ArgoCD bootstrap + ApplicationSets
│   │       ├── apps/             # Cluster-specific app value overrides
│   │       └── cluster.yaml      # Cluster metadata
│   └── apps/                     # Shared app definitions (Helm charts)
│
├── docs/                         # Documentation (see below)
└── scripts/                      # Helper scripts
```

## Documentation

See [docs/README.md](docs/README.md) for comprehensive documentation including:

- **[Tutorials](docs/tutorials/)** - Step-by-step guides for beginners
- **[How-to Guides](docs/how-to/)** - Task-oriented recipes
- **[Reference](docs/reference/)** - Technical specifications
- **[Troubleshooting](docs/troubleshooting/)** - Debugging guides

## Quick Start

### Prerequisites

- Terraform >= 1.14
- Helm 3
- kubectl
- Terraform Cloud account (organization: `bc4`)
- Tailscale API key
- 1Password service account (for secrets management)

### Getting Started

1. **New to this repo?** Start with [Add a New Cluster](docs/tutorials/add-new-cluster.md)
2. **Deploying apps?** See [Deploy Your First App](docs/tutorials/deploy-first-app.md)
3. **Quick reference?** Check the [Architecture Overview](docs/reference/architecture.md)

## Cluster Naming Convention

Format: `{provider}-{region}-{env}`

| Component | Options |
|-----------|---------|
| Provider | `htz` (Hetzner), `do` (DigitalOcean), `aws`, `gcp` |
| Region | Provider's native region codes |
| Environment | `prod`, `stg`, `dev` |

Examples: `htz-fsn1-prod`, `do-nyc1-dev`, `aws-eu-west-1-stg`

## Helper Scripts

| Script | Description |
|--------|-------------|
| `scripts/new-cluster.sh` | Scaffold a new cluster from templates |
| `scripts/new-app.sh` | Scaffold a new application |
| `scripts/bootstrap-argocd.sh` | Install ArgoCD on a cluster |
