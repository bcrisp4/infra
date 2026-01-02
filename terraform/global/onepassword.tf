# Store Tailscale OAuth credentials in 1Password
#
# These credentials are synced to Kubernetes via external-secrets operator
# Provider v3+ uses pure SDK, no CLI required (works in TFC)

resource "onepassword_item" "tailscale_operator" {
  for_each = var.clusters

  vault    = var.onepassword_vault
  title    = "${each.key}-tailscale-operator"
  category = "login"

  # OAuth client exports: id (client ID), key (client secret)
  username = tailscale_oauth_client.k8s_operator[each.key].id
  password = tailscale_oauth_client.k8s_operator[each.key].key

  tags = ["kubernetes", "tailscale", each.key]
}
