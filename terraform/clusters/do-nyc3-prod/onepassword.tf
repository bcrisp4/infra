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
      value = "${local.spaces_region}.digitaloceanspaces.com"
    }

    field {
      label = "scheme"
      type  = "STRING"
      value = "https"
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

# 1Password items for backup bucket S3 credentials
resource "onepassword_item" "backup_credentials" {
  for_each = local.backup_buckets

  vault    = var.onepassword_vault
  title    = "${var.cluster_name}-${each.key}-s3"
  category = "login"

  username = digitalocean_spaces_key.backups[each.key].access_key
  password = digitalocean_spaces_key.backups[each.key].secret_key

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
      value = "${local.spaces_region}.digitaloceanspaces.com"
    }

    field {
      label = "scheme"
      type  = "STRING"
      value = "https"
    }

    field {
      label = "region"
      type  = "STRING"
      value = local.spaces_region
    }
  }

  tags = ["kubernetes", "s3", var.cluster_name, each.key, "backup"]

  lifecycle {
    ignore_changes = [password]
  }
}

# Store kubeconfig in 1Password for secure access
resource "onepassword_item" "kubeconfig" {
  vault    = var.onepassword_vault
  title    = "${var.cluster_name}-kubeconfig"
  category = "secure_note"

  section {
    label = "Cluster Info"

    field {
      label = "cluster_name"
      type  = "STRING"
      value = digitalocean_kubernetes_cluster.main.name
    }

    field {
      label = "endpoint"
      type  = "STRING"
      value = digitalocean_kubernetes_cluster.main.endpoint
    }

    field {
      label = "region"
      type  = "STRING"
      value = "nyc3"
    }
  }

  section {
    label = "Kubeconfig"

    field {
      label = "kubeconfig"
      type  = "STRING"
      value = digitalocean_kubernetes_cluster.main.kube_config[0].raw_config
    }
  }

  tags = ["kubernetes", "kubeconfig", var.cluster_name]
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

output "onepassword_kubeconfig" {
  description = "1Password item reference for kubeconfig"
  value = {
    vault = var.onepassword_vault
    item  = onepassword_item.kubeconfig.title
    uuid  = onepassword_item.kubeconfig.uuid
  }
}

output "onepassword_backup_items" {
  description = "1Password item references for backup bucket credentials"
  value = {
    for k, v in onepassword_item.backup_credentials : k => {
      vault = var.onepassword_vault
      item  = v.title
      uuid  = v.uuid
    }
  }
}

# =============================================================================
# MLflow Secrets
# =============================================================================

# MLflow artifact storage S3 credentials
resource "onepassword_item" "mlflow_artifacts_s3" {
  vault    = var.onepassword_vault
  title    = "${var.cluster_name}-mlflow-artifacts-s3"
  category = "login"

  username = digitalocean_spaces_key.mlflow_artifacts.access_key
  password = digitalocean_spaces_key.mlflow_artifacts.secret_key

  section {
    label = "S3 Configuration"

    field {
      label = "bucket"
      type  = "STRING"
      value = digitalocean_spaces_bucket.mlflow_artifacts.name
    }

    field {
      label = "endpoint"
      type  = "STRING"
      value = "${local.spaces_region}.digitaloceanspaces.com"
    }

    field {
      label = "region"
      type  = "STRING"
      value = local.spaces_region
    }
  }

  tags = ["kubernetes", "s3", var.cluster_name, "mlflow"]

  lifecycle {
    ignore_changes = [password]
  }
}

# MLflow PostgreSQL backup S3 credentials
resource "onepassword_item" "mlflow_postgres_s3" {
  vault    = var.onepassword_vault
  title    = "${var.cluster_name}-mlflow-postgres-s3"
  category = "login"

  username = digitalocean_spaces_key.mlflow_postgres_backups.access_key
  password = digitalocean_spaces_key.mlflow_postgres_backups.secret_key

  section {
    label = "S3 Configuration"

    field {
      label = "bucket"
      type  = "STRING"
      value = digitalocean_spaces_bucket.mlflow_postgres_backups.name
    }

    field {
      label = "endpoint"
      type  = "STRING"
      value = "${local.spaces_region}.digitaloceanspaces.com"
    }
  }

  tags = ["kubernetes", "s3", var.cluster_name, "mlflow", "backup"]

  lifecycle {
    ignore_changes = [password]
  }
}
