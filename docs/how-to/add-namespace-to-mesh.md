# Add a Namespace to Linkerd Mesh

How to enable Linkerd mTLS for an application namespace.

## Prerequisites

- Linkerd control plane installed
- App deployed via ArgoCD

## Steps

### 1. Update the app's config.yaml

Add the `namespaceAnnotations` section:

```yaml
# kubernetes/clusters/{cluster}/apps/{app}/config.yaml
name: my-app
namespaceAnnotations:
  linkerd.io/inject: enabled
```

### 2. Commit and push

```bash
git add kubernetes/clusters/{cluster}/apps/{app}/config.yaml
git commit -m "Enable Linkerd injection for my-app namespace"
git push
```

### 3. Wait for ArgoCD sync

ArgoCD will apply the namespace annotation via `managedNamespaceMetadata`.

### 4. Restart existing pods

New pods automatically get sidecars, but existing pods need a restart:

```bash
kubectl rollout restart deployment -n <namespace>
kubectl rollout restart statefulset -n <namespace>
```

### 5. Verify pods are meshed

Check pods have 2/2 containers:

```bash
kubectl get pods -n <namespace>
# READY column should show 2/2
```

Verify mTLS is working:

```bash
linkerd viz stat deploy -n <namespace>
# Should show MESHED=1/1 and SUCCESS rate
```

## Removing from Mesh

To remove a namespace from the mesh:

1. Remove the `namespaceAnnotations` section (or set to `{}`)
2. Commit and push
3. Restart pods

## Troubleshooting

### Pods still show 1/1

- Verify namespace has the annotation: `kubectl get ns <namespace> -o yaml`
- Check if pods were created before the annotation was applied (restart them)
- Verify Linkerd proxy-injector is running: `kubectl get pods -n linkerd`

### mTLS not showing in linkerd viz

- Ensure both source and destination pods are meshed
- Check for `skip-*-ports` annotations that might bypass Linkerd

See [Linkerd Troubleshooting](../troubleshooting/linkerd.md) for more issues.

## Related

- [Linkerd Reference](../reference/linkerd.md)
- [Strimzi Kafka with Linkerd](strimzi-kafka-linkerd.md) - Special handling for Kafka
