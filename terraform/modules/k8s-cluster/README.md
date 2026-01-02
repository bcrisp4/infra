# Kubernetes Cluster Modules

This directory contains provider-specific Terraform modules for provisioning Kubernetes clusters.

## Structure

```
k8s-cluster/
├── <provider>/           # Provider-specific module (e.g., hetzner/, aws/, gcp/)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   └── README.md
└── README.md             # This file
```

## Adding a New Provider Module

1. Create a new directory for the provider (e.g., `hetzner/`, `digitalocean/`)
2. Implement the module with these standard outputs:
   - `kubeconfig` - Kubernetes cluster kubeconfig (sensitive)
   - `cluster_endpoint` - API server endpoint URL
   - `cluster_name` - Name of the cluster
3. Accept a `tailscale_auth_key` input for node registration (if using Tailscale)
4. Document provider-specific requirements in the module's README

## Standard Variables

All cluster modules should accept these common variables:

| Variable | Type | Description |
|----------|------|-------------|
| `cluster_name` | string | Name of the cluster |
| `tailscale_auth_key` | string | Tailscale auth key for node registration |
| `kubernetes_version` | string | Kubernetes version to deploy |

## Usage

Reference modules from cluster configurations:

```hcl
module "cluster" {
  source = "../../modules/k8s-cluster/<provider>"

  cluster_name       = var.cluster_name
  tailscale_auth_key = data.terraform_remote_state.global.outputs.tailscale_auth_keys[var.cluster_name]
  # ... provider-specific variables
}
```
