# 1Password Terraform Provider

Reference for using the 1Password Terraform provider in this infrastructure.

## Overview

We use the 1Password Terraform provider v3.0+ to create and manage secrets that are later consumed by External Secrets Operator.

## Key Points

- **Use v3.0+** which uses pure SDK (no CLI required) - works in TFC without installing `op`
- Store OAuth credentials with `category = "login"` and use `username`/`password` fields
- The provider uses `OP_SERVICE_ACCOUNT_TOKEN` env var for authentication

## TFC Configuration

The provider credentials are managed via the `onepassword-credentials` variable set in TFC:

- `OP_SERVICE_ACCOUNT_TOKEN` (env, sensitive) - Service account token
- `onepassword_vault` (terraform) - Vault ID for storing secrets

## Example Usage

```hcl
resource "onepassword_item" "app_credentials" {
  vault    = var.onepassword_vault
  title    = "my-app-credentials"
  category = "login"

  username = "access-key-id"
  password = "secret-access-key"

  section {
    label = "Configuration"
    field {
      label = "endpoint"
      type  = "STRING"
      value = "https://api.example.com"
    }
  }
}
```

## Related

- [External Secrets Operator](external-secrets.md)
- [terraform/global/README.md](/terraform/global/README.md)
