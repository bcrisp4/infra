---
name: terraform
description: Apply Terraform changes safely in this infrastructure monorepo. Use when user asks to apply terraform, run terraform plan/apply, make infrastructure changes, update cloud resources, modify node pools, change cluster configuration, or update provider versions. Handles TFC remote execution.
---

# Terraform Apply Skill

Apply Terraform changes safely in this infrastructure monorepo. All Terraform runs (except bootstrap) execute remotely via Terraform Cloud (TFC).

## Directory Structure

```
terraform/
  bootstrap/              # TFC workspaces and variable sets (LOCAL state)
  global/                 # Cross-cluster resources (Tailscale, 1Password)
  clusters/
    do-nyc3-prod/         # DigitalOcean NYC3 production cluster
    _template/            # Template for new clusters
  modules/
    k8s-cluster/{provider}/  # Reusable provider-specific modules
```

## Workflow

### 1. Navigate to the correct module

```bash
cd /Users/ben/Code/infra/terraform/clusters/do-nyc3-prod
```

### 2. Initialize (if needed)

```bash
terraform init
```

### 3. Plan changes

```bash
terraform plan -out=plan.tfplan
```

Use `.tfplan` extension - it's gitignored.

Review the plan output carefully:
- `+` = create new resource
- `~` = modify existing resource
- `-` = destroy resource
- `-/+` = destroy and recreate (potentially disruptive!)

### 4. Apply the plan

```bash
terraform apply plan.tfplan
```

TFC executes the apply remotely. Output streams to the terminal.

## CRITICAL: Security Rules

**NEVER commit these files:**
- `*.tfstate` / `*.tfstate.backup` - Contains sensitive data
- `*.tfvars` - May contain secrets (use `.tfvars.example` instead)
- `*.tfplan` / `tfplan` - Binary plan files may contain sensitive values
- `.terraform/` - Provider plugins and local state
- API keys, tokens, passwords, or any credentials

**Before EVERY commit, verify:**

```bash
# Check for state/var/plan files
git diff --cached --name-only | grep -E '\.(tfstate|tfvars|tfplan)$'
git diff --cached --name-only | grep -E '^.*tfplan$'

# Grep for secrets in staged changes
git diff --cached -S"SECRET" -S"TOKEN" -S"PASSWORD" -S"API_KEY"
```

If either returns matches, unstage immediately. If secrets were committed, repository history must be rewritten.

## TFC Configuration

Organization: `bc4`

| Module | Workspace | Variable Sets |
|--------|-----------|---------------|
| bootstrap | (local state) | - |
| global | bc4/global | tailscale-credentials, onepassword-credentials |
| do-nyc3-prod | bc4/do-nyc3-prod | digitalocean-credentials, onepassword-credentials |

Variable sets are managed in `terraform/bootstrap/main.tf`. To attach a new variable set:

```hcl
resource "tfe_workspace_variable_set" "cluster_onepassword" {
  variable_set_id = tfe_variable_set.onepassword.id
  workspace_id    = tfe_workspace.this["do-nyc3-prod"].id
}
```

## Updating Provider Versions

Query the Terraform Registry API for latest versions:

```bash
# DigitalOcean
curl -s https://registry.terraform.io/v1/providers/digitalocean/digitalocean | jq '.version'

# 1Password
curl -s https://registry.terraform.io/v1/providers/1Password/onepassword | jq '.version'

# Tailscale
curl -s https://registry.terraform.io/v1/providers/tailscale/tailscale | jq '.version'

# TFE (Terraform Cloud)
curl -s https://registry.terraform.io/v1/providers/hashicorp/tfe | jq '.version'

# Terraform itself
curl -s https://releases.hashicorp.com/terraform/index.json | jq -r '.versions | keys | .[]' | sort -V | tail -5
```

Files to update when changing versions:
- `.terraform-version` - tfenv version (should match required_version)
- `terraform/bootstrap/main.tf` - tfe provider
- `terraform/global/main.tf` - tailscale provider
- `terraform/clusters/do-nyc3-prod/main.tf` - digitalocean, onepassword providers
- `terraform/clusters/_template/main.tf` - required_version only

Use pessimistic constraints (`~> X.Y`) pinned to minor version for stability while allowing patches.

## Common Operations

### Resize node pool

Edit `terraform/clusters/{cluster}/cluster.tf`:

```hcl
resource "digitalocean_kubernetes_node_pool" "workers_8vcpu_16gb" {
  name       = "workers-8vcpu-16gb"
  size       = "s-8vcpu-16gb"
  auto_scale = true
  min_nodes  = 3
  max_nodes  = 5
}
```

### Add new Spaces bucket

Edit `terraform/clusters/{cluster}/spaces.tf` and add to the `observability` map.

### Create new cluster

```bash
./scripts/new-cluster.sh <cluster-name>
```

This creates both `terraform/clusters/{cluster}/` and `kubernetes/clusters/{cluster}/`.

## Troubleshooting

### "No configuration files" error

You're in the wrong directory. Always use absolute paths:

```bash
cd /Users/ben/Code/infra/terraform/clusters/do-nyc3-prod && terraform plan
```

### State lock errors

TFC manages state locking. If a run is stuck:
1. Check TFC UI: https://app.terraform.io/app/bc4/{workspace}/runs
2. Cancel any pending runs
3. Retry

### Provider version mismatch

```bash
terraform init -upgrade
```

### "region has insufficient capacity"

DigitalOcean may not have certain instance types available in a region. Check available sizes:

```bash
doctl compute size list --output json | jq -r '.[] | select(.regions[] == "nyc3") | .slug'
```
