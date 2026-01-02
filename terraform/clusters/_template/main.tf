# Cluster: {{cluster_name}}
#
# Copy this template to create a new cluster:
#   cp -r _template ../{{cluster_name}}
#   cd ../{{cluster_name}}
#   # Update backend.tf with workspace name
#   # Update terraform.tfvars with cluster configuration
#   # Uncomment and configure the module below

terraform {
  required_version = ">= 1.14"

  # Add provider requirements for your cluster module here
  # required_providers {
  #   hcloud = {
  #     source  = "hetznercloud/hcloud"
  #     version = "~> 1.45"
  #   }
  # }
}

# Fetch Tailscale auth key from global state
data "terraform_remote_state" "global" {
  backend = "remote"
  config = {
    organization = "bc4"
    workspaces = {
      name = "global"
    }
  }
}

locals {
  tailscale_auth_key = data.terraform_remote_state.global.outputs.tailscale_auth_keys[var.cluster_name]
}

# Uncomment and configure for your provider
# module "cluster" {
#   source = "../../modules/k8s-cluster/<provider>"
#
#   cluster_name       = var.cluster_name
#   tailscale_auth_key = local.tailscale_auth_key
#
#   # Add provider-specific configuration here
# }
