# Migrate Ingress to Tailscale ProxyGroup

How to migrate a Tailscale ingress to use the shared ProxyGroup for HA.

## Prerequisites

- ProxyGroup `ingress-proxies` is running (enabled in cluster's tailscale-operator values)
- ACLs configured with `tag:k8s-ingress` and `tag:k8s-services` (already done in `terraform/global/tailscale.tf`)

Verify ProxyGroup is ready:
```bash
kubectl get proxygroup ingress-proxies
# Should show STATUS: ProxyGroupReady
```

## Migration Steps

### 1. Update the Ingress Template

ProxyGroup ingresses require a different format than standard Kubernetes Ingress.

**Before (standard format):**
```yaml
spec:
  ingressClassName: tailscale
  tls:
    - secretName: myapp-tls
      hosts:
        - myapp
  rules:
    - host: myapp
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 8080
```

**After (ProxyGroup format):**
```yaml
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

**Key changes:**
- Replace `rules` with `defaultBackend`
- Remove `host` from rules (hostname only in `tls.hosts`)
- Remove `tls.secretName` (Tailscale provides certs)

### 2. Add ProxyGroup Annotations

Add annotations to the values.yaml for your app:

```yaml
# kubernetes/clusters/{cluster}/apps/{app}/values.yaml
ingress:
  enabled: true
  className: tailscale
  host: myapp
  annotations:
    tailscale.com/proxy-group: ingress-proxies
    tailscale.com/tags: tag:k8s-services
```

The `tailscale.com/proxy-group` annotation tells the operator to use the shared ProxyGroup instead of creating a dedicated proxy.

The `tailscale.com/tags` annotation sets the tag on the Tailscale Service (defaults to `tag:k8s` if not specified).

### 3. Update Template to Support Annotations

If your ingress template doesn't support annotations, add them:

```yaml
# kubernetes/apps/{app}/templates/ingress.yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  defaultBackend:
    service:
      name: {{ .Release.Name }}
      port:
        number: {{ .Values.service.port }}
  tls:
    - hosts:
        - {{ .Values.ingress.host }}
{{- end }}
```

### 4. Push and Verify

```bash
git add -A && git commit -m "Migrate {app} ingress to ProxyGroup" && git push
```

Wait for ArgoCD to sync, then verify:

```bash
# Check ingress has an address
kubectl get ingress -n {namespace} {name}

# Check for any errors
kubectl describe ingress -n {namespace} {name}

# Test connectivity (from a tailnet device)
curl https://{hostname}.marlin-tet.ts.net/
```

### 5. Verify Old Proxy Cleanup

The operator should automatically clean up the old per-ingress proxy:

```bash
kubectl get statefulset -n tailscale-operator
# Should NOT see ts-{app}-* StatefulSet for this app
# Should see ingress-proxies StatefulSet
```

## Common Issues

### "rule with host ignored, unsupported"

```
Warning  InvalidIngressBackend  tailscale-operator  rule with host "myapp" ignored, unsupported
```

**Cause:** Using `rules` with `host` field instead of `defaultBackend`.

**Fix:** Change ingress spec to use `defaultBackend` format (see step 1).

### Ingress has no ADDRESS

**Cause:** ProxyGroup might not be ready, or annotations are missing.

**Check:**
```bash
# Verify ProxyGroup is ready
kubectl get proxygroup ingress-proxies

# Verify annotations
kubectl get ingress -n {namespace} {name} -o yaml | grep -A5 annotations
```

### ProxyGroup stuck in ProxyGroupCreationFailed

**Cause:** Likely the pod-level resources bug in operator 1.92.x.

**Check:**
```bash
kubectl get proxygroup ingress-proxies -o yaml | grep -A5 "message:"
```

If you see resource validation errors, remove custom resources from ProxyClass until operator 1.94+.

## Example: Miniflux Migration

**Template** (`kubernetes/apps/miniflux/templates/ingress.yaml`):
```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: miniflux
  labels:
    app.kubernetes.io/name: miniflux
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  defaultBackend:
    service:
      name: miniflux
      port:
        number: {{ .Values.service.port }}
  tls:
    - hosts:
        - {{ .Values.ingress.host }}
{{- end }}
```

**Values** (`kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml`):
```yaml
ingress:
  enabled: true
  className: tailscale
  host: miniflux
  annotations:
    tailscale.com/proxy-group: ingress-proxies
    tailscale.com/tags: tag:k8s-services
```

## Related

- [Tailscale Operator Reference](../reference/tailscale-operator.md)
- [ProxyGroup HA Ingress Docs](https://tailscale.com/kb/1439/kubernetes-operator-cluster-ingress)
