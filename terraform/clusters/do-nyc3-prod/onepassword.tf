# 1Password items for observability stack S3 credentials
#
# Each item contains everything needed to connect to a Spaces bucket:
# - Bucket name
# - Endpoint URL
# - Region
# - Access key ID (per-bucket from digitalocean_spaces_key)
# - Secret access key (per-bucket from digitalocean_spaces_key)
#
# Use external-secrets operator to sync these to Kubernetes secrets.

resource "onepassword_item" "spaces_credentials" {
  for_each = local.observability_buckets

  vault    = var.onepassword_vault
  title    = "${var.cluster_name}-${each.key}-s3"
  category = "login"

  # Per-bucket credentials from digitalocean_spaces_key
  username = digitalocean_spaces_key.observability[each.key].access_key
  password = digitalocean_spaces_key.observability[each.key].secret_key

  section {
    label = "S3 Configuration"

    field {
      label = "bucket"
      type  = "STRING"
      value = each.value.name
    }

    field {
      label = "endpoint"
      type  = "STRING"
      value = "https://${local.spaces_region}.digitaloceanspaces.com"
    }

    field {
      label = "region"
      type  = "STRING"
      value = local.spaces_region
    }
  }

  tags = ["kubernetes", "s3", var.cluster_name, each.key]

  # Workaround for provider v3.0.x bug with password field
  # https://github.com/1Password/terraform-provider-onepassword/issues/228
  lifecycle {
    ignore_changes = [password]
  }
}

# Output the 1Password item references for documentation
output "onepassword_items" {
  description = "1Password item references for external-secrets"
  value = {
    for k, v in onepassword_item.spaces_credentials : k => {
      vault = var.onepassword_vault
      item  = v.title
      uuid  = v.uuid
    }
  }
}
