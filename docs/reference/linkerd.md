# Linkerd Service Mesh

Reference documentation for the Linkerd service mesh configuration.

## Overview

Linkerd provides automatic mTLS between meshed workloads using a sidecar proxy model.

## Architecture

- **Control plane:** Runs in `linkerd` namespace
- **Certificates:** Managed by cert-manager with a self-signed CA
- **Trust bundles:** Distributed via trust-manager to all namespaces
- **Injection:** Controlled via namespace annotations

## Namespace Injection

To add a namespace to the mesh, set the annotation in the app's `config.yaml`:

```yaml
# kubernetes/clusters/{cluster}/apps/{app}/config.yaml
name: my-app
namespaceAnnotations:
  linkerd.io/inject: enabled
```

ArgoCD applies this annotation via `managedNamespaceMetadata`.

### What Happens

1. ArgoCD creates/updates the namespace with the annotation
2. Linkerd's proxy-injector webhook intercepts pod creation
3. A `linkerd-proxy` sidecar container is added to each pod
4. mTLS is automatically enabled between meshed pods

### After Adding Annotation

Restart existing pods to inject sidecars:

```bash
kubectl rollout restart deployment -n <namespace>
kubectl rollout restart statefulset -n <namespace>
```

### Removing from Mesh

Remove the `namespaceAnnotations` section or set it to `{}`.

## Verification Commands

### Check namespace annotation

```bash
kubectl get ns <namespace> -o jsonpath='{.metadata.annotations.linkerd\.io/inject}'
# Should output: enabled
```

### Check pods have sidecars

```bash
kubectl get pods -n <namespace>
# READY column should show 2/2 (or 3/3 for pods with multiple containers)
```

### Verify mTLS with linkerd viz

```bash
linkerd viz stat deploy -n <namespace>
# Should show MESHED=1/1 and SUCCESS rate
```

### Check specific pod

```bash
kubectl get pod -n <namespace> <pod-name> -o jsonpath='{.spec.containers[*].name}'
# Should include "linkerd-proxy"
```

## Known Issues

| Issue | Description |
|-------|-------------|
| cert-manager | Cannot have Linkerd injection (circular dependency - Linkerd excludes it automatically) |
| Tailscale operator | Requires Tailscale 1.94.0+ for Linkerd compatibility |
| Strimzi Kafka | Requires special annotations and supplementary NetworkPolicy |

## Linkerd Annotations

| Annotation | Purpose | Where |
|------------|---------|-------|
| `config.linkerd.io/skip-inbound-ports` | Skip Linkerd for inbound traffic | Pod |
| `config.linkerd.io/skip-outbound-ports` | Skip Linkerd for outbound traffic | Pod |
| `config.linkerd.io/opaque-ports` | Mark ports as opaque (binary protocol) | Service or Pod |

**Note:** `opaque-ports` on a pod only affects *inbound* traffic. For clients connecting *to* a service, put it on the Service.

## Related

- [Linkerd Edge Releases](../explanation/linkerd-edge-releases.md) - Why we use edge releases
- [Add Namespace to Mesh](../how-to/add-namespace-to-mesh.md)
- [Update Linkerd Edge](../how-to/update-linkerd-edge.md)
- [Strimzi Kafka with Linkerd](../how-to/strimzi-kafka-linkerd.md)
- [Linkerd Troubleshooting](../troubleshooting/linkerd.md)
