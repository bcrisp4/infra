# Logging Architecture

This document describes the log collection and storage architecture for the cluster.

## Overview

Logs are collected by OpenTelemetry Collector DaemonSets running on each node and shipped to Loki via native OTLP protocol.

```
Node
├── /var/log/pods/*/*/*.log
│   └── filelog receiver ──► [otel-logs DaemonSet]
│                                    │
│                               [processors]
│                                    │
│                                    ▼ (mTLS via Linkerd)
│                            loki-gateway.loki/otlp
│                                    │
│                                    ▼
│                            Loki Distributed → DO Spaces

Kubernetes API
└── events.k8s.io/v1
    └── k8s_events receiver ──► [otel-events Deployment]
                                       │
                                  [processors]
                                       │
                                       ▼ (mTLS via Linkerd)
                               loki-gateway.loki/otlp
```

## Components

### otel-logs (DaemonSet)

OpenTelemetry Collector configured for log collection:

| Component | Description |
|-----------|-------------|
| **Receiver** | `filelog` - Reads container logs from `/var/log/pods` |
| **Processors** | `memory_limiter`, `k8sattributes`, `resource`, `batch` |
| **Exporter** | `otlphttp/loki` - Ships to Loki via OTLP |

**Key features:**
- Runs on each node via DaemonSet
- Enriches logs with Kubernetes metadata (namespace, pod, container, deployment, etc.)
- Adds custom labels: `cluster`, `log_source`
- Checkpoints file positions for reliable collection
- In Linkerd service mesh for mTLS

### otel-events (Deployment)

OpenTelemetry Collector configured for Kubernetes events collection:

| Component | Description |
|-----------|-------------|
| **Receiver** | `k8s_events` - Purpose-built Kubernetes events receiver |
| **Processors** | `memory_limiter`, `resource`, `resource/events`, `batch` |
| **Exporter** | `otlphttp/loki` - Ships to Loki via OTLP |

**Key features:**
- Single replica Deployment (avoids duplicate events)
- Uses semantic conventions for event attributes (e.g., `k8s_event_reason`, `k8s_object_kind`)
- Sets log body to event message (not raw JSON)
- Sets severity from event type (Normal/Warning)
- Adds `log_source: events` label to distinguish from pod logs
- Captures all cluster events (scheduling, scaling, failures, etc.)
- In Linkerd service mesh for mTLS

### Loki (Distributed Mode)

Horizontally scalable log aggregation system:

| Component | Purpose |
|-----------|---------|
| Distributor | Receives logs, distributes to ingesters |
| Ingester | Writes logs to storage, serves recent queries |
| Querier | Executes LogQL queries |
| Query Frontend | Query caching and splitting |
| Compactor | Compacts and deduplicates chunks |
| Index Gateway | Serves index queries |
| Gateway | nginx-based routing with tenant header |

**Storage:** DigitalOcean Spaces (S3-compatible)

## Labels

Logs are indexed with the following labels for efficient querying:

### Indexed Labels (Fast Filtering)

| Label | Source | Description |
|-------|--------|-------------|
| `cluster` | resource processor | Cluster identifier (`do-nyc3-prod`) |
| `log_source` | resource processor | Log source type (`pods` or `events`) |

### Structured Metadata (Queryable)

From k8sattributes processor:

| Label | Description |
|-------|-------------|
| `k8s_namespace_name` | Kubernetes namespace |
| `k8s_pod_name` | Pod name |
| `k8s_container_name` | Container name |
| `k8s_deployment_name` | Deployment name (if applicable) |
| `k8s_statefulset_name` | StatefulSet name (if applicable) |
| `k8s_daemonset_name` | DaemonSet name (if applicable) |
| `k8s_node_name` | Node running the pod |
| `container_image_name` | Container image |
| `container_image_tag` | Container image tag |
| `detected_level` | Auto-detected log level |

From k8s_events receiver (events only):

| Label | Description |
|-------|-------------|
| `k8s_event_reason` | Event reason (e.g., `Scheduled`, `Completed`, `Unhealthy`) |
| `k8s_event_count` | Event occurrence count |
| `k8s_event_name` | Event name |
| `k8s_event_uid` | Event UID |
| `k8s_event_start_time` | When the event first occurred |
| `k8s_object_kind` | Kind of involved object (Pod, Deployment, Job, etc.) |
| `k8s_object_name` | Name of involved object |
| `k8s_object_uid` | UID of involved object |
| `severity_text` | Event type: `Normal` or `Warning` |

## Multi-Tenancy

Loki uses the `X-Scope-OrgID` header for tenant isolation:

- **Tenant:** `prod`
- Header injected by otel-logs exporter and Grafana datasource
- All queries scoped to tenant automatically

## Accessing Logs

### Grafana

The `loki-do-nyc3-prod` datasource is pre-configured in Grafana with the tenant header.

### LogQL Examples

```logql
# All pod logs
{log_source="pods"}

# Logs from specific namespace
{k8s_namespace_name="argocd"}

# Error logs
{k8s_namespace_name="mimir"} |= "error"

# Logs from specific deployment
{k8s_deployment_name="grafana"}

# Combine filters
{cluster="do-nyc3-prod", k8s_namespace_name="loki"} | json | level="error"

# All cluster events
{log_source="events"}

# Events for specific namespace
{log_source="events", k8s_namespace_name="argocd"}

# Warning events
{log_source="events", severity_text="Warning"}

# Pod scheduling events
{log_source="events", k8s_event_reason="Scheduled"}

# Failed events
{log_source="events", k8s_event_reason=~"Failed.*"}
```

## Architecture Decisions

### ADR: Host/Systemd Log Collection Deferred

**Status:** Accepted (January 2026)

**Context:**

The OpenTelemetry Collector journald receiver can collect host-level logs (kubelet, containerd, systemd services) from the journal. However, it requires the `journalctl` binary which is not included in the `otel/opentelemetry-collector-contrib` container image.

Verified findings from DOKS worker nodes:
- `/var/log/syslog` does NOT exist (DOKS uses systemd-only logging)
- `/var/log/journal/` EXISTS with ~789MB of persistent journals per node
- Viable options: custom collector image, journalctl sidecar, or Fluent Bit

**Decision:**

Defer host log collection. Do not build custom images or add sidecars at this time.

**Rationale:**

1. **Low value for managed Kubernetes**: DigitalOcean handles node-level issues. Kubelet and containerd problems manifest as pod events visible via `kubectl describe pod`.

2. **Complexity vs benefit**: All solutions require either custom images (maintenance burden), sidecars (extra resources), or different tooling (Fluent Bit). The operational overhead exceeds the debugging value.

3. **Pod logs cover 90%+ of needs**: Current otel-logs deployment captures all application logs. Host logs are mainly useful for:
   - Node networking issues (rare)
   - Kubelet configuration problems (rare in managed K8s)
   - Node access auditing (SSH disabled by default on DOKS)

**Consequences:**

- Host logs (kubelet, containerd, systemd services) are not collected
- If a debugging need arises that requires host logs, implement Option 1 (custom image) from [Host Logs Collection](../tasks/host-logs-collection.md)
- Decision can be revisited if concrete debugging needs emerge

## Limitations

Current limitations based on architectural decisions above:

### No Host/Systemd Logs

Host-level logs (kubelet, containerd, systemd services) are not collected. See ADR above.

## Related Documentation

- [Query Logs](../how-to/query-logs.md) - LogQL query examples
- [Metrics Architecture](metrics-architecture.md) - Companion metrics system
