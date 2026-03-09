# Metrics Troubleshooting

Common issues with metrics collection, Mimir storage, and otel-metrics collectors.

## No metrics from a pod

1. Check pod has scrape annotation:
   ```bash
   kubectl get pod <pod> -o jsonpath='{.metadata.annotations}'
   ```

2. Check otel-metrics logs:
   ```bash
   kubectl logs -n otel-metrics -l app.kubernetes.io/name=opentelemetry-collector --tail=100
   ```

3. Verify pod exposes /metrics endpoint:
   ```bash
   kubectl port-forward <pod> 8080:8080
   curl localhost:8080/metrics
   ```

## Missing kubelet/cAdvisor metrics

1. Check otel-metrics has RBAC permissions:
   ```bash
   kubectl auth can-i get nodes/metrics --as=system:serviceaccount:otel-metrics:otel-metrics-opentelemetry-collector
   ```

2. Check kubelet is accessible:
   ```bash
   kubectl get --raw /api/v1/nodes/<node>/proxy/metrics
   ```

## Mimir not receiving data

1. Check Kafka cluster health:
   ```bash
   kubectl get kafka -n mimir
   kubectl get pods -n mimir -l strimzi.io/cluster=mimir-kafka
   ```

2. Check Mimir distributor logs:
   ```bash
   kubectl logs -n mimir -l app.kubernetes.io/component=distributor --tail=100
   ```

3. Check Mimir gateway is reachable:
   ```bash
   kubectl run curl --rm -it --image=curlimages/curl -- \
     curl -v http://mimir-gateway.mimir.svc.cluster.local/ready
   ```

4. Check Mimir-Kafka connectivity:
   ```bash
   # Check for connection errors in distributor/ingester logs
   kubectl logs -n mimir -l app.kubernetes.io/component=ingester --tail=100 | grep -i "kafka\|reset\|timeout"
   ```

## Related

- [Metrics Architecture](../reference/metrics-architecture.md)
