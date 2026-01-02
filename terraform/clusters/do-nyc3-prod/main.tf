# Cluster: do-nyc3-prod
#
# DigitalOcean NYC3 production cluster

terraform {
  required_version = ">= 1.14"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.72"
    }
    onepassword = {
      source  = "1Password/onepassword"
      version = "~> 3.0"
    }
  }
}

provider "digitalocean" {
  # Uses DIGITALOCEAN_TOKEN and SPACES_ACCESS_KEY_ID/SPACES_SECRET_ACCESS_KEY
  # Set these in Terraform Cloud workspace variables
}

provider "onepassword" {
  # Uses OP_SERVICE_ACCOUNT_TOKEN environment variable for SDK mode
  # (avoids requiring op CLI on TFC workers)
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
