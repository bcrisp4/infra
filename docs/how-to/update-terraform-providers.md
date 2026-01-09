# Update Terraform Provider Versions

How to check for and update Terraform provider versions.

## Check Current Versions

Query the Terraform Registry API:

```bash
# DigitalOcean
curl -s https://registry.terraform.io/v1/providers/digitalocean/digitalocean | jq '.version'

# 1Password
curl -s https://registry.terraform.io/v1/providers/1Password/onepassword | jq '.version'

# Tailscale
curl -s https://registry.terraform.io/v1/providers/tailscale/tailscale | jq '.version'

# HashiCorp TFE
curl -s https://registry.terraform.io/v1/providers/hashicorp/tfe | jq '.version'
```

For Terraform core releases: https://releases.hashicorp.com/terraform/

## Files to Update

| File | What to Update |
|------|----------------|
| `.terraform-version` | tfenv version (should match required_version) |
| `terraform/bootstrap/main.tf` | tfe provider |
| `terraform/global/main.tf` | tailscale provider |
| `terraform/clusters/do-nyc3-prod/main.tf` | digitalocean, onepassword providers |
| `terraform/clusters/_template/main.tf` | required_version only |
| `README.md` | Prerequisites section |

## Update Procedure

1. Check latest versions using commands above
2. Update the relevant `required_providers` block:
   ```hcl
   terraform {
     required_providers {
       digitalocean = {
         source  = "digitalocean/digitalocean"
         version = "~> 2.50"  # Update this
       }
     }
   }
   ```
3. Run `terraform init -upgrade` in the affected directory
4. Run `terraform plan` to verify no breaking changes
5. Commit and push - TFC will apply automatically

## Dependabot

Dependabot automatically creates PRs for provider updates weekly. See [Dependabot](../reference/dependabot.md) for configuration.

## Related

- [Dependabot Configuration](../reference/dependabot.md)
- [Architecture Overview](../reference/architecture.md)
