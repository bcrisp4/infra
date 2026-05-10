# Infrastructure Monorepo

Personal infrastructure configuration for cross-cluster resources and (eventually) self-hosted applications on Kubernetes.

## Repository Structure

```
infra/
├── terraform/
│   ├── bootstrap/                # TFC workspace/variable set provisioning
│   ├── global/                   # Cross-cluster resources (Tailscale, Cloudflare, 1Password)
│   ├── modules/                  # Reusable provisioning modules
│   └── clusters/                 # Per-cluster Terraform configs (empty)
├── kubernetes/                   # Future Flux-based config (empty)
└── docs/                         # Documentation
```

## Documentation

See [docs/README.md](docs/README.md).

## Prerequisites

- Terraform >= 1.14
- Terraform Cloud account (organization: `bc4`)
- Tailscale API key
- 1Password service account (for secrets management)

## Cluster Naming Convention

Format: `{provider}-{region}-{env}`

| Component | Options |
|-----------|---------|
| Provider | `htz` (Hetzner), `do` (DigitalOcean), `aws`, `gcp` |
| Region | Provider's native region codes |
| Environment | `prod`, `stg`, `dev` |

Examples: `htz-fsn1-prod`, `do-nyc1-dev`, `aws-eu-west-1-stg`.
