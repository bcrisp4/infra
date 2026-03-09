# Metrics Architecture

This document describes the metrics collection, storage, and long-term retention architecture for the cluster.

## Overview

Metrics are collected by Prometheus (via kube-prometheus-stack) and stored locally with 31-day retention. A Thanos sidecar uploads Prometheus TSDB blocks to S3 object storage. Thanos components provide long-term querying with automatic downsampling.

```
                         ┌─────────────────┐
                         │   Grafana        │
                         │                  │
                         │  prometheus-*    │  (recent data, 31d)
                         │  thanos-*        │  (historical data, up to 3y)
                         └──────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
          ┌──────────────┐       ┌──────────────────┐
          │  Prometheus   │       │  Thanos Query     │
          │  (prometheus) │       │  (thanos)         │
          │  port 9090    │       │  port 10902       │
          └──────┬───────┘       └──────┬────────────┘
                 │                      │
          ┌──────┴───────┐    ┌────────┴─────────┐
          │ Thanos        │    │                  │
          │ Sidecar       │    ▼                  ▼
          │ (in-pod)      │  Prometheus       Thanos Store
          └──────┬───────┘  Sidecar           Gateway
                 │          (live data)       (S3 data)
                 ▼
          ┌──────────────┐       ┌──────────────────┐
          │  DO Spaces    │◄─────│  Thanos Compactor  │
          │  (S3)         │      │  (downsamples,     │
          │               │      │   enforces retention│)
          └──────────────┘       └──────────────────┘
```

## Components

### Prometheus (kube-prometheus-stack)

Deployed in the `prometheus` namespace via the kube-prometheus-stack umbrella chart.

| Component | Description |
|-----------|-------------|
| Prometheus | Metric collection and short-term storage (31-day retention) |
| Alertmanager | Alert routing and notification |
| kube-state-metrics | Kubernetes object metrics |
| node-exporter | Node-level hardware and OS metrics |
| Thanos sidecar | Uploads 2-hour TSDB blocks to S3 |

Prometheus scrapes metrics via ServiceMonitors, PodMonitors, and annotation-based discovery.

### Thanos Sidecar

Runs as a sidecar container alongside Prometheus. It:
- Uploads completed 2-hour TSDB blocks to S3 object storage
- Exposes a Store API (gRPC on port 10901) for live data queries from Thanos Query

The sidecar is configured via kube-prometheus-stack's `prometheus.prometheusSpec.thanos` values with the `thanos-objstore-config` secret.

### Thanos Store Gateway

Deployed in the `thanos` namespace as a StatefulSet.

Serves historical metric blocks from S3 object storage via the Store API (gRPC). It caches block metadata and index headers locally for performance.

### Thanos Query

Deployed in the `thanos` namespace as a Deployment.

Provides a unified PromQL endpoint that fans out queries to:
- **Prometheus Thanos sidecar** -- for recent/live data
- **Thanos Store Gateway** -- for historical data from S3

Deduplicates overlapping data from multiple sources automatically.

### Thanos Compactor

Deployed in the `thanos` namespace as a StatefulSet.

Runs continuously (`--wait` mode) and performs:
- **Compaction** -- merges small TSDB blocks into larger ones for query efficiency
- **Downsampling** -- creates 5-minute and 1-hour resolution summaries of raw data
- **Retention enforcement** -- deletes blocks older than configured retention periods

## Retention Policy

| Resolution | Retention | Use case |
|------------|-----------|----------|
| Raw | 90 days | Recent detailed analysis |
| 5-minute | 365 days | Medium-term trend analysis |
| 1-hour | 1095 days (3 years) | Long-term capacity planning |

Prometheus local retention is 31 days. Beyond that window, queries are served from S3 via the Store Gateway.

## Object Storage

Thanos blocks are stored in a DigitalOcean Spaces bucket (`bc4-do-nyc3-prod-thanos`).

Credentials are managed via ExternalSecret from 1Password:
- Prometheus namespace: `thanos-objstore-config` secret (for the sidecar)
- Thanos namespace: `thanos-objstore-config` secret (for Store Gateway and Compactor)

Both secrets reference the same 1Password item (`do-nyc3-prod-thanos-s3`) but are created independently in their respective namespaces.

## Grafana Datasources

| Datasource | Backend | Use case |
|------------|---------|----------|
| `prometheus-do-nyc3-prod` | Prometheus (port 9090) | Default. Recent metrics within 31-day window |
| `thanos-do-nyc3-prod` | Thanos Query (port 10902) | Historical queries beyond 31 days, cross-source queries |

The Thanos datasource uses `max_source_resolution=auto` to automatically select the best resolution (raw, 5m, or 1h) based on the query time range. See [Grafana Datasources](grafana-datasources.md) for configuration details.

## Service URLs

| Service | URL |
|---------|-----|
| Prometheus | `http://prometheus-kube-prometheus-prometheus.prometheus.svc.cluster.local:9090` |
| Alertmanager | `http://prometheus-kube-prometheus-alertmanager.prometheus.svc.cluster.local:9093` |
| Thanos Query (HTTP) | `http://thanos-query.thanos.svc.cluster.local:10902` |
| Thanos Store (gRPC) | `thanos-store.thanos.svc.cluster.local:10901` |
| Prometheus Sidecar (gRPC) | `prometheus-kube-prometheus-prometheus.prometheus.svc.cluster.local:10901` |

## Related Documentation

- [Grafana Datasources](grafana-datasources.md) - Datasource provisioning
- [Logging Architecture](logging-architecture.md) - Companion logging system
- [Metrics Troubleshooting](../troubleshooting/metrics.md) - Debugging metrics issues
