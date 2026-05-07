# Tailscale Kubernetes Operator

Reference documentation for the Tailscale Kubernetes Operator configuration.

## Overview

The Tailscale operator enables exposing Kubernetes services via Tailscale, creating Ingress resources that are accessible within your tailnet. With ProxyGroup, multiple ingresses share a pool of HA proxy replicas instead of each having dedicated proxies.

## OAuth Client Configuration

### Required Scopes

The OAuth client needs these scopes:

| Scope | Purpose |
|-------|---------|
| `devices` | Create and manage devices |
| `auth_keys` | Create auth keys for node registration |
| `routes` | Advertise routes |
| `dns` | Manage DNS settings |
| `services` | Create Tailscale Services (required for ProxyGroup) |

Configuration in `terraform/global/tailscale.tf`:
```hcl
resource "tailscale_oauth_client" "k8s_operator" {
  scopes = ["devices", "auth_keys", "routes", "dns", "services"]
  tags   = ["tag:k8s-operator-${cluster_name}"]
}
```

### Tag Ownership

OAuth client tags must own `tag:k8s` for ingresses to work (operator uses `tag:k8s` by default).

For ProxyGroup, additional tags are needed:
- `tag:k8s-ingress` - Applied to ProxyGroup proxies
- `tag:k8s-services` - Applied to Tailscale Services exposed via ProxyGroup

For Funnel, a dedicated tag scopes the `funnel` nodeAttr to standalone Funnel proxies only:
- `tag:k8s-funnel` - Applied via `tailscale.com/tags` annotation on the Funnel Ingress

ACL example:
```json
{
  "tagOwners": {
    "tag:k8s-operator": [],
    "tag:k8s": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"],
    "tag:k8s-ingress": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"],
    "tag:k8s-services": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"],
    "tag:k8s-funnel": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"]
  },
  "nodeAttrs": [
    { "target": ["tag:k8s-funnel"], "attr": ["funnel"] }
  ]
}
```

### Common Error

If ingresses fail with "requested tags invalid or not permitted", check ACL tag ownership.

## ProxyGroup HA Ingress

ProxyGroup consolidates per-ingress proxies into a shared, multi-replica proxy pool for better availability and resource efficiency.

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Tailscale Service          │
                    │    (miniflux.marlin-tet.ts.net)    │
                    └─────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            ┌──────────────┐                 ┌──────────────┐
            │ ProxyGroup   │                 │ ProxyGroup   │
            │  Replica 0   │                 │  Replica 1   │
            │ (Node A)     │                 │ (Node B)     │
            └──────────────┘                 └──────────────┘
                    │                                 │
                    └────────────────┬────────────────┘
                                     ▼
                           ┌──────────────────┐
                           │  K8s Service     │
                           │  (miniflux:8080) │
                           └──────────────────┘
```

**Key benefits:**
- Multiple ingresses share the same proxy replicas
- Proxies spread across nodes for HA (via topologySpreadConstraints)
- Tailscale Services provide stable endpoints during pod rescheduling
- Reduced resource overhead compared to per-ingress proxies

### Service Auto-Approval

ProxyGroup creates Tailscale Services which need auto-approval via ACLs:

```json
{
  "autoApprovers": {
    "services": {
      "tag:k8s-services": ["tag:k8s-ingress"]
    }
  }
}
```

This allows proxies tagged with `tag:k8s-ingress` to automatically approve services tagged with `tag:k8s-services`.

### ProxyClass Configuration

ProxyClass defines pod configuration for ProxyGroup replicas:

```yaml
# kubernetes/apps/tailscale-operator/templates/proxyclass-ha.yaml
apiVersion: tailscale.com/v1alpha1
kind: ProxyClass
metadata:
  name: ha-ingress
spec:
  statefulSet:
    pod:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: tailscale
```

**Available pod scheduling options:**
- `topologySpreadConstraints` - Spread replicas across nodes/zones
- `affinity` - Pod affinity/anti-affinity rules
- `nodeSelector` - Node selection constraints
- `tolerations` - Tolerations for taints

### ProxyGroup Configuration

```yaml
# kubernetes/apps/tailscale-operator/templates/proxygroup.yaml
apiVersion: tailscale.com/v1alpha1
kind: ProxyGroup
metadata:
  name: ingress-proxies
spec:
  type: ingress
  replicas: 2
  proxyClass: ha-ingress
  tags:
    - tag:k8s-ingress
```

Enable via cluster values:
```yaml
# kubernetes/clusters/{cluster}/apps/tailscale-operator/values.yaml
proxyGroup:
  enabled: true
  name: ingress-proxies
  replicas: 2
```

### Ingress Format for ProxyGroup

**Important:** ProxyGroup ingresses use a different format than standard Kubernetes Ingress.

**Standard Ingress (NOT for ProxyGroup):**
```yaml
spec:
  rules:
    - host: myapp
      http:
        paths:
          - path: /
            backend: ...
```

**ProxyGroup Ingress (required format):**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  annotations:
    tailscale.com/proxy-group: ingress-proxies
    tailscale.com/tags: tag:k8s-services
spec:
  ingressClassName: tailscale
  defaultBackend:
    service:
      name: myapp
      port:
        number: 8080
  tls:
    - hosts:
        - myapp
```

**Key differences:**
- Uses `defaultBackend` instead of `rules` with `host`
- Hostname is only in `tls.hosts`, not in rules
- No `tls.secretName` - Tailscale provides certs automatically
- Requires `tailscale.com/proxy-group` annotation

See [Migrate Ingress to ProxyGroup](../how-to/tailscale-proxygroup-ingress.md) for migration guide.

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

**Important:** Funnel ingresses use **standalone proxies**, not ProxyGroup. This is because:
1. Funnel requires path-based routing (`rules` with `paths`), which ProxyGroup doesn't support
2. Funnel ingresses should be isolated from other services for security
3. The public-facing nature of Funnel benefits from dedicated proxy resources

**Current Funnel ingresses (do-nyc3-prod):**
- `argocd-webhook-funnel` - Exposes `/api/webhook` for GitHub webhooks

To enable Funnel:

1. Add a dedicated `tag:k8s-funnel` to `tagOwners` (owned by `tag:k8s-operator`) and scope the `funnel` nodeAttr to it:
   ```json
   {
     "nodeAttrs": [
       {
         "target": ["tag:k8s-funnel"],
         "attr": ["funnel"]
       }
     ]
   }
   ```

2. Create the Ingress with both `tailscale.com/funnel: "true"` and `tailscale.com/tags: tag:k8s-funnel` annotations. The dedicated tag keeps Funnel scoped to this ingress only — every other ProxyGroup ingress runs under `tag:k8s-services` / `tag:k8s-ingress` and is unaffected.

See [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md) for a complete example.

### Rotating tags on an existing Funnel ingress

Changing `tailscale.com/tags` on an Ingress does not retag the existing proxy device — the operator only sets tags at device creation time, via the auth key it issues. To force a fresh registration with the new tag:

1. Delete the underlying device(s) from the Tailscale admin console (`https://login.tailscale.com/admin/machines`). Both the existing device and any `-N` suffixed duplicate created during a previous rotation must go.
2. Delete the Kubernetes Ingress (`kubectl -n {ns} delete ingress {name}`) and let ArgoCD recreate it from the chart.

The operator then issues a new auth key with the updated tag and the proxy registers with the original hostname.

## Current Ingress Configuration (do-nyc3-prod)

| Ingress | Hostname | Type | Notes |
|---------|----------|------|-------|
| miniflux | `miniflux.marlin-tet.ts.net` | ProxyGroup | `tag:k8s-services` |
| grafana | `grafana.marlin-tet.ts.net` | ProxyGroup | `tag:k8s-services` |
| grafana-mcp | `grafana-mcp-do-nyc3-prod.marlin-tet.ts.net` | ProxyGroup | `tag:k8s-services` |
| argocd-server | `argocd-do-nyc3-prod.marlin-tet.ts.net` | ProxyGroup | `tag:k8s-services` |
| argocd-webhook-funnel | `argocd-webhook-do-nyc3-prod.marlin-tet.ts.net` | Standalone | Funnel for GitHub webhooks; `tag:k8s-funnel` |

## Known Issues

## Files

| File | Purpose |
|------|---------|
| `terraform/global/tailscale.tf` | ACLs, OAuth clients, auth keys |
| `kubernetes/apps/tailscale-operator/` | Operator Helm chart wrapper |
| `kubernetes/apps/tailscale-operator/templates/proxygroup.yaml` | ProxyGroup resource |
| `kubernetes/apps/tailscale-operator/templates/proxyclass-ha.yaml` | HA ProxyClass with topology spread |

## Related

- [Migrate Ingress to ProxyGroup](../how-to/tailscale-proxygroup-ingress.md)
- [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md)
- [Tailscale Kubernetes Operator Docs](https://tailscale.com/kb/1236/kubernetes-operator)
- [ProxyGroup HA Ingress Docs](https://tailscale.com/kb/1439/kubernetes-operator-cluster-ingress)
