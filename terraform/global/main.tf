terraform {
  required_version = ">= 1.14"

  required_providers {
    tailscale = {
      source  = "tailscale/tailscale"
      version = "~> 0.24"
    }
    onepassword = {
      source  = "1Password/onepassword"
      version = "~> 3.0"  # v3 uses pure SDK, no CLI required
    }
  }
}

provider "tailscale" {
  # Uses TAILSCALE_API_KEY and TAILSCALE_TAILNET environment variables
  # Set these in Terraform Cloud workspace variables
}

provider "onepassword" {
  # Uses OP_SERVICE_ACCOUNT_TOKEN environment variable
  # from TFC variable set "onepassword-credentials"
}
