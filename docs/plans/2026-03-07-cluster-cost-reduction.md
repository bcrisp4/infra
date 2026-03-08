# Cluster Cost Reduction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce do-nyc3-prod monthly bill from ~$500 to ~$195 by removing unused apps, replacing Mimir with Prometheus, simplifying Loki, and downsizing nodes.

**Architecture:** Replace the distributed Mimir metrics backend (35 pods, 14.5 GiB) with kube-prometheus-stack (1-2 pods, ~1 GiB). Switch Loki from distributed mode (21 pods) to SimpleScalable (3-5 pods). Remove Tempo, otel-ebpf, and several unused apps. Downsize from 4x s-8vcpu-16gb nodes to 3x s-4vcpu-8gb.

**Tech Stack:** Helm umbrella charts, ArgoCD GitOps, Terraform (TFC remote execution), DigitalOcean Kubernetes

**Design doc:** `docs/plans/2026-03-07-cluster-cost-reduction-design.md`

---

### Task 1: Capture Baseline Metrics

**Purpose:** Record current resource usage so we can measure the impact of changes.

**Step 1: Query current resource metrics**

Use the Grafana MCP tool `query_prometheus` with datasource UID `PDFDDA34E6E7D2823` to run these queries and save results:

```promql
# Per-namespace memory usage
sum by (namespace) (container_memory_working_set_bytes{container!=""})

# Per-namespace CPU usage
sum by (namespace) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))

# Per-namespace memory requests
sum by (namespace) (kube_pod_container_resource_requests{resource="memory"})

# Per-namespace CPU requests
sum by (namespace) (kube_pod_container_resource_requests{resource="cpu"})

# Total node allocatable
sum by (resource) (kube_node_status_allocatable{resource=~"cpu|memory"})

# Pod count per namespace
count by (namespace) (kube_pod_info)
```

Save results to `docs/plans/2026-03-07-baseline-metrics.md` as a markdown table.

**Step 2: Commit baseline**

```bash
git add docs/plans/2026-03-07-baseline-metrics.md
git commit -m "Record baseline metrics before cost reduction"
```

---

### Task 2: Deploy kube-prometheus-stack

**Purpose:** Deploy Prometheus as the replacement metrics backend before removing Mimir, so we don't have a gap in metrics collection.

**Files:**
- Create: `kubernetes/apps/prometheus/Chart.yaml`
- Create: `kubernetes/apps/prometheus/values.yaml`
- Create: `kubernetes/clusters/do-nyc3-prod/apps/prometheus/config.yaml`
- Create: `kubernetes/clusters/do-nyc3-prod/apps/prometheus/values.yaml`

**Step 1: Create the umbrella chart**

Create `kubernetes/apps/prometheus/Chart.yaml`:

```yaml
apiVersion: v2
name: prometheus
description: Prometheus monitoring stack via kube-prometheus-stack
type: application
version: 1.0.0

dependencies:
  - name: kube-prometheus-stack
    version: "~80.13"
    repository: https://prometheus-community.github.io/helm-charts
```

**Step 2: Create base values**

Create `kubernetes/apps/prometheus/values.yaml`:

```yaml
# Base values for kube-prometheus-stack
kube-prometheus-stack:
  # Disable built-in Grafana - we have our own
  grafana:
    enabled: false

  # Alertmanager - single replica, minimal resources
  alertmanager:
    alertmanagerSpec:
      replicas: 1
      resources:
        requests:
          cpu: 10m
          memory: 64Mi
        limits:
          memory: 128Mi

  # Prometheus server configuration
  prometheus:
    prometheusSpec:
      replicas: 1
      retention: 15d
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          memory: 2Gi
      storageSpec:
        volumeClaimTemplate:
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 50Gi
      # Scrape all ServiceMonitors/PodMonitors regardless of labels
      serviceMonitorSelectorNilUsesHelmValues: false
      podMonitorSelectorNilUsesHelmValues: false
      ruleSelectorNilUsesHelmValues: false
      # Additional scrape configs for annotation-based discovery and Linkerd
      additionalScrapeConfigs:
        # Scrape pods with prometheus.io/scrape: "true" annotation
        - job_name: kubernetes-pods
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: "true"
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scheme]
              action: replace
              target_label: __scheme__
              regex: (https?)
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
              action: replace
              target_label: __metrics_path__
              regex: (.+)
            - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
              action: replace
              regex: (.+?)(?::\d+)?;(\d+)
              replacement: $1:$2
              target_label: __address__
            - action: labelmap
              regex: __meta_kubernetes_pod_label_(.+)
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: pod
        # Scrape Linkerd proxy metrics on port 4191
        - job_name: linkerd-proxy
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_container_name]
              action: keep
              regex: linkerd-proxy
            - source_labels: [__meta_kubernetes_pod_container_port_name]
              action: keep
              regex: linkerd-admin
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: pod
          # Linkerd proxies expose metrics on the admin port
          metrics_path: /metrics

  # kube-state-metrics - replaces our standalone app
  kube-state-metrics:
    resources:
      requests:
        cpu: 10m
        memory: 64Mi
      limits:
        memory: 128Mi

  # node-exporter - replaces our standalone app
  prometheus-node-exporter:
    resources:
      requests:
        cpu: 50m
        memory: 32Mi
      limits:
        memory: 64Mi
```

**Step 3: Create cluster config**

Create `kubernetes/clusters/do-nyc3-prod/apps/prometheus/config.yaml`:

```yaml
name: prometheus
namespaceAnnotations:
  linkerd.io/inject: enabled
```

Create `kubernetes/clusters/do-nyc3-prod/apps/prometheus/values.yaml`:

```yaml
# Cluster-specific values for do-nyc3-prod
# Base values are inherited from kubernetes/apps/prometheus/values.yaml
```

**Step 4: Build chart dependencies**

Run: `cd kubernetes/apps/prometheus && helm dependency update`

Expected: Chart.lock created, charts/ directory with the kube-prometheus-stack tgz.

**Step 5: Commit**

```bash
git add kubernetes/apps/prometheus kubernetes/clusters/do-nyc3-prod/apps/prometheus
git commit -m "Deploy kube-prometheus-stack to replace Mimir"
```

**Step 6: Push and verify deployment**

Push to trigger ArgoCD sync. Verify:
- ArgoCD creates the prometheus Application
- Prometheus pod is running: `kubectl get pods -n prometheus`
- Prometheus is scraping targets: check the Prometheus UI or query `up` metric

---

### Task 3: Reconfigure Grafana

**Purpose:** Point Grafana at the new Prometheus datasource, remove Tempo datasource, remove tracing config, scale down to 1 replica and 1 PG instance.

**Files:**
- Modify: `kubernetes/apps/grafana/values.yaml` (datasource definitions)
- Modify: `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml` (cluster overrides)

**Step 1: Update base datasources**

In `kubernetes/apps/grafana/values.yaml`, replace the datasources section. Remove the mimir-do-nyc3-prod and tempo-do-nyc3-prod datasources. Add a prometheus datasource. Keep loki-do-nyc3-prod.

The datasource URL for Prometheus will be:
`http://prometheus-kube-prometheus-stack-prometheus.prometheus.svc.cluster.local:9090`

Note: The service name comes from kube-prometheus-stack's default naming with release name "prometheus". Verify with `kubectl get svc -n prometheus` after Task 2 completes. Adjust the URL if the service name differs.

New datasources section:

```yaml
datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: prometheus-do-nyc3-prod
        type: prometheus
        access: proxy
        url: http://prometheus-kube-prometheus-stack-prometheus.prometheus.svc.cluster.local:9090
        editable: false
        isDefault: true
        jsonData:
          timeInterval: 30s

      - name: loki-do-nyc3-prod
        type: loki
        access: proxy
        url: http://loki-gateway.loki.svc.cluster.local
        editable: false
        jsonData:
          timeout: 60
          maxLines: 1000
          httpHeaderName1: X-Scope-OrgID
        secureJsonData:
          httpHeaderValue1: prod
```

**Step 2: Update cluster values**

In `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml`, make these changes:

1. Drop `database.instances` from 2 to 1
2. Drop `grafana.replicas` from 2 to 1
3. Remove `grafana.headlessService: true` (not needed with 1 replica)
4. Remove the `grafana.deploymentStrategy` section (not needed with 1 replica)
5. Remove the `grafana.podDisruptionBudget` section (not needed with 1 replica)
6. Remove the `grafana.extraEnvs` POD_IP section (not needed without HA alerting)
7. Remove the `grafana.grafana.ini.unified_alerting` HA config (ha_listen_address, ha_advertise_address, ha_peers) -- keep unified_alerting.enabled: true
8. Remove the `grafana.grafana.ini.tracing.opentelemetry` and `grafana.grafana.ini.tracing.opentelemetry.otlp` sections (otel-traces is being removed)
9. Replace the datasources section with the new one from Step 1 (prometheus instead of mimir, remove tempo)
10. Consider removing the image renderer if not actively used (saves ~256Mi memory). If unsure, keep it.

**Step 3: Commit**

```bash
git add kubernetes/apps/grafana/values.yaml kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml
git commit -m "Reconfigure Grafana for Prometheus, scale down to 1 replica"
```

---

### Task 4: Reconfigure linkerd-viz

**Purpose:** Point linkerd-viz at the new Prometheus instead of Mimir.

**Files:**
- Modify: `kubernetes/clusters/do-nyc3-prod/apps/linkerd-viz/values.yaml`

**Step 1: Update linkerd-viz cluster values**

Replace the contents of `kubernetes/clusters/do-nyc3-prod/apps/linkerd-viz/values.yaml`:

```yaml
# Linkerd Viz for do-nyc3-prod
#
# Uses kube-prometheus-stack Prometheus for metrics.

linkerd-viz:
  # Disable built-in Prometheus - using external Prometheus
  prometheus:
    enabled: false

  # Point to kube-prometheus-stack Prometheus
  prometheusUrl: http://prometheus-kube-prometheus-stack-prometheus.prometheus.svc.cluster.local:9090
```

Note: Verify the Prometheus service name from Task 2 before applying. Adjust URL if needed.

**Step 2: Commit**

```bash
git add kubernetes/clusters/do-nyc3-prod/apps/linkerd-viz/values.yaml
git commit -m "Point linkerd-viz at kube-prometheus-stack Prometheus"
```

---

### Task 5: Remove Apps

**Purpose:** Delete all apps that are no longer needed. ArgoCD will auto-prune the resources when config.yaml files are removed.

**Apps to remove (12 total):**
- mimir
- strimzi-kafka-operator
- tempo
- otel-ebpf
- otel-traces
- otel-metrics
- otel-metrics-push
- paperless-ngx
- mlflow
- n8n
- kube-state-metrics (now managed by kube-prometheus-stack)
- node-exporter (now managed by kube-prometheus-stack)

**Step 1: Remove cluster configs**

Delete these directories (each contains config.yaml and values.yaml):

```
kubernetes/clusters/do-nyc3-prod/apps/mimir/
kubernetes/clusters/do-nyc3-prod/apps/strimzi-kafka-operator/
kubernetes/clusters/do-nyc3-prod/apps/tempo/
kubernetes/clusters/do-nyc3-prod/apps/otel-ebpf/
kubernetes/clusters/do-nyc3-prod/apps/otel-traces/
kubernetes/clusters/do-nyc3-prod/apps/otel-metrics/
kubernetes/clusters/do-nyc3-prod/apps/otel-metrics-push/
kubernetes/clusters/do-nyc3-prod/apps/paperless-ngx/
kubernetes/clusters/do-nyc3-prod/apps/mlflow/
kubernetes/clusters/do-nyc3-prod/apps/n8n/
kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics/
kubernetes/clusters/do-nyc3-prod/apps/node-exporter/
```

**Step 2: Remove app chart directories**

Delete these directories:

```
kubernetes/apps/mimir/
kubernetes/apps/strimzi-kafka-operator/
kubernetes/apps/tempo/
kubernetes/apps/otel-ebpf/
kubernetes/apps/otel-traces/
kubernetes/apps/otel-metrics/
kubernetes/apps/otel-metrics-push/
kubernetes/apps/paperless-ngx/
kubernetes/apps/mlflow/
kubernetes/apps/n8n/
kubernetes/apps/kube-state-metrics/
kubernetes/apps/node-exporter/
```

**Step 3: Commit**

```bash
git add -A kubernetes/clusters/do-nyc3-prod/apps/ kubernetes/apps/
git commit -m "Remove mimir, tempo, and 10 other apps for cost reduction

Remove: mimir, strimzi-kafka-operator, tempo, otel-ebpf, otel-traces,
otel-metrics, otel-metrics-push, paperless-ngx, mlflow, n8n,
kube-state-metrics, node-exporter.

kube-state-metrics and node-exporter are now managed by
kube-prometheus-stack."
```

**Step 4: Push and verify**

Push to trigger ArgoCD sync. Monitor ArgoCD to confirm all 12 Applications are deleted and their resources pruned. This may take several minutes.

Check: `kubectl get ns` -- the removed namespaces should be terminating or gone.

Important: Mimir PVs and Kafka PVs may need manual cleanup. Check with:
```bash
kubectl get pv | grep -E 'mimir|strimzi|kafka'
```

---

### Task 6: Migrate Loki to SimpleScalable

**Purpose:** Switch Loki from distributed mode (21 pods, 3.12 GiB) to SimpleScalable mode (3-5 pods, ~1.5 GiB).

**Files:**
- Modify: `kubernetes/apps/loki/values.yaml`
- Modify: `kubernetes/clusters/do-nyc3-prod/apps/loki/values.yaml`

**Step 1: Update base values**

In `kubernetes/apps/loki/values.yaml`, change `deploymentMode` from `Distributed` to `SimpleScalable`.

**Step 2: Rewrite cluster values for SimpleScalable**

Replace `kubernetes/clusters/do-nyc3-prod/apps/loki/values.yaml` with SimpleScalable configuration. Key changes:

1. Change `deploymentMode` to `SimpleScalable` (if not already set in base)
2. Set `write.replicas: 1` (handles ingestion and distribution)
3. Set `read.replicas: 1` (handles queries)
4. Set `backend.replicas: 1` (handles compaction, index gateway, ruler)
5. Remove all distributed component configs (ingester, querier, queryFrontend, queryScheduler, distributor, compactor, indexGateway, patternIngester, gateway, and all cache configs)
6. Keep the S3 storage config, schema config, retention config, and limits_config
7. Remove the tracing config (OTEL_EXPORTER_OTLP_ENDPOINT pointing to otel-traces) since Tempo is gone
8. Keep the loki canary (useful for monitoring)
9. Disable bloom components (already disabled)

New cluster values (preserve S3 and retention settings from current config):

```yaml
# Loki for do-nyc3-prod - SimpleScalable mode
# Uses DO Spaces for S3-compatible storage

externalSecret:
  enabled: true
  itemName: do-nyc3-prod-loki-s3

loki:
  deploymentMode: SimpleScalable

  loki:
    pattern_ingester:
      enabled: true
    compactor:
      retention_enabled: true
      delete_request_store: s3
    limits_config:
      allow_structured_metadata: true
      volume_enabled: true
      retention_period: 2d
      otlp_config:
        resource_attributes:
          attributes_config:
            - action: index_label
              attributes:
                - cluster
                - log_source
                - service_name
    storage:
      bucketNames:
        chunks: ${S3_BUCKET}
        ruler: ${S3_BUCKET}
        admin: ${S3_BUCKET}
      s3:
        endpoint: ${S3_ENDPOINT}
        accessKeyId: ${AWS_ACCESS_KEY_ID}
        secretAccessKey: ${AWS_SECRET_ACCESS_KEY}
    runtimeConfig:
      overrides:
        prod:
          retention_period: 28d

  # SimpleScalable targets
  write:
    replicas: 1
    resources:
      requests:
        cpu: 100m
        memory: 512Mi
      limits:
        memory: 1Gi

  read:
    replicas: 1
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        memory: 512Mi

  backend:
    replicas: 1
    resources:
      requests:
        cpu: 100m
        memory: 512Mi
      limits:
        memory: 1Gi

  gateway:
    replicas: 1
    resources:
      requests:
        cpu: 50m
        memory: 32Mi
      limits:
        memory: 128Mi

  lokiCanary:
    kind: Deployment
    replicas: 1
    resources:
      requests:
        cpu: 25m
        memory: 32Mi
      limits:
        memory: 64Mi

  # Disable caches (accept S3 reads for cache misses)
  resultsCache:
    enabled: false
  chunksCache:
    enabled: false

  # Disable distributed components (not used in SimpleScalable)
  ingester:
    replicas: 0
  querier:
    replicas: 0
  queryFrontend:
    replicas: 0
  queryScheduler:
    replicas: 0
  distributor:
    replicas: 0
  compactor:
    replicas: 0
  indexGateway:
    replicas: 0
  patternIngester:
    replicas: 0
  bloomPlanner:
    replicas: 0
  bloomBuilder:
    replicas: 0
  bloomGateway:
    replicas: 0
  singleBinary:
    replicas: 0
```

Note: Check the Loki Helm chart docs for SimpleScalable to confirm that explicitly setting distributed components to 0 is the correct approach. The chart may handle this automatically based on `deploymentMode`. Adjust accordingly.

**Step 3: Commit**

```bash
git add kubernetes/apps/loki/values.yaml kubernetes/clusters/do-nyc3-prod/apps/loki/values.yaml
git commit -m "Switch Loki from distributed to SimpleScalable mode"
```

**Step 4: Push and verify**

Push to trigger ArgoCD sync. Verify:
- Old distributed pods are terminating
- New SimpleScalable pods (write, read, backend) are running
- Loki canary is healthy
- Query recent logs in Grafana to confirm Loki is working

---

### Task 7: Scale Down Miniflux PostgreSQL

**Purpose:** Drop Miniflux PostgreSQL from 2 instances to 1.

**Files:**
- Modify: `kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml`

**Step 1: Update cluster values**

Read `kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml` and change the PostgreSQL `instances` value from 2 to 1 (or add it if not present in cluster overrides -- check the base values at `kubernetes/apps/miniflux/values.yaml`).

**Step 2: Commit**

```bash
git add kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml
git commit -m "Scale Miniflux PostgreSQL to 1 instance"
```

---

### Task 8: Update Documentation

**Purpose:** Update docs and references that mention removed components.

**Files:**
- Modify: `CLAUDE.md` -- remove references to Mimir tenancy, Tempo datasource, otel-ebpf, n8n, Miniflux PG HA, strimzi-kafka-linkerd docs
- Modify: `docs/reference/architecture.md` -- update Object storage line (remove Mimir, Tempo, Pyroscope references)
- Remove: `docs/reference/mimir-tenancy.md`
- Remove: `docs/reference/metrics-architecture.md` (describes the old OTel-to-Mimir pipeline)
- Remove: `docs/reference/tracing-architecture.md` (Tempo is gone)
- Remove: `docs/reference/n8n.md`
- Remove: `docs/reference/miniflux.md` (if it references the old HA setup -- check first, update if still relevant)
- Modify: `docs/reference/grafana-datasources.md` -- update with new Prometheus datasource, remove Mimir and Tempo

Update the CLAUDE.md datasources table:

```markdown
## Grafana Datasources

| Name | Type |
|------|------|
| `prometheus-do-nyc3-prod` | prometheus |
| `loki-do-nyc3-prod` | loki |
```

Remove the UID column since UIDs will change.

**Step: Commit**

```bash
git add -A CLAUDE.md docs/
git commit -m "Update documentation for post-cost-reduction architecture"
```

---

### Task 9: Push All Changes and Verify

**Purpose:** Push all commits and verify ArgoCD syncs everything correctly.

**Step 1: Push**

```bash
git push origin main
```

**Step 2: Monitor ArgoCD**

Use the ArgoCD MCP tool or CLI to verify:
- Removed apps are deleted
- Prometheus app is synced and healthy
- Grafana is synced with new datasources
- Loki is synced in SimpleScalable mode
- linkerd-viz is synced with new Prometheus URL

**Step 3: Verify metrics pipeline**

- Open Grafana and confirm the prometheus-do-nyc3-prod datasource is working
- Run a test query: `up` should return targets
- Check Loki: query recent logs to confirm ingestion is working
- Check linkerd-viz: confirm the dashboard shows traffic data

**Step 4: Wait for stabilization**

Wait 15-30 minutes for all pods to settle, old pods to terminate, and PVs to be released.

---

### Task 10: Capture Post-Change Metrics

**Purpose:** Record resource usage after changes and compare with baseline.

**Step 1: Query post-change metrics**

Run the same Prometheus queries from Task 1 (now against the new Prometheus). Save to `docs/plans/2026-03-07-post-change-metrics.md`.

Note: Some metrics (like kube_pod_container_resource_requests) need time to populate in the new Prometheus. Wait until Prometheus has been scraping for at least 10-15 minutes.

**Step 2: Create comparison table**

Create a before/after comparison in `docs/plans/2026-03-07-metrics-comparison.md`:

```markdown
# Cost Reduction Metrics Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total memory usage | X GiB | Y GiB | -Z% |
| Total CPU usage | X cores | Y cores | -Z% |
| Total pods | X | Y | -Z |
| Node count | 4 | 4 (pre-resize) | - |
```

**Step 3: Commit**

```bash
git add docs/plans/2026-03-07-post-change-metrics.md docs/plans/2026-03-07-metrics-comparison.md
git commit -m "Record post-change metrics and comparison"
```

---

### Task 11: Resize Node Pool

**Purpose:** Downsize from 4x s-8vcpu-16gb ($384/mo) to 3x s-4vcpu-8gb ($144/mo).

**Files:**
- Modify: `terraform/clusters/do-nyc3-prod/cluster.tf`

**Step 1: Add new node pool**

In `terraform/clusters/do-nyc3-prod/cluster.tf`, add a new node pool resource alongside the existing one:

```hcl
resource "digitalocean_kubernetes_node_pool" "workers_4vcpu_8gb" {
  cluster_id = digitalocean_kubernetes_cluster.main.id

  name       = "workers-4vcpu-8gb"
  size       = "s-4vcpu-8gb"
  auto_scale = true
  min_nodes  = 3
  max_nodes  = 4

  labels = {
    pool = "workers-4vcpu-8gb"
  }
}
```

**Step 2: Plan and apply (add new pool)**

Follow the Terraform workflow from `docs/how-to/` or CLAUDE.md. Use the `terraform` skill if available.

```bash
cd terraform/clusters/do-nyc3-prod
terraform init
terraform plan   # Verify: only adding new node pool
terraform apply  # Or use TFC remote execution
```

Wait for new nodes to be ready: `kubectl get nodes`

**Step 3: Cordon and drain old nodes**

```bash
# Get old node names
kubectl get nodes -l pool=workers-8vcpu-16gb -o name

# Cordon (prevent new scheduling)
kubectl cordon <node1> <node2> <node3> <node4>

# Drain (move pods to new nodes)
kubectl drain <node1> --ignore-daemonsets --delete-emptydir-data
kubectl drain <node2> --ignore-daemonsets --delete-emptydir-data
kubectl drain <node3> --ignore-daemonsets --delete-emptydir-data
kubectl drain <node4> --ignore-daemonsets --delete-emptydir-data
```

Wait for all pods to be rescheduled on new nodes. Check: `kubectl get pods --all-namespaces -o wide`

Important: PVs need to be in the same region. DigitalOcean Volumes are regional, so this should work within nyc3. If any PV fails to attach, investigate.

**Step 4: Remove old node pool from Terraform**

Remove or comment out the `digitalocean_kubernetes_node_pool.workers_8vcpu_16gb` resource from `cluster.tf`.

```bash
terraform plan   # Verify: only destroying old node pool
terraform apply
```

**Step 5: Commit Terraform changes**

```bash
git add terraform/clusters/do-nyc3-prod/cluster.tf
git commit -m "Resize node pool from 4x s-8vcpu-16gb to 3x s-4vcpu-8gb"
```

---

### Task 12: Final Verification and Cleanup

**Purpose:** Confirm everything is working and capture final metrics.

**Step 1: Verify all workloads**

```bash
kubectl get pods --all-namespaces | grep -v Running | grep -v Completed
```

Should return no pending/crashing pods.

**Step 2: Verify Grafana dashboards**

Open Grafana and spot-check:
- Prometheus datasource is healthy
- Loki datasource is healthy
- Kubernetes dashboards from kube-prometheus-stack are showing data
- Linkerd-viz dashboard shows traffic

**Step 3: Check DigitalOcean billing**

```bash
doctl kubernetes cluster node-pool list 1f8f99b7-ab0b-4ccd-b94b-29d070fcddcd --format Name,Size,Count
```

Expected: 1 pool, 3x s-4vcpu-8gb.

**Step 4: Clean up orphaned PVs**

```bash
kubectl get pv | grep Released
```

Delete any released PVs from removed apps (mimir, tempo, kafka, paperless, mlflow, n8n).

**Step 5: Final metrics snapshot**

Capture final metrics after node resize (memory/CPU will look different with new allocatable totals). Update `docs/plans/2026-03-07-metrics-comparison.md` with final numbers.

**Step 6: Push**

```bash
git push origin main
```

---

## Execution Order Summary

| Task | Description | Dependencies |
|------|-------------|-------------|
| 1 | Capture baseline metrics | None |
| 2 | Deploy kube-prometheus-stack | None |
| 3 | Reconfigure Grafana | Task 2 (need Prometheus URL) |
| 4 | Reconfigure linkerd-viz | Task 2 (need Prometheus URL) |
| 5 | Remove 12 apps | Tasks 2-4 (Prometheus must be ready first) |
| 6 | Migrate Loki to SimpleScalable | Task 5 (remove tracing refs to otel-traces) |
| 7 | Scale down Miniflux PG | None (independent) |
| 8 | Update documentation | Tasks 5-7 (reflect final state) |
| 9 | Push and verify | Tasks 1-8 |
| 10 | Capture post-change metrics | Task 9 |
| 11 | Resize node pool | Task 10 (verify workloads fit) |
| 12 | Final verification | Task 11 |

## Parallelizable Tasks

- Tasks 1, 2 can run in parallel (baseline capture + chart setup)
- Tasks 3, 4, 7 can run in parallel (all independent reconfigurations once Prometheus is deployed)
- Tasks 6, 8 can run in parallel (Loki migration + doc updates)
