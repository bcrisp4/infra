# Global Terraform Configuration

This directory manages shared tailnet, DNS, and bsync staging and production resources.

## Resources Managed

- Tailscale ACLs and per-cluster auth keys control tailnet and node access.
- Cloudflare serves authoritative DNS records for `thecrisp.io`, `bencrisp.co.uk`, and `bc4.uk`.
- bsync staging and production use Terraform-managed Access applications, policies, and Worker custom domains. Wrangler owns Worker code and Durable Object classes. bsync tenant storage uses Durable Object SQLite, not D1.
- AWS Route 53 Domains manages `bc4.uk` registration and nameservers.
- The AWS Route 53 hosted zone remains for rollback during DNS propagation.

## Prerequisites

1. Run `terraform/bootstrap` to create TFC workspace and variable sets
2. Set credentials in the `tailscale-credentials` variable set:
   - `TAILSCALE_API_KEY` (sensitive) - Tailscale API key
   - `TAILSCALE_TAILNET` - Pre-set to `marlin-tet.ts.net`
3. Apply the bootstrap configuration to attach the `aws-route53-credentials` variable set.
   - `TFC_AWS_PROVIDER_AUTH` - Set to `true`
   - `TFC_AWS_RUN_ROLE_ARN` - AWS IAM role for the `global` workspace
   - The role policy allows `route53domains:GetDomainDetail`, `route53domains:ListTagsForDomain`, and `route53domains:UpdateDomainNameservers` on `*`. Route 53 Domains does not support resource-level IAM scoping.

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
| `cloudflare.tf` | Cloudflare zone lookup and DNS records |
| `bsync.tf` | bsync Access applications, policies, and Worker custom domains. Worker code and Durable Object classes stay in `~/src/bsync`. |
| `route53.tf` | AWS Route 53 registration and hosted zone |
| `tailscale.tf` | Tailscale resources |
