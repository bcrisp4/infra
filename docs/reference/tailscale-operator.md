# Tailscale Kubernetes Operator

Reference documentation for the Tailscale Kubernetes Operator configuration.

## Overview

The Tailscale operator enables exposing Kubernetes services via Tailscale, creating Ingress resources that are accessible within your tailnet.

## OAuth Client Configuration

### Required Scopes

The OAuth client needs these scopes:
- `devices` - Create and manage devices
- `auth_keys` - Create auth keys for node registration
- `routes` - Advertise routes
- `dns` - Manage DNS settings

### Tag Ownership

OAuth client tags must own `tag:k8s` for ingresses to work (operator uses `tag:k8s` by default).

ACL example:
```json
{
  "tagOwners": {
    "tag:k8s": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"]
  }
}
```

### Common Error

If ingresses fail with "requested tags invalid or not permitted", check ACL tag ownership.

## MagicDNS Naming

MagicDNS uses **flat naming only** - no nested subdomains are supported.

| Pattern | Valid |
|---------|-------|
| `argocd-do-nyc3-prod.marlin-tet.ts.net` | Yes |
| `argocd.do-nyc3-prod.marlin-tet.ts.net` | No (dots create DNS hierarchy) |

**Naming convention:** `{hostname}.{tailnet}.ts.net`

Use dashes to create logical groupings: `{app}-{cluster}.{tailnet}.ts.net`

### Custom Subdomains

For custom subdomain structures, alternatives require additional infrastructure:
- Own domain + split DNS (e.g., `argocd.do-nyc3-prod.internal.example.com`)
- Gateway API + ExternalDNS + cert-manager

## Tailscale Funnel

Funnel allows exposing specific paths publicly through Tailscale's infrastructure.

To enable Funnel:

1. Add `funnel` attribute to the tag in ACLs:
   ```json
   {
     "nodeAttrs": [
       {
         "target": ["tag:k8s"],
         "attr": ["funnel"]
       }
     ]
   }
   ```

2. Create Ingress with `tailscale.com/funnel: "true"` annotation

See [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md) for a complete example.

## Related

- [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md)
- [terraform/global/tailscale.tf](/terraform/global/tailscale.tf)
