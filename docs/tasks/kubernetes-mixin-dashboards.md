# Task: Deploy Kubernetes-Mixin Dashboards

## Overview

Deploy the kubernetes-mixin Grafana dashboards for comprehensive Kubernetes resource monitoring. This requires three components:
1. **Metric relabeling** - Fix kube-state-metrics label mismatch
2. **Recording rules** - Pre-aggregate metrics for dashboard performance
3. **Dashboards** - JSON files loaded via ConfigMap sidecar

## Problem: Label Mismatch

kube-state-metrics (KSM) uses `exported_*` prefix labels:
- `exported_namespace` - the namespace of the resource being monitored
- `exported_pod` - the pod being monitored
- `namespace` - the KSM pod's own namespace (always `kube-state-metrics`)

kubernetes-mixin expects standard labels (`namespace`, `pod`, `container`). Recording rules and dashboards won't work without fixing this.

**Solution**: Add `metric_relabel_configs` to rename `exported_*` labels to standard names at scrape time.

> **Breaking Change**: Existing queries using `exported_namespace`, `exported_pod`, etc. will need to be updated to use `namespace`, `pod`, etc.

## Implementation Steps

### Phase 0: Audit Existing Dashboards

Before adding metric relabeling, check for existing dashboards using `exported_*` labels that will break.

**Search existing dashboards for `exported_` usage**:
```bash
grep -r "exported_" kubernetes/apps/grafana/dashboards/
```

**Check Grafana for dashboards not in Git** (manually created):
- Use Grafana API or UI to search for dashboards with `exported_namespace` in queries

**Update affected dashboards** to use standard labels (`namespace`, `pod`, etc.) after relabeling is deployed.

### Phase 1: Metric Relabeling

**File**: `kubernetes/clusters/do-nyc3-prod/apps/otel-metrics/values.yaml`

Add `metric_relabel_configs` to the `prometheus/annotations` scrape config to rename labels for kube-state-metrics:

```yaml
metric_relabel_configs:
  # Only apply to kube-state-metrics (job contains kube-state-metrics)
  - source_labels: [job, exported_namespace]
    regex: ".*/kube-state-metrics;(.+)"
    target_label: namespace
    replacement: "$1"
    action: replace
  - source_labels: [job, exported_pod]
    regex: ".*/kube-state-metrics;(.+)"
    target_label: pod
    replacement: "$1"
    action: replace
  - source_labels: [job, exported_container]
    regex: ".*/kube-state-metrics;(.+)"
    target_label: container
    replacement: "$1"
    action: replace
  - source_labels: [job, exported_node]
    regex: ".*/kube-state-metrics;(.+)"
    target_label: node
    replacement: "$1"
    action: replace
  # Drop exported_* labels after copying
  - regex: "exported_(namespace|pod|container|node)"
    action: labeldrop
```

### Phase 2: Recording Rules

Recording rules pre-aggregate expensive queries. They must be loaded into Mimir ruler.

**Files to create**:
- `kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml` - Rules from release
- `kubernetes/apps/mimir/templates/kubernetes-mixin-rules-configmap.yaml` - ConfigMap template

**File to modify**:
- `kubernetes/clusters/do-nyc3-prod/apps/mimir/values.yaml` - Mount ConfigMap in ruler

**Download rules**:
```bash
curl -sL "https://github.com/kubernetes-monitoring/kubernetes-mixin/releases/download/version-1.4.1/kubernetes-mixin-version-1.4.1.zip" -o /tmp/k8s-mixin.zip
unzip -p /tmp/k8s-mixin.zip prometheus_rules.yaml > kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml
```

**ConfigMap template** (`kubernetes/apps/mimir/templates/kubernetes-mixin-rules-configmap.yaml`):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kubernetes-mixin-rules
  labels:
    app.kubernetes.io/name: mimir
data:
  rules.yaml: |
    {{- .Files.Get "files/kubernetes-mixin-rules.yaml" | nindent 4 }}
```

**Ruler configuration** (add to mimir values):
```yaml
mimir-distributed:
  ruler:
    extraVolumes:
      - name: kubernetes-mixin-rules
        configMap:
          name: kubernetes-mixin-rules
    extraVolumeMounts:
      - name: kubernetes-mixin-rules
        mountPath: /etc/mimir/rules/kubernetes-mixin
        readOnly: true
```

### Phase 3: Dashboards

**Download and organize dashboards**:
```bash
# Extract dashboards
unzip -j /tmp/k8s-mixin.zip "dashboards_out/*.json" -d /tmp/k8s-dashboards/

# Remove Windows dashboards (not needed for DOKS)
rm /tmp/k8s-dashboards/*windows*.json

# Add stable UIDs to prevent duplicates
for f in /tmp/k8s-dashboards/*.json; do
  name=$(basename "$f" .json)
  uid=$(echo -n "k8s-mixin-$name" | md5 | cut -c1-12)
  jq --arg uid "$uid" '.uid = $uid' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
```

**Directory structure**:
```
kubernetes/apps/grafana/dashboards/kubernetes-mixin/
  k8s-resources-cluster.json
  k8s-resources-namespace.json
  k8s-resources-node.json
  k8s-resources-pod.json
  k8s-resources-workload.json
  k8s-resources-workloads-namespace.json
  kubelet.json
  apiserver.json
  persistentvolumesusage.json
  ... (networking dashboards)
```

**ConfigMap template** (`kubernetes/apps/grafana/templates/kubernetes-mixin-dashboards-configmap.yaml`):
```yaml
{{- $files := .Files.Glob "dashboards/kubernetes-mixin/*.json" }}
{{- if $files }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards-kubernetes-mixin
  labels:
    grafana_dashboard: "1"
  annotations:
    k8s-sidecar-target-directory: /tmp/dashboards/Kubernetes
data:
  {{- range $path, $bytes := $files }}
  {{ base $path }}: |
    {{- $.Files.Get $path | nindent 4 }}
  {{- end }}
{{- end }}
```

The Grafana sidecar is already configured to watch for ConfigMaps with `grafana_dashboard: "1"` label.

## Files Summary

| File | Action |
|------|--------|
| `kubernetes/clusters/do-nyc3-prod/apps/otel-metrics/values.yaml` | Modify - add metric_relabel_configs |
| `kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml` | Create - recording rules |
| `kubernetes/apps/mimir/templates/kubernetes-mixin-rules-configmap.yaml` | Create - rules ConfigMap |
| `kubernetes/clusters/do-nyc3-prod/apps/mimir/values.yaml` | Modify - mount rules in ruler |
| `kubernetes/apps/grafana/dashboards/kubernetes-mixin/*.json` | Create - ~15 dashboard files |
| `kubernetes/apps/grafana/templates/kubernetes-mixin-dashboards-configmap.yaml` | Create - dashboards ConfigMap |

## Verification

1. **Metric relabeling**: Query `kube_pod_info` and verify `namespace` label shows actual pod namespaces (not `kube-state-metrics`)

2. **Recording rules**: Query for recording rule metrics:
   ```promql
   namespace_cpu:kube_pod_container_resource_requests:sum
   ```

3. **Dashboards**: Open Grafana, navigate to "Kubernetes" folder, verify dashboards load with data

## Notes

- **DOKS limitations**: Skip scheduler/controller-manager/etcd dashboards (managed by DigitalOcean, not accessible)
- **Windows dashboards**: Skip - not applicable
- **Updates**: Create `scripts/update-kubernetes-mixin.sh` for future updates from upstream
- **Source**: https://github.com/kubernetes-monitoring/kubernetes-mixin
