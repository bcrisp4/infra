# Bootstrap Terraform Cloud
#
# This configuration creates TFC workspaces and configuration.
# Run with local state first, then optionally migrate to TFC.

terraform {
  required_version = ">= 1.14"

  required_providers {
    tfe = {
      source  = "hashicorp/tfe"
      version = "~> 0.72"
    }
  }

  # Start with local state
  # After bootstrap, can migrate to TFC if desired
}

provider "tfe" {
  # Uses TFE_TOKEN environment variable
}

# Variables
variable "organization" {
  description = "Terraform Cloud organization name"
  type        = string
  default     = "bc4"
}

variable "github_repo" {
  description = "GitHub repository for VCS connection (owner/repo format)"
  type        = string
  default     = "bcrisp4/infra"
}

variable "workspaces" {
  description = "Map of workspace names to their configuration"
  type = map(object({
    working_directory = string
    description       = optional(string, "")
    auto_apply        = optional(bool, false)
    execution_mode    = optional(string, "remote")
  }))
  default = {
    "global" = {
      working_directory = "terraform/global"
      description       = "Cross-cluster resources (Tailscale)"
      auto_apply        = false
    }
    "do-nyc3-prod" = {
      working_directory = "terraform/clusters/do-nyc3-prod"
      description       = "DigitalOcean NYC3 production cluster"
      auto_apply        = false
    }
  }
}

# Data source for organization
data "tfe_organization" "this" {
  name = var.organization
}

# Create project for infrastructure
resource "tfe_project" "infra" {
  organization = data.tfe_organization.this.name
  name         = "infrastructure"
  description  = "Kubernetes cluster infrastructure"
}

# Create workspaces
resource "tfe_workspace" "this" {
  for_each = var.workspaces

  organization      = data.tfe_organization.this.name
  project_id        = tfe_project.infra.id
  name              = each.key
  description       = each.value.description
  working_directory = each.value.working_directory
  auto_apply        = each.value.auto_apply

  # Queue all runs (no VCS trigger - manual or API trigger)
  queue_all_runs = false
}

# Workspace settings (execution mode and remote state sharing)
resource "tfe_workspace_settings" "this" {
  for_each = var.workspaces

  workspace_id   = tfe_workspace.this[each.key].id
  execution_mode = each.value.execution_mode

  # Global workspace shares state with cluster workspaces
  global_remote_state       = each.key == "global" ? false : null
  remote_state_consumer_ids = each.key == "global" ? [
    for name, ws in tfe_workspace.this : ws.id if name != "global"
  ] : null
}

# Variable set for Tailscale credentials (shared across workspaces)
resource "tfe_variable_set" "tailscale" {
  organization = data.tfe_organization.this.name
  name         = "tailscale-credentials"
  description  = "Tailscale API credentials for cluster provisioning"
}

# Tailscale API key variable (placeholder - set manually in TFC UI)
resource "tfe_variable" "tailscale_api_key" {
  key             = "TAILSCALE_API_KEY"
  value           = ""
  category        = "env"
  sensitive       = true
  variable_set_id = tfe_variable_set.tailscale.id
  description     = "Tailscale API key"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "tfe_variable" "tailscale_tailnet" {
  key             = "TAILSCALE_TAILNET"
  value           = "marlin-tet.ts.net"
  category        = "env"
  sensitive       = false
  variable_set_id = tfe_variable_set.tailscale.id
  description     = "Tailscale tailnet name"
}

# Attach Tailscale variable set to global workspace
resource "tfe_workspace_variable_set" "global_tailscale" {
  variable_set_id = tfe_variable_set.tailscale.id
  workspace_id    = tfe_workspace.this["global"].id
}

# Clusters configuration for global workspace
resource "tfe_variable" "global_clusters" {
  key          = "clusters"
  value        = jsonencode({
    for name, config in var.workspaces : name => {
      tags = [name]
    } if name != "global"
  })
  category     = "terraform"
  hcl          = true
  workspace_id = tfe_workspace.this["global"].id
  description  = "Clusters to create Tailscale auth keys for"
}

# Variable set for DigitalOcean credentials
resource "tfe_variable_set" "digitalocean" {
  organization = data.tfe_organization.this.name
  name         = "digitalocean-credentials"
  description  = "DigitalOcean API and Spaces credentials"
}

resource "tfe_variable" "do_token" {
  key             = "DIGITALOCEAN_TOKEN"
  value           = ""
  category        = "env"
  sensitive       = true
  variable_set_id = tfe_variable_set.digitalocean.id
  description     = "DigitalOcean API token"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "tfe_variable" "spaces_access_key" {
  key             = "SPACES_ACCESS_KEY_ID"
  value           = ""
  category        = "env"
  sensitive       = true
  variable_set_id = tfe_variable_set.digitalocean.id
  description     = "DigitalOcean Spaces access key ID"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "tfe_variable" "spaces_secret_key" {
  key             = "SPACES_SECRET_ACCESS_KEY"
  value           = ""
  category        = "env"
  sensitive       = true
  variable_set_id = tfe_variable_set.digitalocean.id
  description     = "DigitalOcean Spaces secret access key"

  lifecycle {
    ignore_changes = [value]
  }
}

# Attach DigitalOcean variable set to do-nyc3-prod workspace
resource "tfe_workspace_variable_set" "do_nyc3_prod_digitalocean" {
  count           = contains(keys(var.workspaces), "do-nyc3-prod") ? 1 : 0
  variable_set_id = tfe_variable_set.digitalocean.id
  workspace_id    = tfe_workspace.this["do-nyc3-prod"].id
}


# Variable set for 1Password credentials
resource "tfe_variable_set" "onepassword" {
  organization = data.tfe_organization.this.name
  name         = "onepassword-credentials"
  description  = "1Password service account credentials"
}

resource "tfe_variable" "onepassword_token" {
  key             = "OP_SERVICE_ACCOUNT_TOKEN"
  value           = ""
  category        = "env"
  sensitive       = true
  variable_set_id = tfe_variable_set.onepassword.id
  description     = "1Password service account token (env var for SDK mode)"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "tfe_variable" "onepassword_vault" {
  key             = "onepassword_vault"
  value           = ""
  category        = "terraform"
  sensitive       = false
  variable_set_id = tfe_variable_set.onepassword.id
  description     = "1Password vault ID for storing secrets"

  lifecycle {
    ignore_changes = [value]
  }
}

# Attach 1Password variable set to global workspace
resource "tfe_workspace_variable_set" "global_onepassword" {
  variable_set_id = tfe_variable_set.onepassword.id
  workspace_id    = tfe_workspace.this["global"].id
}

# Attach 1Password variable set to do-nyc3-prod workspace
resource "tfe_workspace_variable_set" "do_nyc3_prod_onepassword" {
  count           = contains(keys(var.workspaces), "do-nyc3-prod") ? 1 : 0
  variable_set_id = tfe_variable_set.onepassword.id
  workspace_id    = tfe_workspace.this["do-nyc3-prod"].id
}

# Outputs
output "organization" {
  value = data.tfe_organization.this.name
}

output "project_id" {
  value = tfe_project.infra.id
}

output "workspace_ids" {
  value = { for k, v in tfe_workspace.this : k => v.id }
}

output "variable_set_id" {
  value = tfe_variable_set.tailscale.id
}

output "next_steps" {
  value = <<-EOT

    Terraform Cloud bootstrap complete!

    Next steps:
    1. Set Tailscale credentials in TFC:
       - Go to: https://app.terraform.io/app/${data.tfe_organization.this.name}/settings/varsets
       - Edit "tailscale-credentials" variable set
       - Set TAILSCALE_API_KEY (sensitive)
       - Set TAILSCALE_TAILNET (your tailnet name)

    2. Initialize global workspace:
       cd ../global
       terraform init
       terraform plan

    3. To add a new cluster workspace, update terraform.tfvars:
       workspaces = {
         "global" = { ... }
         "htz-fsn1-prod" = {
           working_directory = "terraform/clusters/htz-fsn1-prod"
           description       = "Hetzner FSN1 production cluster"
         }
       }
  EOT
}
