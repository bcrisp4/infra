# Terraform Cloud Bootstrap

This configuration bootstraps Terraform Cloud workspaces and variable sets.

> **Warning:** The local state file (`terraform.tfstate`) contains sensitive information
> including TFC variable set IDs and references. It is gitignored but take care not to
> expose it. Consider migrating state to TFC after bootstrap if needed.

## Prerequisites

- Terraform Cloud account
- Organization `bc4` already created
- TFC API token with organization-level permissions

## Usage

### 1. Set TFC Token

```bash
export TFE_TOKEN="your-tfc-token"
```

Or create a token at: https://app.terraform.io/app/settings/tokens

### 2. Initialize and Apply

```bash
terraform init
terraform plan
terraform apply
```

### 3. Configure Credentials

After bootstrap, set credentials in the TFC variable sets:

1. Go to https://app.terraform.io/app/bc4/settings/varsets

2. Edit **tailscale-credentials**:
   - `TAILSCALE_API_KEY` (env, sensitive) - Your Tailscale API key
   - `TAILSCALE_TAILNET` is pre-set to `marlin-tet.ts.net`

3. Edit **digitalocean-credentials**:
   - `DIGITALOCEAN_TOKEN` (env, sensitive) - DigitalOcean API token
   - `SPACES_ACCESS_KEY_ID` (env, sensitive) - Spaces access key (for DO provider)
   - `SPACES_SECRET_ACCESS_KEY` (env, sensitive) - Spaces secret key (for DO provider)

4. Edit **onepassword-credentials**:
   - `OP_SERVICE_ACCOUNT_TOKEN` (env, sensitive) - 1Password service account token
   - `onepassword_vault` (terraform) - 1Password vault ID for storing secrets

### 4. Add More Workspaces

To add cluster workspaces, edit `terraform.tfvars`:

```hcl
workspaces = {
  "global" = {
    working_directory = "terraform/global"
    description       = "Cross-cluster resources (Tailscale)"
  }
  "do-nyc3-prod" = {
    working_directory = "terraform/clusters/do-nyc3-prod"
    description       = "DigitalOcean NYC3 production cluster"
  }
  "htz-fsn1-prod" = {
    working_directory = "terraform/clusters/htz-fsn1-prod"
    description       = "Hetzner FSN1 production cluster"
  }
}
```

Then run `terraform apply`.

## State Management

This bootstrap config uses local state by default. Options:

1. **Keep local** - Simple, state file stays in this directory
2. **Migrate to TFC** - Add `cloud {}` block and run `terraform init` to migrate

## Resources Created

### Project

- `infrastructure` - TFC project containing all workspaces

### Workspaces

| Workspace | Purpose |
|-----------|---------|
| `global` | Cross-cluster resources (Tailscale ACLs, auth keys) |
| `do-nyc3-prod` | DigitalOcean NYC3 production cluster |

### Variable Sets

| Variable Set | Variables | Attached To |
|--------------|-----------|-------------|
| `tailscale-credentials` | `TAILSCALE_API_KEY`, `TAILSCALE_TAILNET` | `global` |
| `digitalocean-credentials` | `DIGITALOCEAN_TOKEN`, `SPACES_ACCESS_KEY_ID`, `SPACES_SECRET_ACCESS_KEY` | DO cluster workspaces |
| `onepassword-credentials` | `OP_SERVICE_ACCOUNT_TOKEN`, `onepassword_vault` | Cluster workspaces needing 1Password |

### Workspace Settings

- Global workspace shares remote state with cluster workspaces
- Cluster workspaces can read Tailscale auth keys from global state

## Variable Types

| Category | Usage |
|----------|-------|
| `env` | Environment variables for provider authentication |
| `terraform` | Terraform variables passed to root modules |

Most credentials use `env` category since providers read from environment variables.
The exception is `onepassword_vault` which is a terraform variable passed to the cluster module.

## 1Password Setup

The 1Password integration uses a service account token (no CLI or Connect server required).

1. Create a service account in 1Password: https://my.1password.com/developer-tools/infrastructure-secrets/serviceaccount
2. Grant access to the vault where secrets will be stored
3. Copy the token and set it in the `onepassword-credentials` variable set

The 1Password Terraform provider v3.0+ uses the native SDK, so it works in TFC without any CLI installation.
