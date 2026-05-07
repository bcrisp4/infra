# Tailscale ACL configuration
resource "tailscale_acl" "this" {
  acl = jsonencode({
    groups = {
      "group:admins" = ["ben@thecrisp.io"]
    }

    tagOwners = merge(
      # Global k8s operator tags (shared across all clusters)
      # Each per-cluster operator tag also owns tag:k8s for default ingress behavior
      {
        "tag:k8s-operator" = []
        "tag:k8s"          = concat(["tag:k8s-operator"], [for name, _ in var.clusters : "tag:k8s-operator-${name}"])
        # ProxyGroup HA ingress tags
        "tag:k8s-ingress"  = concat(["tag:k8s-operator"], [for name, _ in var.clusters : "tag:k8s-operator-${name}"])
        "tag:k8s-services" = concat(["tag:k8s-operator"], [for name, _ in var.clusters : "tag:k8s-operator-${name}"])
        # Dedicated tag for Funnel-eligible standalone proxies
        "tag:k8s-funnel" = concat(["tag:k8s-operator"], [for name, _ in var.clusters : "tag:k8s-operator-${name}"])
      },
      # Per-cluster operator tags: tag:k8s-operator-{cluster} owns tag:k8s-{cluster}
      merge(
        { for name, _ in var.clusters : "tag:k8s-operator-${name}" => [] },
        { for name, _ in var.clusters : "tag:k8s-${name}" => ["tag:k8s-operator-${name}"] }
      )
    )

    acls = []

    grants = [
      # Web UIs over tailnet (ProxyGroup HA ingress)
      {
        src = ["group:admins"]
        dst = ["tag:k8s-services", "tag:k8s-ingress"]
        ip  = ["tcp:443"]
      },
      # Funnel proxy device (admin debugging via tailnet hostname)
      {
        src = ["group:admins"]
        dst = ["tag:k8s-funnel"]
        ip  = ["tcp:443"]
      },
      # Personal user-owned devices (laptops, phones, etc.)
      {
        src = ["group:admins"]
        dst = ["autogroup:self"]
        ip  = ["*"]
      },
      # Exit node egress (use any approved exit node on tailnet)
      {
        src = ["group:admins"]
        dst = ["autogroup:internet"]
        ip  = ["*"]
      },
      # Home LAN subnet route
      {
        src = ["group:admins"]
        dst = ["192.168.1.0/24"]
        ip  = ["*"]
      }
    ]

    ssh = [
      {
        action = "check"
        src    = ["group:admins"]
        dst    = ["autogroup:self"]
        users  = ["autogroup:nonroot", "root"]
      }
    ]

    # Auto-approve Tailscale Services for ProxyGroup HA ingress
    # Auto-approve exit node routes and home LAN subnet from owner's devices
    autoApprovers = {
      services = {
        "tag:k8s-services" = ["tag:k8s-ingress"]
      }
      exitNode = ["group:admins"]
      routes = {
        "192.168.1.0/24" = ["group:admins"]
      }
    }

    nodeAttrs = [
      {
        target = ["group:admins"]
        attr   = ["funnel"]
      },
      {
        target = ["tag:k8s-funnel"]
        attr   = ["funnel"]
      }
    ]
  })
}

# OAuth clients for Tailscale Kubernetes operator
resource "tailscale_oauth_client" "k8s_operator" {
  for_each   = var.clusters
  depends_on = [tailscale_acl.this]

  tags        = ["tag:k8s-operator-${each.key}"]
  description = "Kubernetes operator for ${each.key}"

  # Scopes needed for k8s operator with ProxyGroup support
  # See: https://tailscale.com/kb/1236/kubernetes-operator#prerequisites
  # Services scope required for ProxyGroup HA ingress
  scopes = ["devices", "auth_keys", "routes", "dns", "services"]
}
