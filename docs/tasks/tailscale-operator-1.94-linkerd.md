# Re-enable Linkerd for Tailscale Operator

**Status**: Pending release of Tailscale operator 1.94.0
**Target date**: ~Jan 14, 2026
**Tracking**: https://github.com/tailscale/tailscale/issues/17000

## Background

Tailscale operator v1.92.x has a bug where it sets pod-level resources to 1m/1Mi in its StatefulSet template. Kubernetes 1.34+ enables the `PodLevelResources` feature gate by default, which validates that pod-level resources must be >= aggregate container resources.

When Linkerd injects its sidecar (100m CPU, 32Mi memory minimum), the validation fails because 1m < 100m.

This prevents Tailscale proxy pods from participating in the Linkerd mesh.

## When to Apply

After upgrading to Tailscale operator 1.94.0 or later.

Check the current version:
```bash
kubectl get deployment operator -n tailscale-operator -o jsonpath='{.spec.template.spec.containers[0].image}'
```

## Steps

### 1. Update Tailscale operator version

Update the chart version in `kubernetes/apps/tailscale-operator/Chart.yaml` to include the fix.

### 2. Re-enable Linkerd injection for tailscale-operator namespace

Edit `kubernetes/clusters/do-nyc3-prod/apps/tailscale-operator/config.yaml`:

```yaml
name: tailscale-operator
namespaceAnnotations:
  linkerd.io/inject: enabled
```

### 3. Re-enable ProxyClass for ArgoCD ingress

Edit `kubernetes/clusters/do-nyc3-prod/argocd/bootstrap/values.yaml`:

```yaml
    ingress:
      enabled: true
      ingressClassName: tailscale
      hostname: argocd-do-nyc3-prod
      tls: true
      annotations:
        tailscale.com/proxy-class: linkerd-mesh
```

### 4. Commit and push

```bash
git add -A
git commit -m "Re-enable Linkerd for Tailscale operator proxies

Tailscale operator 1.94.0 fixes the pod-level resources bug that
prevented Linkerd sidecar injection on Kubernetes 1.34+.

See: https://github.com/tailscale/tailscale/issues/17000"
git push
```

### 5. Verify

After ArgoCD syncs, verify the proxy pods have Linkerd sidecars:

```bash
# Check proxy pod has 2/2 containers (tailscale + linkerd-proxy)
kubectl get pods -n tailscale-operator

# Verify mTLS is working
linkerd viz stat deploy -n tailscale-operator
```

## Related Files

- `kubernetes/apps/tailscale-operator/templates/proxyclass.yaml` - ProxyClass with Linkerd injection and sufficient resources
- `kubernetes/clusters/do-nyc3-prod/apps/tailscale-operator/config.yaml` - Namespace annotations
- `kubernetes/clusters/do-nyc3-prod/argocd/bootstrap/values.yaml` - ArgoCD ingress configuration