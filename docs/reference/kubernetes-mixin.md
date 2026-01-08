# Kubernetes Mixin

The kubernetes-mixin provides pre-built Grafana dashboards and Prometheus recording rules for monitoring Kubernetes clusters. This document describes the deployment and configuration in this infrastructure.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Grafana                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Kubernetes Folder (15 dashboards)                 │    │
│  │  - Cluster/Namespace/Node/Pod/Workload Resources                    │    │
│  │  - Kubelet, API Server, Proxy                                       │    │
│  │  - Networking (cluster/namespace/pod/workload)                      │    │
│  │  - Persistent Volume Usage                                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │ PromQL queries                                │
│                              │ (using recording rules)                       │
│                              ▼                                               │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Mimir                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Recording Rules (16 groups)                       │    │
│  │  namespace: kubernetes-mixin                                         │    │
│  │  - Pre-aggregates expensive queries                                  │    │
│  │  - Improves dashboard performance                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▲ Queries raw metrics                           │
│                              │                                               │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│                          otel-metrics (DaemonSet)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    metric_relabel_configs                            │    │
│  │  Renames kube-state-metrics labels:                                  │    │
│  │  - exported_namespace → namespace                                    │    │
│  │  - exported_pod → pod                                               │    │
│  │  - exported_container → container                                    │    │
│  │  - exported_node → node                                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▲ Scrapes                                       │
│                              │                                               │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│                         kube-state-metrics                                   │
│  Exposes Kubernetes object state as Prometheus metrics                       │
│  Uses exported_* prefix for resource labels                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Dashboards

15 dashboards deployed via Grafana sidecar ConfigMap to the "Kubernetes" folder.

| Dashboard | Description |
|-----------|-------------|
| **k8s-resources-cluster** | Cluster-wide CPU, memory, and network overview |
| **k8s-resources-namespace** | Per-namespace resource usage breakdown |
| **k8s-resources-node** | Node-level resource utilization |
| **k8s-resources-pod** | Pod resource requests, limits, and usage |
| **k8s-resources-workload** | Workload (deployment/statefulset/daemonset) resources |
| **k8s-resources-workloads-namespace** | Workloads grouped by namespace |
| **kubelet** | Kubelet performance and operation metrics |
| **apiserver** | Kubernetes API server request rates, latencies, errors |
| **proxy** | kube-proxy metrics |
| **persistentvolumesusage** | PVC capacity and usage |
| **cluster-total** | Cluster-wide networking |
| **namespace-by-pod** | Namespace networking by pod |
| **namespace-by-workload** | Namespace networking by workload |
| **pod-total** | Pod networking |
| **workload-total** | Workload networking |

**Excluded dashboards** (not applicable to DOKS):
- Windows dashboards - DOKS uses Linux nodes only
- scheduler.json - Control plane managed by DigitalOcean
- controller-manager.json - Control plane managed by DigitalOcean

### Recording Rules

16 rule groups pre-aggregate expensive queries for dashboard performance.

| Rule Group | Purpose |
|------------|---------|
| **kube-apiserver-availability.rules** | API server availability SLIs |
| **kube-apiserver-burnrate.rules** | API server error budget burn rate |
| **kube-apiserver-histogram.rules** | API server latency percentiles |
| **k8s.rules.container_cpu_usage_seconds_total** | Container CPU aggregations |
| **k8s.rules.container_memory_working_set_bytes** | Container memory aggregations |
| **k8s.rules.container_memory_rss** | Container RSS memory |
| **k8s.rules.container_memory_cache** | Container cache memory |
| **k8s.rules.container_memory_swap** | Container swap memory |
| **k8s.rules.container_memory_requests** | Memory requests by namespace/workload |
| **k8s.rules.container_memory_limits** | Memory limits by namespace/workload |
| **k8s.rules.container_cpu_requests** | CPU requests by namespace/workload |
| **k8s.rules.container_cpu_limits** | CPU limits by namespace/workload |
| **k8s.rules.pod_owner** | Pod ownership mapping |
| **kube-scheduler.rules** | Scheduler metrics (limited in DOKS) |
| **node.rules** | Node-level aggregations |
| **kubelet.rules** | Kubelet aggregations |

### Metric Relabeling

The otel-metrics collector applies two types of metric relabeling:

#### 1. Cluster Label (`k8s_cluster`)

All scraped metrics get a `k8s_cluster` label to identify the Kubernetes cluster. We use `k8s_cluster` instead of `cluster` to avoid collision with CloudNativePG's `cluster` label (which identifies database clusters).

```yaml
metric_relabel_configs:
  - target_label: k8s_cluster
    replacement: "do-nyc3-prod"
    action: replace
```

The kubernetes-mixin dashboards and recording rules have been modified to use `k8s_cluster` instead of the standard `cluster` label.

#### 2. kube-state-metrics Label Renaming

kube-state-metrics uses `exported_*` prefix labels to distinguish between:
- Labels describing the KSM pod itself (`namespace`, `pod`)
- Labels describing the monitored resource (`exported_namespace`, `exported_pod`)

kubernetes-mixin expects standard labels. The otel-metrics collector renames these at scrape time:

```yaml
metric_relabel_configs:
  - source_labels: [job, exported_namespace]
    regex: ".*/kube-state-metrics;(.+)"
    target_label: namespace
    replacement: "$1"
    action: replace
  # ... similar for exported_pod, exported_container, exported_node
  - regex: "exported_(namespace|pod|container|node)"
    action: labeldrop
```

**Breaking change**: Any existing queries using `exported_*` labels will need updating after this relabeling is deployed.

## File Locations

| File | Purpose |
|------|---------|
| `scripts/update-kubernetes-mixin.sh` | Update script for new mixin versions |
| `kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml` | Recording rules (Mimir format) |
| `kubernetes/apps/grafana/dashboards/kubernetes-mixin/*.json` | Dashboard JSON files |
| `kubernetes/apps/grafana/templates/kubernetes-mixin-dashboards-configmap.yaml` | Sidecar ConfigMap template |
| `kubernetes/clusters/do-nyc3-prod/apps/otel-metrics/values.yaml` | Metric relabel config |

## Key Recording Rule Metrics

These pre-aggregated metrics are used by the dashboards:

```promql
# CPU requests by namespace
namespace_cpu:kube_pod_container_resource_requests:sum

# Memory requests by namespace
namespace_memory:kube_pod_container_resource_requests:sum

# CPU usage by namespace/workload
namespace_workload_pod:kube_pod_owner:relabel

# Container resource aggregations
node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate
node_namespace_pod_container:container_memory_working_set_bytes

# API server availability
apiserver_request:availability30d
```

## Mimir Ruler Storage

Recording rules are stored in Mimir's ruler via S3 (DO Spaces). Rules are uploaded using mimirtool, not stored as local files in the ruler pod.

```bash
# Upload rules to Mimir
kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &
mimirtool rules sync \
  --address=http://localhost:8080 \
  --id=prod \
  kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml
```

Rules are stored under the `kubernetes-mixin` namespace (Mimir concept, not K8s namespace) for the `prod` tenant.

## Version

Current version: **1.4.1**

Source: https://github.com/kubernetes-monitoring/kubernetes-mixin

## Related Documentation

- [Metrics Architecture](metrics-architecture.md) - Overall metrics infrastructure
- [How to Update kubernetes-mixin](../how-to/update-kubernetes-mixin.md) - Update procedure
- [Mimir Tenancy](mimir-tenancy.md) - Multi-tenant configuration
- [Future: GitOps Rule Automation](../tasks/mimir-rules-gitops.md) - Planned automation
