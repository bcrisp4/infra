locals {
  bsync_cloudflare_account_id = "80e7492f41a66e136f50564f095fa638"
}

data "cloudflare_zero_trust_organization" "bc4" {
  account_id = local.bsync_cloudflare_account_id
}

resource "cloudflare_zero_trust_access_identity_provider" "cloudflare" {
  account_id = local.bsync_cloudflare_account_id
  name       = "Cloudflare"
  type       = "cloudflare"
  config = {
    restrict_to_account_members = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "bsync_staging" {
  account_id       = local.bsync_cloudflare_account_id
  name             = "Allow Ben - bsync bc4 staging"
  decision         = "allow"
  session_duration = "24h"
  include = [{
    email = { email = "ben@thecrisp.io" }
  }]
}

resource "cloudflare_zero_trust_access_application" "bsync_staging" {
  account_id                = local.bsync_cloudflare_account_id
  name                      = "bsync staging account"
  type                      = "self_hosted"
  domain                    = "bsync-staging.bc4.uk"
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.cloudflare.id]
  auto_redirect_to_identity = true
  session_duration          = "24h"
  destinations = [{
    type = "public"
    uri  = "bsync-staging.bc4.uk"
  }]
  policies = [{
    id         = cloudflare_zero_trust_access_policy.bsync_staging.id
    precedence = 1
  }]
  oauth_configuration = {
    enabled = true
    dynamic_client_registration = {
      enabled                = true
      allow_any_on_localhost = false
      allow_any_on_loopback  = true
      allowed_uris           = ["io.thecrisp.bsyncprobe:/oauth/callback"]
    }
    grant = {
      access_token_lifetime = "15m"
      session_duration      = "24h"
    }
  }
}

resource "cloudflare_d1_database" "bsync_staging" {
  account_id            = local.bsync_cloudflare_account_id
  name                  = "bsync-staging"
  primary_location_hint = "weur"
  read_replication = {
    mode = "disabled"
  }
}

resource "cloudflare_workers_custom_domain" "bsync_staging" {
  account_id = local.bsync_cloudflare_account_id
  zone_id    = local.cloudflare_zones.bc4_uk
  hostname   = "bsync-staging.bc4.uk"
  service    = "bsync-staging"
}
