# Tailscale ACL configuration
resource "tailscale_acl" "this" {
  acl = jsonencode({
    tagOwners = merge(
      # Global k8s operator tags (shared across all clusters)
      # Each per-cluster operator tag also owns tag:k8s for default ingress behavior
      {
        "tag:k8s-operator" = []
        "tag:k8s"          = concat(["tag:k8s-operator"], [for name, _ in var.clusters : "tag:k8s-operator-${name}"])
      },
      # Legacy cluster tags (nbg1-prod1)
      {
        "tag:k8s-operator-nbg1-prod1" = []
        "tag:k8s-nbg1-prod1"          = ["tag:k8s-operator-nbg1-prod1"]
      },
      # Per-cluster operator tags: tag:k8s-operator-{cluster} owns tag:k8s-{cluster}
      merge(
        { for name, _ in var.clusters : "tag:k8s-operator-${name}" => [] },
        { for name, _ in var.clusters : "tag:k8s-${name}" => ["tag:k8s-operator-${name}"] }
      )
    )

    acls = [
      # Allow all connections (existing policy)
      { action = "accept", src = ["*"], dst = ["*:*"] }
    ]

    ssh = [
      {
        action = "check"
        src    = ["autogroup:member"]
        dst    = ["autogroup:self"]
        users  = ["autogroup:nonroot", "root"]
      }
    ]

    nodeAttrs = [
      {
        target = ["autogroup:member"]
        attr   = ["funnel"]
      },
      {
        target = ["tag:k8s"]
        attr   = ["funnel"]
      }
    ]
  })
}

# Generate auth keys for each cluster (legacy - kept for compatibility)
resource "tailscale_tailnet_key" "cluster" {
  for_each   = var.clusters
  depends_on = [tailscale_acl.this]

  reusable      = true
  preauthorized = true
  tags          = ["tag:k8s-operator-${each.key}"]
  description   = "k8s-operator ${each.key}"
}

# OAuth clients for Tailscale Kubernetes operator
# These are the preferred auth method for the operator
resource "tailscale_oauth_client" "k8s_operator" {
  for_each   = var.clusters
  depends_on = [tailscale_acl.this]

  tags        = ["tag:k8s-operator-${each.key}"]
  description = "Kubernetes operator for ${each.key}"

  # Scopes needed for k8s operator
  # See: https://tailscale.com/kb/1236/kubernetes-operator#prerequisites
  scopes = ["devices", "auth_keys", "routes", "dns"]
}
