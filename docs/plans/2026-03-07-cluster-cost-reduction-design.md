# Cluster Cost Reduction Design

Date: 2026-03-07

## Goal

Reduce do-nyc3-prod monthly DigitalOcean bill from ~$500 to ~$200 by removing unused apps, replacing over-engineered components with simpler alternatives, and downsizing the node pool.

## Current State

- **Nodes**: 4 x s-8vcpu-16gb ($96/mo each = $384 compute)
- **Memory**: 31.28 GiB used of 53.31 GiB allocatable (59%)
- **CPU**: 6.50 cores used of 31.52 allocatable (21%)
- **Pods**: 170 across 26 namespaces
- **Biggest consumer**: Mimir at 14.50 GiB (46% of cluster memory), 35 pods

## Changes

### Phase 1: Remove Apps

Delete the following apps (both `kubernetes/apps/{app}/` and `kubernetes/clusters/do-nyc3-prod/apps/{app}/`):

| App | Memory Freed | Pods Freed | Reason |
|-----|-------------|------------|--------|
| mimir | 14.50 GiB | 35 | Replaced by Prometheus |
| strimzi-kafka-operator | 0.36 GiB | 1 | Only needed for Mimir's Kafka |
| tempo | 1.95 GiB | 15 | Not needed |
| otel-ebpf | 2.43 GiB | 4 | Not needed |
| otel-traces | 0.42 GiB | 4 | No traces backend |
| otel-metrics | 1.84 GiB | 4 | Prometheus scrapes natively |
| otel-metrics-push | 0.35 GiB | 4 | Main consumer (otel-ebpf) removed |
| paperless-ngx | 0.75 GiB | 5 | Not needed |
| mlflow | 0.36 GiB | 2 | Not needed |
| n8n | 0.36 GiB | 2 | Not needed |

**Total freed**: ~23.3 GiB memory, ~76 pods

Also remove standalone `kube-state-metrics` and `node-exporter` apps -- kube-prometheus-stack will manage these.

### Phase 2: Deploy Prometheus

Deploy kube-prometheus-stack as a new app following the umbrella chart pattern:

- **Chart**: prometheus-community/kube-prometheus-stack
- **Namespace**: prometheus
- **Configuration**:
  - Disable built-in Grafana (we have our own)
  - Enable kube-state-metrics (replaces standalone)
  - Enable node-exporter (replaces standalone)
  - Configure Kubernetes service discovery scrape targets matching what otel-metrics was scraping
  - Include Linkerd proxy scrape config (port 4191)
  - Set retention to 15d with local PV storage (50Gi)
  - Minimal resource requests: 500m CPU, 1Gi memory

### Phase 3: Reconfigure Dependencies

- **Grafana**: Update metrics datasource from Mimir (type: prometheus, UID: PDFDDA34E6E7D2823) to point at the new Prometheus server
- **linkerd-viz**: Reconfigure to query Prometheus instead of Mimir's tenant proxy
- **Alerting**: Migrate any Mimir recording/alerting rules to Prometheus

### Phase 4: Scale Down Remaining Apps

**Loki**: Switch from distributed to SimpleScalable mode
- 3 target paths: read (1 pod), write (1 pod), backend (1 pod)
- Keep existing S3 object storage config
- Drop all caches (or keep 1 small results cache)
- Estimated: 21 pods -> 3-5 pods, ~3.12 GiB -> ~1.5 GiB

**Grafana**:
- Drop replicas from 2 to 1
- Drop PostgreSQL instances from 2 to 1
- Consider removing image renderer if not actively used

**Miniflux**:
- Drop PostgreSQL instances from 2 to 1

**ArgoCD**:
- Review and right-size resource requests

**cert-manager**:
- Currently 8 pods and 0.36 GiB -- review if all components are needed

### Phase 5: Resize Node Pool

After all app changes are stable:

- **New pool**: 3 x s-4vcpu-8gb ($48/mo each = $144 compute)
- **Allocatable**: ~10.5 cores CPU, ~20 GiB memory
- **Estimated usage**: ~3 cores CPU, ~7-8 GiB memory
- **Headroom**: ~60% memory free, ~70% CPU free

Migration approach: Add new node pool, cordon/drain old nodes, remove old pool.

## Estimated Post-Change State

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Memory usage | 31.28 GiB | ~7-8 GiB | -74% |
| CPU usage | 6.50 cores | ~3 cores | -54% |
| Pods | 170 | ~75-80 | -55% |
| Node count | 4 | 3 | -1 |
| Node size | s-8vcpu-16gb | s-4vcpu-8gb | -50% RAM |
| Compute cost | $384/mo | $144/mo | -63% |
| **Total bill** | **~$500/mo** | **~$195/mo** | **-61%** |

## Trade-offs

- **No distributed tracing**: Tempo and trace pipeline removed entirely
- **Metrics history resets**: Prometheus starts fresh; Mimir data remains in S3 bucket but is not queryable
- **No HA**: Single replicas across the board; brief downtime during node maintenance events
- **Less metrics retention**: Prometheus 15d local storage vs Mimir's unlimited S3 (adjustable)
- **Linkerd kept for now**: Still adds sidecar overhead but will be smaller with fewer pods (~75 vs 170)

## What We Keep

- Linkerd service mesh (evaluate later)
- Full logging pipeline (Loki + otel-logs + otel-events)
- Metrics pipeline (Prometheus + Grafana)
- GitOps (ArgoCD)
- Secret management (external-secrets + 1Password)
- TLS (cert-manager + trust-manager)
- Secure access (Tailscale operator)
- RSS reader (Miniflux)
- Grafana MCP server

## Measurement

Collect before/after metrics using Prometheus queries:
- `sum by (namespace) (kube_pod_container_resource_requests{resource="cpu"})`
- `sum by (namespace) (kube_pod_container_resource_requests{resource="memory"})`
- `sum by (namespace) (rate(container_cpu_usage_seconds_total[5m]))`
- `sum by (namespace) (container_memory_working_set_bytes)`
- `count by (namespace) (kube_pod_info)`
- `sum(kube_node_status_allocatable{resource="cpu|memory"})`

Capture snapshots before starting and after each phase completes.
