# DigitalOcean Spaces buckets for observability stack
#
# These S3-compatible buckets store long-term data for:
# - Loki (logs)
# - Mimir (metrics)
# - Tempo (traces)
# - Pyroscope (profiles)

locals {
  spaces_region = "nyc3"

  # Bucket names must be globally unique across all DO customers
  # Using bc4 + cluster name as prefix for uniqueness
  bucket_prefix = "bc4-${var.cluster_name}"

  observability_buckets = {
    loki = {
      name        = "${local.bucket_prefix}-loki"
      description = "Loki log storage"
    }
    mimir = {
      name        = "${local.bucket_prefix}-mimir"
      description = "Mimir metrics storage"
    }
    tempo = {
      name        = "${local.bucket_prefix}-tempo"
      description = "Tempo trace storage"
    }
    pyroscope = {
      name        = "${local.bucket_prefix}-pyroscope"
      description = "Pyroscope profile storage"
    }
  }
}

# Create Spaces buckets
resource "digitalocean_spaces_bucket" "observability" {
  for_each = local.observability_buckets

  name   = each.value.name
  region = local.spaces_region
  acl    = "private"

  # Enable versioning for data protection
  versioning {
    enabled = true
  }

  # Lifecycle rules for cost optimization
  lifecycle_rule {
    id      = "expire-old-versions"
    enabled = true

    noncurrent_version_expiration {
      days = 30
    }
  }
}

# Create per-bucket Spaces access keys
# Note: bucket-scoped keys are incompatible with bucket policies
# so we use scoped keys instead for fine-grained access control
resource "digitalocean_spaces_key" "observability" {
  for_each = digitalocean_spaces_bucket.observability

  name = "${var.cluster_name}-${each.key}"

  grant {
    bucket     = each.value.name
    permission = "readwrite"
  }
}

# Outputs for use in Kubernetes secrets
output "spaces_buckets" {
  description = "Spaces bucket information for observability stack"
  value = {
    for k, v in digitalocean_spaces_bucket.observability : k => {
      name     = v.name
      region   = v.region
      endpoint = "https://${local.spaces_region}.digitaloceanspaces.com"
    }
  }
}

output "spaces_endpoint" {
  description = "Spaces S3-compatible endpoint"
  value       = "https://${local.spaces_region}.digitaloceanspaces.com"
}

output "spaces_region" {
  description = "Spaces region"
  value       = local.spaces_region
}
