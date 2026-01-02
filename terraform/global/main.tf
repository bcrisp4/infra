terraform {
  required_version = ">= 1.14"

  required_providers {
    tailscale = {
      source  = "tailscale/tailscale"
      version = "~> 0.24"
    }
  }
}

provider "tailscale" {
  # Uses TAILSCALE_API_KEY and TAILSCALE_TAILNET environment variables
  # Set these in Terraform Cloud workspace variables
}
