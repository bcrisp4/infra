# Tracing Architecture

This document describes the distributed tracing storage architecture for the cluster.

## Overview

Traces are stored in Grafana Tempo, a horizontally scalable distributed tracing backend. Tempo uses S3-compatible storage (DigitalOcean Spaces) for trace data and generates derived metrics that are written to Mimir.

```
Applications
└── [instrumented with OpenTelemetry]
    │
    ▼ (OTLP)
[OTel Collector] ──────────────────────────────────────────┐
    │                                                      │
    ▼ (mTLS via Linkerd)                                   │
tempo-distributor.tempo:4317 (OTLP gRPC)                   │
    │                                                      │
    ▼                                                      │
Tempo Distributed                                          │
├── Distributor ─► Ingester ─► DO Spaces                   │
├── Querier ─► Query Frontend                              │
└── Metrics Generator ─► Mimir ────────────────────────────┘
                              │
                              ▼
                      Grafana (Service Graph, RED metrics)
```

## Components

### Tempo Distributed

Horizontally scalable trace storage system:

| Component | Purpose |
|-----------|---------|
| Distributor | Receives traces, distributes to ingesters |
| Ingester | Writes traces to storage, serves recent queries |
| Querier | Executes TraceQL queries |
| Query Frontend | Query caching and splitting |
| Compactor | Compacts and deduplicates blocks |
| Gateway | nginx-based routing with tenant header |
| Metrics Generator | Derives metrics from traces |

**Storage:** DigitalOcean Spaces (S3-compatible)

### Metrics Generator

The metrics generator is an optional component that derives metrics from ingested traces. It runs as a separate deployment and writes metrics to Mimir via Prometheus remote_write.

| Processor | Metrics | Purpose |
|-----------|---------|---------|
| service-graphs | `traces_service_graph_request_total`, `traces_service_graph_request_failed_total`, `traces_service_graph_request_server_seconds_*` | Service dependency graphs showing request flow between services |
| span-metrics | `traces_spanmetrics_calls_total`, `traces_spanmetrics_latency_*`, `traces_spanmetrics_size_total` | RED metrics (Request, Error, Duration) per service and operation |

**Remote Write Configuration:**
- Endpoint: `http://mimir-gateway.mimir.svc.cluster.local/api/v1/push`
- Tenant header: `X-Scope-OrgID: prod`

## Multi-Tenancy

Tempo uses the `X-Scope-OrgID` header for tenant isolation:

- **Tenant:** `prod`
- Header injected by OTel collector exporters and Grafana datasource
- All queries scoped to tenant automatically
- Metrics generator forwards tenant header to Mimir

## Grafana Integration

The Tempo datasource is configured with links to other datasources for correlation:

### Service Map

Service graphs are visualized using metrics from the metrics generator:

- **Datasource:** `mimir-do-nyc3-prod`
- **Metrics:** `traces_service_graph_*`
- Shows service dependencies and request flow
- Click through to drill down into traces

### Trace to Logs

Jump from trace spans to correlated logs in Loki:

- **Datasource:** `loki-do-nyc3-prod`
- Filters by trace ID and span ID
- Requires logs to contain `traceID` and `spanID` fields

### Trace to Metrics

Jump from traces to related metrics in Mimir:

- **Datasource:** `mimir-do-nyc3-prod`
- Uses span attributes to filter metrics

## Storage Configuration

### S3 Backend

Tempo stores trace data in DigitalOcean Spaces:

| Setting | Value |
|---------|-------|
| Bucket | `bc4-do-nyc3-prod-tempo` |
| Endpoint | `nyc3.digitaloceanspaces.com` |
| Region | `nyc3` |

Credentials are synced from 1Password via ExternalSecret:
- 1Password item: `do-nyc3-prod-tempo-s3`
- Kubernetes secret: `s3-credentials`

### Block Storage

Tempo stores traces as blocks:

- **Block retention:** 48 hours (default)
- **Compaction:** Automatic background compaction
- **WAL:** Write-ahead log for durability

## Accessing Traces

### Grafana

The `tempo-do-nyc3-prod` datasource is pre-configured in Grafana with:
- Tenant header for multi-tenancy
- Service map linked to Mimir
- Trace-to-logs linked to Loki
- Trace-to-metrics linked to Mimir

### TraceQL Examples

```traceql
# Find traces by service name
{ resource.service.name = "my-service" }

# Find traces with errors
{ status = error }

# Find slow traces (duration > 1s)
{ duration > 1s }

# Find traces by HTTP route
{ span.http.route = "/api/users" }

# Combine filters
{ resource.service.name = "api-gateway" && status = error && duration > 500ms }

# Find traces with specific attribute
{ span.user.id = "12345" }
```

### Service Graph View

To view the service graph in Grafana:

1. Go to Explore
2. Select the Tempo datasource
3. Click "Service Graph" tab
4. Service dependencies are shown based on `traces_service_graph_*` metrics

**Requirements for service graph:**
- Traces must have `service.name` resource attribute
- Parent-child span relationships must exist (service A calling service B)
- Metrics generator must be enabled and writing to Mimir

## Component Sizing

| Component | Replicas | Memory Limit |
|-----------|----------|--------------|
| Ingester | 3 | 1Gi |
| Distributor | 2 | 512Mi |
| Querier | 2 | 512Mi |
| Query Frontend | 2 | 512Mi |
| Compactor | 1 | 2Gi |
| Gateway | 2 | 128Mi |
| Memcached | 1 | 300Mi |
| Metrics Generator | 1 | 512Mi |

## Trace Ingestion

Traces are collected by OpenTelemetry Collector DaemonSets (`otel-traces`) and shipped to Tempo via OTLP.

### Collector Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Node 1                         Node 2                      │
│  ┌─────────┐                    ┌─────────┐                 │
│  │ App Pod │──┐                 │ App Pod │──┐              │
│  └─────────┘  │                 └─────────┘  │              │
│               ▼                              ▼              │
│         ┌───────────┐                 ┌───────────┐         │
│         │otel-traces│                 │otel-traces│         │
│         │(DaemonSet)│                 │(DaemonSet)│         │
│         └─────┬─────┘                 └─────┬─────┘         │
└───────────────┼─────────────────────────────┼───────────────┘
                └──────────────┬──────────────┘
                               ▼
                    tempo-distributor.tempo.svc:4317
                               │
                               ▼
                          Tempo (S3)
```

**Key features:**
- DaemonSet mode (one collector per node)
- Service with `internalTrafficPolicy: Local` for node-local routing
- Linkerd mesh injection for mTLS

### Application Configuration

Applications send traces to the OTel collector via OTLP:

**gRPC (recommended):**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-traces.otel-traces.svc.cluster.local:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

**HTTP:**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-traces.otel-traces.svc.cluster.local:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

### Processor Pipeline

```
OTLP Receiver (gRPC/HTTP)
    │
    ▼
memory_limiter (reject if over 400MB - safety)
    │
    ▼
k8sattributes (add pod/namespace/deployment metadata)
    │
    ▼
resource (add cluster=do-nyc3-prod)
    │
    ▼
batch (group 256 spans or 10s timeout)
    │
    ▼
OTLP Exporter → tempo-distributor:4317 (X-Scope-OrgID: prod)
```

### Tempo OTLP Endpoints

The collector exports to Tempo distributor via OTLP gRPC:

| Protocol | Endpoint |
|----------|----------|
| OTLP gRPC (collector) | `tempo-distributor.tempo.svc.cluster.local:4317` |
| OTLP HTTP (via gateway) | `http://tempo-gateway.tempo.svc.cluster.local/otlp` |

All requests must include the `X-Scope-OrgID: prod` header.

### Sampling

**Current configuration:** No sampling - all traces are kept.

**Why no server-side sampling in Tempo:**
- Tempo is a storage backend, not a processing layer
- Tail sampling requires buffering complete traces before deciding
- Sampling must happen in the collector before traces reach Tempo

**Future options if volume becomes an issue:**

1. **Probabilistic (head) sampling** - Add to DaemonSet collectors (simple):
   ```yaml
   processors:
     probabilistic_sampler:
       sampling_percentage: 10
   ```

2. **Tail sampling** - Requires gateway collector layer (complex):
   - Need load balancer with trace ID affinity
   - Stateful collectors that buffer complete traces
   - Consider generating span metrics BEFORE sampling

**Note:** If tail sampling is enabled, Tempo's metrics generator won't see dropped traces, resulting in incomplete service graphs and RED metrics.

## Instrumented Cluster Apps

The following cluster applications are configured to emit traces:

| App | Status | Protocol | Configuration |
|-----|--------|----------|---------------|
| Grafana | Working | OTLP gRPC | `grafana.ini` tracing section |
| Mimir | Working | OTLP HTTP | OTel SDK env vars |
| Loki | Broken | OTLP HTTP | OTel SDK env vars + `tracing.enabled` |

### Grafana

Grafana uses native OpenTelemetry support configured via `grafana.ini`:

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml
grafana:
  grafana.ini:
    tracing.opentelemetry:
      custom_attributes: "cluster:do-nyc3-prod,service.name:grafana"
      sampler_type: const
      sampler_param: 1  # 100% sampling
    tracing.opentelemetry.otlp:
      address: otel-traces.otel-traces.svc.cluster.local:4317
      propagation: w3c
```

**Notes:**
- Uses OTLP gRPC (port 4317)
- Traces UI operations, API calls, and datasource queries

### Mimir

Mimir uses the standard OTel SDK environment variables:

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/mimir/values.yaml
mimir-distributed:
  global:
    extraEnv:
      - name: OTEL_EXPORTER_OTLP_ENDPOINT
        value: "http://otel-traces.otel-traces.svc.cluster.local:4318"
      - name: OTEL_SERVICE_NAME
        value: "mimir"
      - name: OTEL_TRACES_SAMPLER
        value: "parentbased_always_on"
      - name: OTEL_PROPAGATORS
        value: "tracecontext,baggage"
```

**Notes:**
- Uses OTLP HTTP (port 4318) - Mimir's OTel SDK does not support gRPC
- All Mimir components (ingester, distributor, querier, etc.) emit traces
- Traces query execution, ingestion, and inter-component communication

### Loki

Loki is configured for tracing but currently broken due to an upstream bug:

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/loki/values.yaml
loki:
  global:
    extraEnv:
      - name: OTEL_EXPORTER_OTLP_ENDPOINT
        value: "http://otel-traces.otel-traces.svc.cluster.local:4318"
      - name: OTEL_SERVICE_NAME
        value: "loki"
      - name: OTEL_TRACES_SAMPLER
        value: "parentbased_always_on"
      - name: OTEL_PROPAGATORS
        value: "tracecontext,baggage"
  loki:
    tracing:
      enabled: true
```

**Notes:**
- Uses OTLP HTTP (port 4318) - same as Mimir
- Requires `tracing.enabled: true` in addition to env vars
- See Known Issues section below

### Apps Not Instrumented

| App | Reason |
|-----|--------|
| ArgoCD | `--otlp-address` flag broken in v3.x ([Issue #25735](https://github.com/argoproj/argo-cd/issues/25735)) |
| cert-manager | Infrastructure operator, low value |
| cloudnative-pg | Infrastructure operator, low value |
| external-secrets | Infrastructure operator, low value |
| linkerd | Service mesh has own observability |

## Known Issues

### Loki OTel Schema Conflict (grafana/loki#19975)

**Status:** Open bug in Loki 3.6.0+

**Error:**
```
error in initializing tracing. tracing will not be enabled
err="failed to initialise trace resource: conflicting Schema URL:
https://opentelemetry.io/schemas/1.37.0 and https://opentelemetry.io/schemas/1.34.0"
```

**Cause:** Loki 3.6.0 has conflicting OTel SDK schema versions in its dependencies.

**Workaround:** Downgrade to Loki 3.5.7 (Helm chart loki 6.46.0) if tracing is required.

**Tracking:** [grafana/loki#19975](https://github.com/grafana/loki/issues/19975)

## Architecture Decisions

### ADR: Metrics Generator for Service Graphs

**Status:** Accepted (January 2026)

**Context:**

Grafana's service graph feature can be powered by:
1. **Tempo metrics generator** - derives metrics from traces
2. **Application-level metrics** - applications emit service graph metrics directly
3. **Grafana Agent/OTel Collector** - generate metrics at collection time

**Decision:**

Use Tempo's built-in metrics generator.

**Rationale:**

1. **Centralized processing:** All traces flow through Tempo anyway, so generating metrics here avoids duplicate processing at collectors.

2. **Accurate relationship detection:** The metrics generator analyzes complete traces to identify service-to-service calls, which is more accurate than edge-based sampling at collectors.

3. **Simpler collector config:** Collectors only need to export traces, not also generate service graph metrics.

4. **Consistent tenant handling:** The metrics generator automatically forwards the tenant header to Mimir.

**Consequences:**

- Metrics are delayed slightly (processing happens after trace ingestion)
- Metrics generator requires additional resources (1 replica, 512Mi memory)
- All RED metrics come from traces, not from application instrumentation

## Related Documentation

- [Logging Architecture](logging-architecture.md) - Companion logging system
- [Metrics Architecture](metrics-architecture.md) - Companion metrics system
- [Grafana Datasources](grafana-datasources.md) - Datasource configuration
