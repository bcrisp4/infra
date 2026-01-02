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
└── scripts/                      # Helper scripts
```

## Quick Start

### Prerequisites

- Terraform >= 1.14
- Helm 3
- kubectl
- Terraform Cloud account (organization: `bc4`)
- Tailscale API key
- 1Password service account (for secrets management)

### 1. Bootstrap Terraform Cloud

```bash
# Configure Terraform Cloud credentials
terraform login

# Bootstrap TFC workspaces and variable sets
cd terraform/bootstrap
terraform init
terraform apply

# Set credentials in TFC UI:
# - https://app.terraform.io/app/bc4/settings/varsets
# - tailscale-credentials: TAILSCALE_API_KEY
# - digitalocean-credentials: DIGITALOCEAN_TOKEN, SPACES_ACCESS_KEY_ID, SPACES_SECRET_ACCESS_KEY
# - onepassword-credentials: OP_SERVICE_ACCOUNT_TOKEN, onepassword_vault
```

### 2. Set Up Global Resources

```bash
cd terraform/global
terraform init
terraform apply
```

### 3. Create a New Cluster

```bash
# Use the helper script
./scripts/new-cluster.sh htz-fsn1-prod

# Or manually copy templates
cp -r terraform/clusters/_template terraform/clusters/htz-fsn1-prod
cp -r kubernetes/clusters/_template kubernetes/clusters/htz-fsn1-prod
```

### 4. Deploy the Cluster

```bash
# Add provider module to terraform/modules/k8s-cluster/
# Configure terraform/clusters/htz-fsn1-prod/terraform.tfvars

cd terraform/clusters/htz-fsn1-prod
terraform init
terraform apply
```

### 5. Bootstrap ArgoCD

```bash
# Export kubeconfig
terraform output -raw kubeconfig > ~/.kube/htz-fsn1-prod

# Bootstrap ArgoCD
./scripts/bootstrap-argocd.sh htz-fsn1-prod
```

### 6. Add Applications

```bash
# Create app definition
./scripts/new-app.sh grafana htz-fsn1-prod

# Edit the app's Chart.yaml and values
# ArgoCD automatically deploys it
```

## Cluster Naming Convention

Format: `{provider}-{region}-{env}`

| Component | Options |
|-----------|---------|
| Provider | `htz` (Hetzner), `do` (DigitalOcean), `aws`, `gcp` |
| Region | Provider's native region codes |
| Environment | `prod`, `stg`, `dev` |

Examples: `htz-fsn1-prod`, `do-nyc1-dev`, `aws-eu-west-1-stg`

## Workflows

### Adding a New Cluster

1. Add cluster to `terraform/global/terraform.tfvars`
2. Apply global Terraform (creates Tailscale auth key)
3. Create cluster Terraform config
4. Apply cluster Terraform
5. Create Kubernetes cluster config
6. Bootstrap ArgoCD

### Adding a New Application

1. Create app in `kubernetes/apps/{app-name}/`
2. Add upstream chart dependency to `Chart.yaml`
3. Configure base values in `values.yaml`
4. For each cluster: create `kubernetes/clusters/{cluster}/apps/{app}/values.yaml`
5. ArgoCD automatically deploys

## Helper Scripts

| Script | Description |
|--------|-------------|
| `scripts/new-cluster.sh` | Scaffold a new cluster from templates |
| `scripts/new-app.sh` | Scaffold a new application |
| `scripts/bootstrap-argocd.sh` | Install ArgoCD on a cluster |
| `scripts/Makefile` | Common make targets |

## Documentation

- [TFC Bootstrap](terraform/bootstrap/README.md)
- [Terraform Modules](terraform/modules/k8s-cluster/README.md)
- [Global Terraform](terraform/global/README.md)
- [Cluster Template](terraform/clusters/_template/README.md)
- [Kubernetes Base](kubernetes/base/README.md)
- [Kubernetes Cluster Template](kubernetes/clusters/_template/README.md)
- [App Template](kubernetes/apps/_template/README.md)
