# Tutorial: Add a New Cluster

This tutorial walks you through adding a new Kubernetes cluster to the infrastructure.

## What You'll Learn

- How cluster infrastructure is organized
- How to provision infrastructure with Terraform
- How to bootstrap ArgoCD for GitOps
- How Tailscale provides secure connectivity

## Prerequisites

- Terraform CLI installed
- kubectl installed
- Terraform Cloud account with access to the `bc4` organization
- Cloud provider credentials (DigitalOcean, Hetzner, etc.)
- Tailscale API key

## Overview

Adding a cluster involves three main steps:

1. **Global Terraform** - Create Tailscale auth key for the cluster
2. **Cluster Terraform** - Provision the Kubernetes cluster
3. **Kubernetes Config** - Bootstrap ArgoCD and configure apps

## Step 1: Register the Cluster in Global Terraform

First, register the new cluster to create its Tailscale auth key.

Edit `terraform/global/terraform.tfvars`:

```hcl
clusters = {
  "do-nyc3-prod" = {
    tags = ["do-nyc3-prod"]
  }
  # Add your new cluster:
  "htz-fsn1-prod" = {
    tags = ["htz-fsn1-prod"]
  }
}
```

Apply the changes:

```bash
cd terraform/global
terraform init
terraform plan
terraform apply
```

This creates a Tailscale auth key that the cluster will use to join the tailnet.

## Step 2: Create the Cluster Terraform

Use the helper script:

```bash
./scripts/new-cluster.sh htz-fsn1-prod
```

Or manually copy the template:

```bash
cp -r terraform/clusters/_template terraform/clusters/htz-fsn1-prod
```

### Configure the Backend

Edit `terraform/clusters/htz-fsn1-prod/backend.tf`:

```hcl
terraform {
  cloud {
    organization = "bc4"
    workspaces {
      name = "htz-fsn1-prod"
    }
  }
}
```

### Add Provider Module

Ensure the provider module exists in `terraform/modules/k8s-cluster/<provider>/`.

Edit `terraform/clusters/htz-fsn1-prod/main.tf` to use the correct module:

```hcl
module "cluster" {
  source = "../../modules/k8s-cluster/hetzner"

  cluster_name       = var.cluster_name
  tailscale_auth_key = data.terraform_remote_state.global.outputs.tailscale_auth_keys[var.cluster_name]

  # Provider-specific variables
  location = "fsn1"
  # ...
}
```

### Create TFC Workspace

Add the workspace to `terraform/bootstrap/main.tf` and apply bootstrap, or create manually in TFC UI.

### Apply Cluster Terraform

```bash
cd terraform/clusters/htz-fsn1-prod
terraform init
terraform plan
terraform apply
```

## Step 3: Export Kubeconfig

After Terraform completes, export the kubeconfig:

```bash
terraform output -raw kubeconfig > ~/.kube/htz-fsn1-prod
export KUBECONFIG=~/.kube/htz-fsn1-prod
```

Verify connectivity:

```bash
kubectl get nodes
```

## Step 4: Create Kubernetes Cluster Config

Use the helper script:

```bash
./scripts/new-cluster.sh htz-fsn1-prod
```

Or manually:

```bash
cp -r kubernetes/clusters/_template kubernetes/clusters/htz-fsn1-prod
```

### Update ArgoCD Configuration

Edit `kubernetes/clusters/htz-fsn1-prod/argocd/bootstrap/values.yaml`:

```yaml
cluster:
  name: htz-fsn1-prod

argo-cd:
  server:
    ingress:
      enabled: true
      ingressClassName: tailscale
      hostname: argocd-htz-fsn1-prod
      tls: true
```

### Update ApplicationSet

Edit `kubernetes/clusters/htz-fsn1-prod/argocd/manifests/apps.yaml`:

Replace `_template` with `htz-fsn1-prod` in the Git files generator path:

```yaml
generators:
  - git:
      repoURL: https://github.com/yourorg/infra.git
      revision: HEAD
      files:
        - path: "kubernetes/clusters/htz-fsn1-prod/apps/*/config.yaml"
```

### Update Helm Dependencies

```bash
cd kubernetes/clusters/htz-fsn1-prod/argocd/bootstrap
helm dependency update
```

## Step 5: Bootstrap ArgoCD

Use the helper script:

```bash
./scripts/bootstrap-argocd.sh htz-fsn1-prod
```

Or manually:

```bash
kubectl create namespace argocd
cd kubernetes/clusters/htz-fsn1-prod/argocd/bootstrap
helm install argocd . -n argocd
```

## Step 6: Apply Initial Manifests

Apply the ArgoCD self-management and ApplicationSet:

```bash
kubectl apply -f kubernetes/clusters/htz-fsn1-prod/argocd/manifests/
```

ArgoCD will now manage itself and auto-discover apps.

## Step 7: Commit and Push

```bash
git add terraform/global kubernetes/clusters/htz-fsn1-prod
git commit -m "Add htz-fsn1-prod cluster"
git push
```

## Step 8: Verify

### Check ArgoCD UI

Access via Tailscale:

```
https://argocd-htz-fsn1-prod.<tailnet>.ts.net
```

Get the initial admin password:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

### Check Tailscale

The cluster should appear in your Tailscale admin console.

## Naming Convention

Cluster names follow the format: `{provider}-{region}-{env}`

| Provider | Abbreviation | Example |
|----------|--------------|---------|
| Hetzner | `htz` | `htz-fsn1-prod` |
| DigitalOcean | `do` | `do-nyc3-prod` |
| AWS | `aws` | `aws-eu-west-1-stg` |
| GCP | `gcp` | `gcp-us-central1-dev` |

## Next Steps

- Deploy your first app: [Deploy Your First App](deploy-first-app.md)
- Set up GitHub webhooks for instant sync
- Configure monitoring and logging

## Related

- [Architecture Overview](../reference/architecture.md)
- [terraform/bootstrap/README.md](/terraform/bootstrap/README.md)
- [terraform/global/README.md](/terraform/global/README.md)
