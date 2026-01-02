# Infrastructure Monorepo Specification

This document describes the design and structure of a personal infrastructure monorepo. Use this as a guide to scaffold and implement the repository.

## Overview

A monorepo containing all infrastructure configuration for self-hosted applications across multiple Kubernetes clusters. Single user, personal use only.

## Repository Structure

```
infra/
├── terraform/
│   ├── modules/
│   │   └── k8s-cluster/          # Reusable cluster provisioning module
│   ├── clusters/
│   │   ├── htz-fsn1-prod/        # Per-cluster Terraform configs
│   │   │   ├── main.tf
│   │   │   ├── backend.tf
│   │   │   └── terraform.tfvars
│   │   └── do-nyc1-prod/
│   │       ├── main.tf
│   │       ├── backend.tf
│   │       └── terraform.tfvars
│   └── global/                   # Cross-cluster resources
│       ├── main.tf
│       ├── backend.tf
│       ├── terraform.tfvars
│       └── tailscale.tf
│
├── kubernetes/
│   ├── base/                     # Shared Helm values, common configs
│   ├── clusters/
│   │   ├── htz-fsn1-prod/
│   │   │   ├── argocd/
│   │   │   │   ├── bootstrap/    # ArgoCD installation + root ApplicationSet
│   │   │   │   └── applicationsets/
│   │   │   ├── apps/             # Cluster-specific app value overrides
│   │   │   └── cluster.yaml      # Cluster metadata
│   │   └── do-nyc1-prod/
│   │       ├── argocd/
│   │       │   ├── bootstrap/
│   │       │   └── applicationsets/
│   │       ├── apps/
│   │       └── cluster.yaml
│   └── apps/                     # Shared app definitions
│       ├── grafana/
│       │   ├── Chart.yaml        # Umbrella chart referencing upstream
│       │   └── values.yaml       # Base values
│       └── example-app/
│           ├── Chart.yaml
│           └── values.yaml
│
└── scripts/                      # Helper scripts, Makefiles
```

## Cluster Naming Convention

Format: `{provider}-{region}-{env}`

### Provider Abbreviations

| Provider     | Abbreviation |
|--------------|--------------|
| Hetzner      | `htz`        |
| DigitalOcean | `do`         |
| AWS          | `aws`        |
| GCP          | `gcp`        |

### Region Codes

Use the cloud provider's native region codes:

- Hetzner: `fsn1`, `nbg1`, `hel1`, etc.
- DigitalOcean: `nyc1`, `sfo1`, `ams3`, etc.
- AWS: `eu-west-1`, `us-east-1`, etc.
- GCP: `us-central1`, `europe-west1`, etc.

### Environments

| Environment | Abbreviation |
|-------------|--------------|
| Production  | `prod`       |
| Staging     | `stg`        |
| Development | `dev`        |

### Examples

- `htz-fsn1-prod` - Hetzner Falkenstein production
- `do-nyc1-dev` - DigitalOcean NYC development
- `aws-eu-west-1-stg` - AWS Ireland staging

## Terraform Configuration

### State Management

Use Terraform Cloud for remote state management.

### Workspaces

One Terraform Cloud workspace per Terraform root module:

| Directory                      | TF Cloud Workspace |
|--------------------------------|--------------------|
| `terraform/global/`            | `global`           |
| `terraform/clusters/htz-fsn1-prod/` | `htz-fsn1-prod` |
| `terraform/clusters/do-nyc1-prod/`  | `do-nyc1-prod`  |

### Backend Configuration

Each Terraform root module needs a `backend.tf`:

```hcl
terraform {
  cloud {
    organization = "YOUR_ORG"  # User needs to set this
    
    workspaces {
      name = "WORKSPACE_NAME"  # Matches directory/cluster name
    }
  }
}
```

### Module Structure

The `terraform/modules/k8s-cluster/` module should be provider-agnostic where possible, with provider-specific submodules if needed:

```
terraform/modules/
├── k8s-cluster/
│   ├── hetzner/
│   ├── digitalocean/
│   └── aws/
```

### Global Resources

`terraform/global/` manages cross-cluster resources:

- Tailscale configuration (ACLs, auth keys, DNS settings)
- Shared DNS zones
- Any other resources that span clusters

### Tailscale Integration

The global Terraform config should:

1. Define Tailscale ACLs and access policies
2. Generate reusable, preauthorized auth keys per cluster with appropriate tags
3. Export auth keys so cluster Terraform can reference them via remote state

Example structure in `terraform/global/tailscale.tf`:

```hcl
resource "tailscale_acl" "this" {
  # ACL configuration
}

resource "tailscale_tailnet_key" "htz_fsn1_prod" {
  reusable      = true
  preauthorized = true
  tags          = ["tag:k8s-node", "tag:htz-fsn1-prod"]
}

output "tailscale_auth_keys" {
  value = {
    htz-fsn1-prod = tailscale_tailnet_key.htz_fsn1_prod.key
  }
  sensitive = true
}
```

Cluster Terraform can then consume this:

```hcl
data "terraform_remote_state" "global" {
  backend = "remote"
  config = {
    organization = "YOUR_ORG"
    workspaces = {
      name = "global"
    }
  }
}

# Use: data.terraform_remote_state.global.outputs.tailscale_auth_keys["htz-fsn1-prod"]
```

## Kubernetes Configuration

### Helm-Based Deployments

All Kubernetes applications are deployed via Helm charts.

### App Structure

Each app in `kubernetes/apps/` is a thin umbrella chart:

```yaml
# kubernetes/apps/grafana/Chart.yaml
apiVersion: v2
name: grafana
version: 1.0.0
dependencies:
  - name: grafana
    version: "7.x.x"
    repository: "https://grafana.github.io/helm-charts"
```

```yaml
# kubernetes/apps/grafana/values.yaml
# Base values shared across all clusters
grafana:
  persistence:
    enabled: true
```

### Cluster-Specific Overrides

Cluster-specific values go in `kubernetes/clusters/{cluster}/apps/{app}/values.yaml`:

```yaml
# kubernetes/clusters/htz-fsn1-prod/apps/grafana/values.yaml
grafana:
  ingress:
    hosts:
      - grafana.htz-fsn1.example.com
```

### Cluster Metadata

Each cluster has a `cluster.yaml` with metadata:

```yaml
# kubernetes/clusters/htz-fsn1-prod/cluster.yaml
name: htz-fsn1-prod
provider: hetzner
region: fsn1
environment: prod
```

## ArgoCD Configuration

### One ArgoCD Per Cluster

Each Kubernetes cluster runs its own ArgoCD instance. ArgoCD config is nested under the cluster directory.

### Bootstrap Process

1. Terraform creates the cluster
2. Manually apply `kubernetes/clusters/{cluster}/argocd/bootstrap/` to install ArgoCD
3. Bootstrap includes a root ApplicationSet that watches for apps

### ApplicationSet Pattern

The root ApplicationSet should:

1. Scan `kubernetes/clusters/{cluster}/apps/` for enabled apps
2. For each app found, generate an Application that:
   - References the chart in `kubernetes/apps/{app}/`
   - Applies cluster-specific values from `kubernetes/clusters/{cluster}/apps/{app}/values.yaml`

Example ApplicationSet structure:

```yaml
# kubernetes/clusters/htz-fsn1-prod/argocd/applicationsets/apps.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-apps
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/USER/infra.git
        revision: HEAD
        directories:
          - path: kubernetes/clusters/htz-fsn1-prod/apps/*
  template:
    metadata:
      name: '{{path.basename}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/USER/infra.git
        targetRevision: HEAD
        path: 'kubernetes/apps/{{path.basename}}'
        helm:
          valueFiles:
            - '../../clusters/htz-fsn1-prod/apps/{{path.basename}}/values.yaml'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path.basename}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

## Deployment Workflow

### New Cluster

1. Create Terraform config in `terraform/clusters/{cluster-name}/`
2. Create Terraform Cloud workspace
3. Add Tailscale auth key resource in `terraform/global/tailscale.tf`
4. Apply global Terraform
5. Apply cluster Terraform
6. Create `kubernetes/clusters/{cluster-name}/` structure
7. Apply ArgoCD bootstrap

### New Application

1. Create app definition in `kubernetes/apps/{app-name}/`
2. For each cluster that should run it, create `kubernetes/clusters/{cluster}/apps/{app-name}/values.yaml`
3. ArgoCD automatically picks it up via ApplicationSet

## Implementation Notes

- Do not use em dashes in any generated content
- Keep configurations minimal and avoid over-engineering
- Prefer explicit configuration over clever automation
- Add README.md files in key directories explaining their purpose
