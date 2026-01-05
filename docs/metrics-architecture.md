# Metrics Architecture

This document describes the metrics collection and storage infrastructure for do-nyc3-prod.

## Overview

```
                                    ┌─────────────────────────────────────────┐
                                    │              Grafana                    │
                                    │     (Visualization & Dashboards)        │
                                    └────────────────┬────────────────────────┘
                                                     │ PromQL queries
                                                     │ (X-Scope-OrgID: prod)
                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Mimir (Distributed)                              │
│  ┌─────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ Gateway │→ │ Distributor │→ │  Kafka   │→ │  Ingester   │→ │ S3 (DO    │ │
│  │         │  │             │  │ (Strimzi)│  │             │  │  Spaces)  │ │
│  └────┬────┘  └─────────────┘  └──────────┘  └─────────────┘  └───────────┘ │
│       │▲                                                             │       │
│       ││                       ┌──────────────┐  ┌──────────────┐    │       │
│       ││                       │ Store Gateway│← │  Compactor   │←───┘       │
│       ││                       └──────────────┘  └──────────────┘            │
│       │                                                                      │
│       └── /tenant/prod/ path adds X-Scope-OrgID for clients that can't      │
│           set headers (e.g., linkerd-viz metrics-api)                        │
└──────────────────────────────────────────────────────────────────────────────┘
        │ OTLP/HTTP (X-Scope-OrgID: prod)
        │
┌───────┴──────────────────────────────────────────────────────────────────────┐
│                         otel-metrics (DaemonSet)                              │
│  Scrapes metrics from pods, kubelet, cAdvisor, kube-apiserver, linkerd       │
└───────┬──────────────────────────────────────────────────────────────────────┘
        │ Prometheus scrape
        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Metric Sources                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ Application Pods│  │ kube-state-     │  │ node-exporter   │               │
│  │ (annotations)   │  │ metrics         │  │ (DaemonSet)     │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ kubelet/cAdvisor│  │ kube-apiserver  │  │ Linkerd proxies │               │
│  └─────────────────┘  └─────────────────┘  │ (port 4191)     │               │
│                                            └─────────────────┘               │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Metrics Collection

| Component | Type | Purpose |
|-----------|------|---------|
| **otel-metrics** | DaemonSet | Scrapes Prometheus metrics from pods and system components, forwards to Mimir via OTLP |
| **kube-state-metrics** | Deployment | Exposes Kubernetes object state (pods, nodes, PVCs, deployments) as metrics |
| **node-exporter** | DaemonSet | Exposes node-level hardware/OS metrics (CPU, memory, disk, network) |

### Metrics Storage

| Component | Type | Purpose |
|-----------|------|---------|
| **Mimir** | Distributed | Long-term metrics storage with Prometheus-compatible query API |
| **Strimzi Kafka** | StatefulSet (3 replicas) | Ingest buffer for Mimir - provides durability during ingester restarts |
| **DO Spaces** | Object Storage | S3-compatible backend for Mimir blocks, ruler, and alertmanager data |

### Visualization

| Component | Purpose |
|-----------|---------|
| **Grafana** | Dashboards and alerting, queries Mimir via Prometheus datasource |
| **linkerd-viz** | Service mesh dashboard, queries Mimir via tenant proxy |

### Multi-Tenancy

Mimir requires `X-Scope-OrgID` header for multi-tenancy. Current tenant: `prod`.

| Component | How it sets tenant |
|-----------|-------------------|
| **Grafana** | `secureJsonData.httpHeaderValue1: prod` in datasource config |
| **otel-metrics** | `headers: X-Scope-OrgID: prod` in OTLP exporter |
| **linkerd-viz** | Via gateway's `/tenant/prod/` path (cannot set headers directly) |

The Mimir gateway exposes a `/tenant/prod/` path that adds the `X-Scope-OrgID: prod` header for clients that cannot set custom HTTP headers.

## Data Flow

1. **otel-metrics** DaemonSet runs on every node
2. Scrapes metrics every 30s from:
   - Pods with `prometheus.io/scrape: "true"` annotation
   - Pods with ports named `*metrics*` (fallback)
   - kubelet metrics (port 10250)
   - cAdvisor metrics (/metrics/cadvisor)
   - kube-apiserver metrics
3. Scrapes Linkerd proxy metrics every 10s from:
   - Linkerd sidecar containers on port 4191 (linkerd-admin)
   - Filtered to request/response/TCP metrics only
4. Adds `cluster: do-nyc3-prod` resource attribute
5. Sends to Mimir Gateway via OTLP/HTTP with `X-Scope-OrgID: prod` header
6. Mimir distributes to Kafka, then ingesters write to S3

## DOKS-Specific Considerations

DigitalOcean Kubernetes (DOKS) is a managed service. Some components are NOT accessible:

| Component | Accessible | Notes |
|-----------|------------|-------|
| kubelet | Yes | Port 10250, requires service account token |
| cAdvisor | Yes | Via kubelet /metrics/cadvisor |
| kube-apiserver | Yes | Via kubernetes service in default namespace |
| CoreDNS | Yes | Standard pod scraping |
| **etcd** | **No** | Managed by DigitalOcean |
| **kube-scheduler** | **No** | Managed by DigitalOcean |
| **kube-controller-manager** | **No** | Managed by DigitalOcean |

## Adding Metrics to Your Application

### Option 1: Prometheus Annotations (Recommended)

Add these annotations to your pod spec:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"        # Optional: defaults to container port
    prometheus.io/path: "/metrics"    # Optional: defaults to /metrics
    prometheus.io/scheme: "http"      # Optional: http or https
```

### Option 2: Port Naming (Fallback)

Name your metrics port with "metrics" in the name:

```yaml
ports:
  - name: http-metrics  # or "metrics", "prom-metrics", etc.
    containerPort: 8080
```

### Custom Labels

Add custom labels to your metrics via annotations:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/label-cluster: "do-nyc3-prod"
    prometheus.io/label-environment: "production"
    prometheus.io/label-service: "my-app"
```

## Querying Metrics

### Via Grafana

Grafana is configured with Mimir as a Prometheus datasource. Use standard PromQL:

```promql
# Container CPU usage
rate(container_cpu_usage_seconds_total{namespace="my-app"}[5m])

# Memory usage
container_memory_working_set_bytes{namespace="my-app"}

# Pod status
kube_pod_status_phase{namespace="my-app"}

# Node disk usage
node_filesystem_avail_bytes{mountpoint="/"}
```

### Via Mimir API

Direct queries to Mimir (requires X-Scope-OrgID header):

```bash
curl -H "X-Scope-OrgID: prod" \
  "http://mimir-gateway.mimir.svc.cluster.local/prometheus/api/v1/query?query=up"
```

## Available Metrics

### From kube-state-metrics

- `kube_pod_status_phase` - Pod lifecycle state
- `kube_pod_container_status_restarts_total` - Container restart count
- `kube_deployment_status_replicas` - Deployment replica counts
- `kube_node_status_condition` - Node health conditions
- `kube_persistentvolumeclaim_status_phase` - PVC states
- `kube_job_status_succeeded` - Job completion status

### From node-exporter

- `node_cpu_seconds_total` - CPU time by mode
- `node_memory_MemTotal_bytes` - Total memory
- `node_memory_MemAvailable_bytes` - Available memory
- `node_filesystem_size_bytes` - Filesystem size
- `node_filesystem_avail_bytes` - Available disk space
- `node_network_receive_bytes_total` - Network RX
- `node_network_transmit_bytes_total` - Network TX

### From kubelet/cAdvisor

- `container_cpu_usage_seconds_total` - Container CPU usage
- `container_memory_working_set_bytes` - Container memory
- `container_network_receive_bytes_total` - Container network RX
- `container_network_transmit_bytes_total` - Container network TX
- `kubelet_volume_stats_used_bytes` - PVC usage
- `kubelet_volume_stats_capacity_bytes` - PVC capacity

### From kube-apiserver

- `apiserver_request_total` - API request counts
- `apiserver_request_duration_seconds` - API latency
- `etcd_request_duration_seconds` - etcd latency (from apiserver perspective)

### From Linkerd Proxies

Scraped from port 4191 on meshed pods. Labels include `namespace`, `pod`, `deployment` (or `statefulset`/`daemonset`).

- `request_total` - Total requests by direction (inbound/outbound), target, status
- `response_total` - Total responses by direction, target, status code, classification
- `response_latency_ms_bucket` - Response latency histogram buckets
- `response_latency_ms_count` - Response latency count
- `response_latency_ms_sum` - Response latency sum
- `tcp_open_total` - TCP connections opened
- `tcp_close_total` - TCP connections closed
- `tcp_read_bytes_total` - Bytes read from TCP connections
- `tcp_write_bytes_total` - Bytes written to TCP connections

## Retention and Limits

| Setting | Value |
|---------|-------|
| Mimir retention | Default (configurable per tenant) |
| Kafka retention | 6 hours |
| Max label names per series | 60 |
| Ingestion rate limit | 100,000 samples/s |
| Ingestion burst limit | 200,000 samples/s |
| Max global series per user | 1,500,000 |

## Troubleshooting

### No metrics from a pod

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

### Missing kubelet/cAdvisor metrics

1. Check otel-metrics has RBAC permissions:
   ```bash
   kubectl auth can-i get nodes/metrics --as=system:serviceaccount:otel-metrics:otel-metrics-opentelemetry-collector
   ```

2. Check kubelet is accessible:
   ```bash
   kubectl get --raw /api/v1/nodes/<node>/proxy/metrics
   ```

### Mimir not receiving data

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

### Missing Linkerd metrics

1. Check pod is meshed (has linkerd-proxy container):
   ```bash
   kubectl get pod -n <namespace> <pod> -o jsonpath='{.spec.containers[*].name}'
   # Should include "linkerd-proxy"
   ```

2. Check linkerd-proxy exposes metrics:
   ```bash
   kubectl port-forward -n <namespace> <pod> 4191:4191
   curl localhost:4191/metrics | head -20
   ```

3. Check otel-metrics is scraping Linkerd proxies:
   ```bash
   kubectl logs -n otel-metrics -l app.kubernetes.io/name=opentelemetry-collector --tail=100 | grep linkerd
   ```

### linkerd-viz showing no data

1. Verify Mimir gateway is running:
   ```bash
   kubectl get pods -n mimir -l app.kubernetes.io/component=gateway
   ```

2. Test tenant endpoint connectivity:
   ```bash
   kubectl run curl --rm -it --image=curlimages/curl -- \
     curl -v "http://mimir-gateway.mimir.svc.cluster.local/tenant/prod/prometheus/api/v1/query?query=up"
   ```

3. Check linkerd-viz metrics-api logs:
   ```bash
   kubectl logs -n linkerd-viz deploy/metrics-api --tail=100
   ```

## Related Documentation

- [Mimir Documentation](https://grafana.com/docs/mimir/latest/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics)
- [Prometheus node-exporter](https://github.com/prometheus/node_exporter)
- [Linkerd Proxy Metrics](https://linkerd.io/2-edge/reference/proxy-metrics/)
