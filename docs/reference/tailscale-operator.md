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

ACL example:
```json
{
  "tagOwners": {
    "tag:k8s-operator": [],
    "tag:k8s": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"],
    "tag:k8s-ingress": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"],
    "tag:k8s-services": ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"]
  }
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

## Known Issues

### Pod-Level Resources Bug (Operator 1.92.x)

Tailscale operator v1.92.x sets pod-level resources to 1m/1Mi. On Kubernetes 1.34+ with `PodLevelResources` feature gate enabled, this causes validation failures when:
- Using custom container resources in ProxyClass
- Enabling Linkerd sidecar injection

**Workaround:** Don't set custom resources in ProxyClass until operator 1.94+.

See [Re-enable Linkerd for Tailscale Operator](../tasks/tailscale-operator-1.94-linkerd.md) for tracking.

## Files

| File | Purpose |
|------|---------|
| `terraform/global/tailscale.tf` | ACLs, OAuth clients, auth keys |
| `kubernetes/apps/tailscale-operator/` | Operator Helm chart wrapper |
| `kubernetes/apps/tailscale-operator/templates/proxygroup.yaml` | ProxyGroup resource |
| `kubernetes/apps/tailscale-operator/templates/proxyclass-ha.yaml` | HA ProxyClass with topology spread |
| `kubernetes/apps/tailscale-operator/templates/proxyclass.yaml` | Linkerd-enabled ProxyClass (blocked until 1.94) |

## Related

- [Migrate Ingress to ProxyGroup](../how-to/tailscale-proxygroup-ingress.md)
- [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md)
- [Re-enable Linkerd for Tailscale Operator](../tasks/tailscale-operator-1.94-linkerd.md)
- [Tailscale Kubernetes Operator Docs](https://tailscale.com/kb/1236/kubernetes-operator)
- [ProxyGroup HA Ingress Docs](https://tailscale.com/kb/1439/kubernetes-operator-cluster-ingress)
