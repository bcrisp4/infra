# Strimzi Kafka with Linkerd Service Mesh

This document describes the configuration required to run Strimzi Kafka clusters within the Linkerd service mesh.

## Overview

Strimzi Kafka requires specific Linkerd annotations because:
1. Kafka uses a binary protocol that Linkerd cannot parse (requires opaque mode)
2. Strimzi uses internal TLS on certain ports that conflicts with Linkerd's mTLS
3. Strimzi creates restrictive NetworkPolicies that block Linkerd's proxy ports

## Port Configuration

| Port | Purpose | Linkerd Mode |
|------|---------|--------------|
| 9092 | Kafka client (PLAINTEXT) | Opaque (binary protocol) |
| 9091 | Inter-broker replication | Skip (Strimzi TLS) |
| 9090 | KRaft controller | Skip (Strimzi TLS) |
| 8443 | Strimzi agent | Skip (Strimzi TLS) |

## Required Annotations

### Kafka Broker Pods

Set on the Kafka CR under `spec.kafka.template.pod.metadata.annotations`:

```yaml
spec:
  kafka:
    template:
      pod:
        metadata:
          annotations:
            # Skip Linkerd for ports with Strimzi TLS
            config.linkerd.io/skip-outbound-ports: "8443,9090,9091"
            config.linkerd.io/skip-inbound-ports: "8443,9090,9091"
            # Treat Kafka client port as opaque (binary protocol)
            config.linkerd.io/opaque-ports: "9092"
```

**Why these annotations:**
- `skip-inbound-ports`: Prevents Linkerd from intercepting inbound traffic on these ports. Strimzi already encrypts these with its own TLS.
- `skip-outbound-ports`: Prevents Linkerd proxy from wrapping outbound connections to these ports. Needed for inter-broker communication.
- `opaque-ports`: Tells Linkerd the protocol is opaque (not HTTP). Linkerd still provides mTLS but doesn't attempt protocol detection.

### Kafka Services

Set on the Kafka CR under `spec.kafka.template.bootstrapService` and `spec.kafka.template.brokersService`:

```yaml
spec:
  kafka:
    template:
      bootstrapService:
        metadata:
          annotations:
            config.linkerd.io/opaque-ports: "9092"
      brokersService:
        metadata:
          annotations:
            config.linkerd.io/opaque-ports: "9092"
```

**Why these annotations:**
Service-level `opaque-ports` ensures Linkerd's service profile discovery marks the port as opaque for all clients connecting via the service.

### Strimzi Operator

Set in the Strimzi operator Helm values:

```yaml
strimzi-kafka-operator:
  annotations:
    config.linkerd.io/skip-outbound-ports: "8443,9090,9091"
```

**Why:** The operator communicates with Kafka brokers on these TLS ports.

### Entity Operator

Set on the Kafka CR under `spec.entityOperator.template.pod.metadata.annotations`:

```yaml
spec:
  entityOperator:
    template:
      pod:
        metadata:
          annotations:
            config.linkerd.io/skip-outbound-ports: "9091"
```

**Why:** The entity operator (topic/user operator) connects to brokers on port 9091.

## NetworkPolicy for Linkerd

Strimzi automatically creates NetworkPolicies that only allow traffic to Kafka ports (9092, 9091, 9090, 8443, 9404). These block Linkerd's proxy-to-proxy communication on port 4143.

Create a supplementary NetworkPolicy to allow Linkerd ports:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mimir-kafka-allow-linkerd
spec:
  podSelector:
    matchLabels:
      strimzi.io/cluster: mimir-kafka
      strimzi.io/kind: Kafka
      strimzi.io/name: mimir-kafka-kafka
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}
      ports:
        - protocol: TCP
          port: 4143  # Linkerd inbound proxy
        - protocol: TCP
          port: 4190  # Linkerd tap
        - protocol: TCP
          port: 4191  # Linkerd admin/metrics
```

This NetworkPolicy is additive - it doesn't replace the Strimzi-created policies but supplements them.

## Common Mistakes

### 1. Using opaque-ports on client pods

**Wrong:**
```yaml
# On Mimir ingester/distributor pods
config.linkerd.io/opaque-ports: "9092"
```

**Why it's wrong:** `opaque-ports` on a pod only affects *inbound* traffic to that pod, not outbound. Since the ingester/distributor connect *to* Kafka (outbound), this annotation has no effect.

**Correct approach:** Put `opaque-ports: "9092"` on the Kafka *service* annotations, which affects clients routing through that service.

### 2. Using skip-outbound-ports instead of opaque-ports

**Wrong:**
```yaml
# On client pods
config.linkerd.io/skip-outbound-ports: "9092"
```

**Why it's usually wrong:** This bypasses Linkerd entirely for port 9092, losing mTLS encryption. Use this only when you need to completely bypass Linkerd (e.g., for ports with their own TLS).

**Correct approach:** Use `opaque-ports` on the Kafka service to maintain Linkerd mTLS while handling the binary protocol correctly.

### 3. Forgetting the NetworkPolicy

**Symptom:** Connection timeouts, "connection reset by peer" errors despite correct annotations.

**Root cause:** Strimzi NetworkPolicy blocks port 4143 (Linkerd inbound proxy).

**Fix:** Add the supplementary NetworkPolicy shown above.

## Verification

### Check Kafka pods have correct annotations

```bash
kubectl get pod mimir-kafka-combined-0 -n mimir -o jsonpath='{.metadata.annotations}' | jq -r 'to_entries[] | select(.key | startswith("config.linkerd")) | "\(.key): \(.value)"'
```

Expected output:
```
config.linkerd.io/opaque-ports: 9092
config.linkerd.io/skip-inbound-ports: 8443,9090,9091
config.linkerd.io/skip-outbound-ports: 8443,9090,9091
```

### Check services have correct annotations

```bash
kubectl get svc -n mimir -l strimzi.io/cluster=mimir-kafka -o jsonpath='{range .items[*]}{.metadata.name}: {.metadata.annotations.config\.linkerd\.io/opaque-ports}{"\n"}{end}'
```

Expected output:
```
mimir-kafka-kafka-bootstrap: 9092
mimir-kafka-kafka-brokers: 9092
```

### Check entity operator annotations

```bash
kubectl get pod -n mimir -l strimzi.io/name=mimir-kafka-entity-operator -o jsonpath='{.items[0].metadata.annotations}' | jq -r 'to_entries[] | select(.key | startswith("config.linkerd")) | "\(.key): \(.value)"'
```

Expected output:
```
config.linkerd.io/skip-outbound-ports: 9091
```

### Verify Linkerd mTLS is working

```bash
# Check Kafka pods are meshed
linkerd viz stat -n mimir deploy

# Check traffic from ingesters to Kafka
linkerd viz tap deploy/mimir-ingester -n mimir --to svc/mimir-kafka-kafka-bootstrap
```

## Troubleshooting

### Connection timeout errors

```
level=warn msg="send data to partitions: DoBatch: context deadline exceeded"
```

1. Check NetworkPolicy allows port 4143
2. Verify Kafka pods have `skip-inbound-ports` for Strimzi TLS ports
3. Check Linkerd proxy logs: `kubectl logs <kafka-pod> -c linkerd-proxy`

### Connection reset by peer

```
failed to read from server: read tcp: connection reset by peer
```

1. Usually caused by NetworkPolicy blocking Linkerd proxy ports
2. Verify the `mimir-kafka-allow-linkerd` NetworkPolicy exists
3. Check it targets the correct pod labels

### Protocol detection failures

```
level=warn msg="protocol detection failed" addr=x.x.x.x:9092
```

1. Verify `opaque-ports: "9092"` on Kafka services
2. Ensure annotation is on the *service*, not just the pods

## Related Files

- `kubernetes/apps/mimir/templates/kafka-cluster.yaml` - Kafka CR with Linkerd annotations
- `kubernetes/apps/mimir/templates/kafka-linkerd-networkpolicy.yaml` - Supplementary NetworkPolicy
- `kubernetes/clusters/do-nyc3-prod/apps/strimzi-kafka-operator/values.yaml` - Operator annotations
