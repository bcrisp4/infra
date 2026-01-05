# Linkerd Troubleshooting

Common issues with the Linkerd service mesh, mTLS, and proxy sidecars.

## Pod not in mesh

**Symptom:** Pod shows 1/1 containers instead of 2/2, no mTLS.

1. Check namespace has injection annotation:
   ```bash
   kubectl get ns <namespace> -o jsonpath='{.metadata.annotations.linkerd\.io/inject}'
   # Should output: enabled
   ```

2. If annotation is missing, add it to the app's `config.yaml`:
   ```yaml
   namespaceAnnotations:
     linkerd.io/inject: enabled
   ```

3. Restart pods after adding annotation:
   ```bash
   kubectl rollout restart deployment -n <namespace>
   ```

## Verifying mTLS is working

```bash
# Check pods are meshed (should show MESHED column)
linkerd viz stat deploy -n <namespace>

# Watch live traffic
linkerd viz tap deploy/<deployment> -n <namespace>
```

## Connection timeout errors (Kafka/Strimzi)

**Symptom:**
```
level=warn msg="send data to partitions: DoBatch: context deadline exceeded"
```

**Causes and fixes:**

1. NetworkPolicy blocking Linkerd proxy ports
   - Strimzi creates restrictive NetworkPolicies
   - Add supplementary NetworkPolicy allowing ports 4143, 4190, 4191

2. Missing `skip-inbound-ports` annotation on Kafka pods
   - Strimzi uses internal TLS on ports 8443, 9090, 9091
   - Add: `config.linkerd.io/skip-inbound-ports: "8443,9090,9091"`

3. Check Linkerd proxy logs:
   ```bash
   kubectl logs <kafka-pod> -c linkerd-proxy --tail=100
   ```

## Connection reset by peer

**Symptom:**
```
failed to read from server: read tcp: connection reset by peer
```

**Most common cause:** NetworkPolicy blocking Linkerd proxy port 4143.

1. Check the supplementary NetworkPolicy exists:
   ```bash
   kubectl get networkpolicy -n <namespace> | grep linkerd
   ```

2. Verify it allows port 4143 ingress from all pods in namespace

See [Strimzi Kafka with Linkerd](../how-to/strimzi-kafka-linkerd.md) for full NetworkPolicy example.

## Protocol detection failures

**Symptom:**
```
level=warn msg="protocol detection failed" addr=x.x.x.x:9092
```

**Cause:** Linkerd trying to detect HTTP on a binary protocol (e.g., Kafka).

**Fix:** Mark port as opaque on the *service* (not the pod):
```yaml
metadata:
  annotations:
    config.linkerd.io/opaque-ports: "9092"
```

## Jobs never complete

**Symptom:** Kubernetes Jobs stay in Running state forever, main container exits but pod continues.

**Cause:** Linkerd sidecar keeps running after main container exits.

**Fix:** Enable native sidecars (requires Linkerd edge release + K8s 1.29+):
```yaml
# In linkerd values.yaml
proxy:
  nativeSidecar: true
```

See [Linkerd Edge Releases](../explanation/linkerd-edge-releases.md) for details.

## Proxy injection blocked by pod resources

**Symptom:** Pods fail to start with resource validation errors when Linkerd injects sidecar.

**Cause:** Pod-level resources set too low (Kubernetes 1.34+ with `PodLevelResources` feature gate).

**Example error:**
```
pod-level resources must be >= aggregate container resources
```

**Fix:** Ensure pod-level resources accommodate sidecar (100m CPU, 32Mi memory minimum).

## Common Linkerd annotations

| Annotation | Purpose | Where to apply |
|------------|---------|----------------|
| `config.linkerd.io/skip-inbound-ports` | Skip Linkerd for inbound traffic on ports | Pod |
| `config.linkerd.io/skip-outbound-ports` | Skip Linkerd for outbound traffic to ports | Pod |
| `config.linkerd.io/opaque-ports` | Mark ports as opaque (binary protocol) | Service or Pod |

**Note:** `opaque-ports` on a pod only affects *inbound* traffic. For clients connecting *to* a service, put it on the Service.

## Related

- [Linkerd Reference](../reference/linkerd.md)
- [Strimzi Kafka with Linkerd](../how-to/strimzi-kafka-linkerd.md)
- [Add Namespace to Mesh](../how-to/add-namespace-to-mesh.md)
