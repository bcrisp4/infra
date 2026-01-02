# Cluster Terraform Template

Template for provisioning a new Kubernetes cluster.

## Setup Instructions

### 1. Prerequisites

Ensure the cluster is registered in global Terraform:

```hcl
# In terraform/global/terraform.tfvars
clusters = {
  "{{cluster_name}}" = {
    tags = ["{{cluster_name}}"]
  }
}
```

Apply global Terraform to create the Tailscale auth key.

### 2. Create Cluster Directory

```bash
cp -r _template ../{{cluster_name}}
cd ../{{cluster_name}}
```

### 3. Configure Backend

Edit `backend.tf` and replace `{{cluster_name}}` with the actual cluster name.

Create the Terraform Cloud workspace:
- Name: `{{cluster_name}}`
- Organization: `bc4`

### 4. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your configuration
```

### 5. Add Provider Module

1. Ensure the provider module exists in `terraform/modules/k8s-cluster/<provider>/`
2. Uncomment and configure the module in `main.tf`
3. Add any required provider configuration

### 6. Deploy

```bash
terraform init
terraform plan
terraform apply
```

## Naming Convention

Cluster names follow the format: `{provider}-{region}-{env}`

| Provider | Example |
|----------|---------|
| Hetzner | `htz-fsn1-prod` |
| DigitalOcean | `do-nyc1-dev` |
| AWS | `aws-eu-west-1-stg` |

## Outputs

After deployment, the cluster outputs:

- `kubeconfig` - Use to access the cluster
- `cluster_endpoint` - API server URL
- `cluster_name` - Cluster identifier

## Next Steps

After Terraform apply:

1. Export kubeconfig: `terraform output -raw kubeconfig > ~/.kube/{{cluster_name}}`
2. Create Kubernetes cluster config: `cp -r ../../kubernetes/clusters/_template ../../kubernetes/clusters/{{cluster_name}}`
3. Bootstrap ArgoCD (see kubernetes cluster README)
