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
        ▲ OTLP/HTTP (X-Scope-OrgID: prod)              ▲ OTLP/HTTP
        │                                              │
┌───────┴──────────────────────────┐   ┌───────────────┴───────────────────────┐
│     otel-metrics (DaemonSet)     │   │     otel-metrics-push (DaemonSet)     │
│  Scrapes Prometheus metrics from │   │  Receives OTLP metrics from apps,    │
│  pods, kubelet, apiserver, etc.  │   │  enriches with k8s metadata          │
└───────┬──────────────────────────┘   └───────────────▲───────────────────────┘
        │ Prometheus scrape                            │ OTLP (gRPC/HTTP)
        ▼                                              │
┌──────────────────────────────────────────────────────┴───────────────────────┐
│                            Metric Sources                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ Application Pods│  │ kube-state-     │  │ node-exporter   │               │
│  │ (annotations)   │  │ metrics         │  │ (DaemonSet)     │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ kubelet/cAdvisor│  │ kube-apiserver  │  │ Linkerd proxies │               │
│  └─────────────────┘  └─────────────────┘  │ (port 4191)     │               │
│                                            └─────────────────┘               │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │ Applications with OpenTelemetry SDK (push OTLP metrics)     │             │
│  └─────────────────────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Metrics Collection

| Component | Type | Purpose |
|-----------|------|---------|
| **otel-metrics** | DaemonSet | Scrapes Prometheus metrics from pods and system components, forwards to Mimir via OTLP |
| **otel-metrics-push** | DaemonSet | Receives OTLP metrics from applications, enriches with k8s metadata, forwards to Mimir |
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
| **otel-metrics-push** | `headers: X-Scope-OrgID: prod` in OTLP exporter |
| **linkerd-viz** | Via gateway's `/tenant/prod/` path (cannot set headers directly) |

The Mimir gateway exposes a `/tenant/prod/` path that adds the `X-Scope-OrgID: prod` header for clients that cannot set custom HTTP headers.

## Data Flow

### Pull-based Collection (otel-metrics)

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

### Push-based Collection (otel-metrics-push)

1. **otel-metrics-push** DaemonSet runs on every node
2. Applications send OTLP metrics to the collector:
   - gRPC: `otel-metrics-push.otel-metrics-push.svc.cluster.local:4317`
   - HTTP: `otel-metrics-push.otel-metrics-push.svc.cluster.local:4318`
3. Service uses `internalTrafficPolicy: Local` for node-local routing
4. Collector enriches metrics with Kubernetes metadata via k8sattributes processor:
   - `k8s.namespace.name`, `k8s.pod.name`, `k8s.container.name`
   - `k8s.deployment.name`, `k8s.statefulset.name`, `k8s.daemonset.name`
5. Adds `cluster: do-nyc3-prod` resource attribute
6. Sends to Mimir Gateway via OTLP/HTTP with `X-Scope-OrgID: prod` header

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

There are two ways to get metrics from your application into Mimir:

1. **Pull-based (Prometheus scraping)** - Expose a `/metrics` endpoint; otel-metrics scrapes it
2. **Push-based (OTLP)** - Use OpenTelemetry SDK to push metrics to otel-metrics-push

### Option 1: Prometheus Annotations (Pull-based, Recommended for existing apps)

Add these annotations to your pod spec:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"        # Optional: defaults to container port
    prometheus.io/path: "/metrics"    # Optional: defaults to /metrics
    prometheus.io/scheme: "http"      # Optional: http or https
```

### Option 2: Port Naming (Pull-based, Fallback)

Name your metrics port with "metrics" in the name:

```yaml
ports:
  - name: http-metrics  # or "metrics", "prom-metrics", etc.
    containerPort: 8080
```

### Option 3: OTLP Push (Push-based, Recommended for new apps with OTel SDK)

Configure your application to send OTLP metrics to the collector:

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-metrics-push.otel-metrics-push.svc.cluster.local:4317"
  - name: OTEL_EXPORTER_OTLP_PROTOCOL
    value: "grpc"
  - name: OTEL_SERVICE_NAME
    value: "my-app"
```

For HTTP instead of gRPC:

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-metrics-push.otel-metrics-push.svc.cluster.local:4318"
  - name: OTEL_EXPORTER_OTLP_PROTOCOL
    value: "http/protobuf"
```

**Language-specific examples:**

Go:
```go
import "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"

exporter, _ := otlpmetricgrpc.New(ctx,
    otlpmetricgrpc.WithEndpoint("otel-metrics-push.otel-metrics-push.svc.cluster.local:4317"),
    otlpmetricgrpc.WithInsecure(),
)
```

Python:
```python
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

exporter = OTLPMetricExporter(
    endpoint="otel-metrics-push.otel-metrics-push.svc.cluster.local:4317",
    insecure=True,
)
```

Java/Spring Boot (`application.yaml`):
```yaml
management:
  otlp:
    metrics:
      export:
        url: http://otel-metrics-push.otel-metrics-push.svc.cluster.local:4318/v1/metrics
```

### Custom Labels (Pull-based only)

Add custom labels to your metrics via annotations:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/label-cluster: "do-nyc3-prod"
    prometheus.io/label-environment: "production"
    prometheus.io/label-service: "my-app"
```

For push-based metrics, labels should be set as resource attributes in your OpenTelemetry SDK configuration.

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

See [Metrics Troubleshooting](../troubleshooting/metrics.md) for common issues and solutions.

## Related Documentation

- [Mimir Documentation](https://grafana.com/docs/mimir/latest/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics)
- [Prometheus node-exporter](https://github.com/prometheus/node_exporter)
- [Linkerd Proxy Metrics](https://linkerd.io/2-edge/reference/proxy-metrics/)
- [Strimzi Kafka with Linkerd](../how-to/strimzi-kafka-linkerd.md) - Linkerd configuration for Mimir's Kafka ingest storage
