# Metrics Troubleshooting

Common issues with Prometheus metrics collection, Thanos long-term storage, and scraping.

## No metrics from a pod

1. Check pod has scrape annotation or a ServiceMonitor/PodMonitor:
   ```bash
   kubectl get pod <pod> -o jsonpath='{.metadata.annotations}'
   kubectl get servicemonitors -A
   ```

2. Check Prometheus targets:
   ```bash
   kubectl port-forward -n prometheus svc/prometheus-kube-prometheus-prometheus 9090
   # Visit http://localhost:9090/targets
   ```

3. Verify pod exposes /metrics endpoint:
   ```bash
   kubectl port-forward <pod> 8080:8080
   curl localhost:8080/metrics
   ```

## Thanos Store Gateway not serving historical data

1. Check store gateway logs for block sync errors:
   ```bash
   kubectl logs -n thanos thanos-store-0 --tail=100
   ```

2. Verify the objstore secret exists and is synced:
   ```bash
   kubectl get externalsecret -n thanos thanos-objstore-config
   kubectl get secret -n thanos thanos-objstore-config
   ```

3. Check blocks exist in object storage:
   ```bash
   # The Thanos sidecar on Prometheus uploads 2-hour TSDB blocks
   kubectl logs -n prometheus prometheus-kube-prometheus-prometheus-0 -c thanos-sidecar --tail=50
   ```

## Thanos Compactor issues

1. Check compactor logs for errors:
   ```bash
   kubectl logs -n thanos thanos-compact-0 --tail=100
   ```

2. Check compactor is running (not crash-looping):
   ```bash
   kubectl get pods -n thanos -l app.kubernetes.io/component=compact
   ```

3. Common issues:
   - **Overlapping blocks**: The compactor will halt if it detects overlapping blocks. Check logs for `overlapping blocks` errors.
   - **Bucket permission errors**: Verify the S3 credentials in the ExternalSecret are correct.

## Thanos Query returning no data

1. Check query can reach its endpoints:
   ```bash
   kubectl logs -n thanos -l app.kubernetes.io/component=query --tail=100
   ```

2. Verify endpoints are registered:
   ```bash
   kubectl port-forward -n thanos svc/thanos-query 10902
   # Visit http://localhost:10902/stores to see connected stores
   ```

3. Check the Prometheus sidecar is exposing the Store API:
   ```bash
   kubectl logs -n prometheus prometheus-kube-prometheus-prometheus-0 -c thanos-sidecar --tail=50
   ```

## Related

- [Metrics Architecture](../reference/metrics-architecture.md)
