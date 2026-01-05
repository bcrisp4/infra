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
tempo-gateway.tempo (OTLP endpoint)                        │
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

**Note:** Trace ingestion (OTel collectors sending traces to Tempo) is configured separately from this storage architecture. See the OTel collector configuration for trace export settings.

### OTLP Endpoints

Tempo accepts traces via OTLP:

| Protocol | Endpoint |
|----------|----------|
| OTLP HTTP | `http://tempo-gateway.tempo.svc.cluster.local/otlp` |
| OTLP gRPC | `tempo-distributor.tempo.svc.cluster.local:4317` |

All requests must include the `X-Scope-OrgID: prod` header.

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
