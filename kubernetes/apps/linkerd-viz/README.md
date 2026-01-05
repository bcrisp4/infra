# Linkerd Viz

Linkerd observability extension providing metrics, dashboard, and live traffic inspection.

## Components

| Component | Purpose |
|-----------|---------|
| Dashboard | Web UI for service topology and stats |
| Metrics API | Queries Mimir for `linkerd viz stat` commands |
| Tap | Live traffic sampling for debugging |

## Current Setup

The extension uses **Mimir** as the external metrics backend:
- Linkerd proxy metrics scraped by otel-metrics collectors (port 4191)
- Metrics stored in Mimir with 30+ day retention
- Built-in Prometheus disabled

### Architecture

```
Linkerd proxies (port 4191)
    |
    v (scrape)
otel-metrics DaemonSet
    |
    v (OTLP with X-Scope-OrgID: prod)
Mimir
    ^
    | (query)
mimir-tenant-proxy-prod (adds X-Scope-OrgID: prod)
    ^
    | (query without header)
linkerd-viz metrics-api
```

The tenant proxy is needed because linkerd-viz cannot set custom HTTP headers. The proxy adds the `X-Scope-OrgID: prod` header before forwarding to the Mimir gateway.

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

## Reverting to Built-in Prometheus

If needed, revert to built-in Prometheus:

```yaml
# kubernetes/clusters/{cluster}/apps/linkerd-viz/values.yaml
linkerd-viz:
  prometheus:
    enabled: true
    args:
      storage.tsdb.retention.time: 6h

  prometheusUrl: ""  # Empty = use built-in
```

## Metrics Endpoints

Linkerd exposes metrics at these endpoints for OTel/Prometheus scraping:

| Endpoint | Port | Description |
|----------|------|-------------|
| `/metrics` on linkerd-proxy | 4191 | Per-pod proxy metrics (request counts, latencies) |
| `/metrics` on control plane | 9990 | Control plane component metrics |

## Grafana Integration (Optional)

To link the viz dashboard to external Grafana:

```yaml
linkerd-viz:
  grafana:
    externalUrl: https://grafana-do-nyc3-prod.marlin-tet.ts.net
    uidPrefix: linkerd-
```
