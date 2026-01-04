# Linkerd Viz

Linkerd observability extension providing metrics, dashboard, and live traffic inspection.

## Components

| Component | Purpose |
|-----------|---------|
| Dashboard | Web UI for service topology and stats |
| Metrics API | Queries Prometheus for `linkerd viz stat` commands |
| Tap | Live traffic sampling for debugging |
| Prometheus | Built-in metrics storage (6h retention) |

## Current Setup

The extension is deployed with its **built-in Prometheus** for metrics storage. This is a temporary configuration until Mimir and OpenTelemetry collectors are deployed.

### Accessing the Dashboard

```bash
# Port forward to the dashboard
kubectl port-forward -n linkerd-viz svc/web 8084:8084

# Or use linkerd CLI
linkerd viz dashboard
```

### Checking Stats

```bash
# View stats for all deployments
linkerd viz stat deploy -A

# View stats for a specific namespace
linkerd viz stat deploy -n loki

# Live traffic sampling
linkerd viz tap deploy/loki-gateway -n loki
```

## Migration to Mimir

When Mimir and OTel collectors are deployed, follow these steps to switch from the built-in Prometheus to external metrics storage.

### Step 1: Configure OTel to Scrape Linkerd Metrics

Linkerd proxies expose metrics on port 4191. Configure OTel collector to scrape:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'linkerd-proxy'
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            # Only scrape pods with linkerd proxy
            - source_labels: [__meta_kubernetes_pod_container_name]
              action: keep
              regex: linkerd-proxy
            - source_labels: [__meta_kubernetes_pod_container_port_name]
              action: keep
              regex: linkerd-admin
          metric_relabel_configs:
            # Keep only essential metrics to reduce cardinality
            - source_labels: [__name__]
              action: keep
              regex: 'request_total|response_total|response_latency_ms_bucket|tcp_.*'
```

### Step 2: Update Linkerd Viz Values

Once Mimir is receiving metrics, update the cluster values:

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/linkerd-viz/values.yaml
linkerd-viz:
  # Disable built-in Prometheus
  prometheus:
    enabled: false

  # Point to Mimir query frontend
  prometheusUrl: http://mimir-query-frontend.mimir.svc:8080/prometheus
```

### Step 3: Verify Migration

```bash
# Check that stats still work after migration
linkerd viz stat deploy -A

# Verify dashboard shows data
linkerd viz dashboard
```

### Step 4: Configure Grafana Dashboards (Optional)

If using external Grafana, import the Linkerd dashboards and configure the viz extension to link to them:

```yaml
linkerd-viz:
  grafana:
    externalUrl: https://grafana.example.com
    uidPrefix: linkerd-  # Prefix for dashboard UIDs
```

## Metrics Endpoints

Linkerd exposes metrics at these endpoints for OTel/Prometheus scraping:

| Endpoint | Port | Description |
|----------|------|-------------|
| `/metrics` on linkerd-proxy | 4191 | Per-pod proxy metrics (request counts, latencies) |
| `/metrics` on control plane | 9990 | Control plane component metrics |

## Retention

- Built-in Prometheus: 6 hours (sufficient for real-time dashboards)
- Mimir: Configure based on your retention policy (recommend 30+ days for historical analysis)
