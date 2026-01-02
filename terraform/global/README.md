# Global Terraform Configuration

This directory manages cross-cluster resources, primarily Tailscale configuration.

## Resources Managed

- **Tailscale ACLs** - Access control policies for the tailnet
- **Tailscale Auth Keys** - Per-cluster preauthorized keys for node registration

## Prerequisites

1. Run `terraform/bootstrap` to create TFC workspace and variable sets
2. Set credentials in the `tailscale-credentials` variable set:
   - `TAILSCALE_API_KEY` (sensitive) - Tailscale API key
   - `TAILSCALE_TAILNET` - Pre-set to `marlin-tet.ts.net`

## Usage

### Adding a New Cluster

1. Add the cluster to `terraform.tfvars`:

```hcl
clusters = {
  "htz-fsn1-prod" = {
    tags = ["htz-fsn1-prod"]
  }
}
```

2. Apply the configuration:

```bash
terraform apply
```

3. The auth key will be available in outputs for the cluster Terraform to consume via remote state.

### Consuming Auth Keys in Cluster Terraform

```hcl
data "terraform_remote_state" "global" {
  backend = "remote"
  config = {
    organization = "bc4"
    workspaces = { name = "global" }
  }
}

# Access the key
local {
  tailscale_auth_key = data.terraform_remote_state.global.outputs.tailscale_auth_keys["htz-fsn1-prod"]
}
```

## Files

| File | Purpose |
|------|---------|
| `main.tf` | Provider configuration |
| `backend.tf` | Terraform Cloud backend |
| `variables.tf` | Input variables |
| `outputs.tf` | Exported values |
| `tailscale.tf` | Tailscale resources |
