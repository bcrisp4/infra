# How to Update kubernetes-mixin

This guide explains how to update the kubernetes-mixin dashboards and recording rules to a new version.

## Prerequisites

- `mimirtool` installed (`brew install grafana/tap/mimirtool`)
- `jq` installed (`brew install jq`)
- `kubectl` configured with cluster access
- `unzip` and `curl` available

## Update Procedure

### Step 1: Check for New Releases

Check the kubernetes-mixin releases page for new versions:

https://github.com/kubernetes-monitoring/kubernetes-mixin/releases

Review the changelog for any breaking changes or new dashboards.

### Step 2: Run the Update Script

```bash
# Update to a specific version
./scripts/update-kubernetes-mixin.sh 1.5.0

# Or use the default version (currently 1.4.1)
./scripts/update-kubernetes-mixin.sh
```

The script will:
1. Download the specified release
2. Extract and convert rules to Mimir format (adds `namespace: kubernetes-mixin`)
3. Rename `cluster` label to `k8s_cluster` in rules (avoids collision with CNPG)
4. Extract dashboards, remove Windows/inaccessible dashboards
5. Rename `cluster` label to `k8s_cluster` in dashboard queries and variables
6. Add stable UIDs to dashboards (prevents duplicates)
7. Copy files to the appropriate locations

### Step 3: Review Changes

```bash
# See what changed
git diff kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml
git diff kubernetes/apps/grafana/dashboards/kubernetes-mixin/

# Check for new or removed dashboards
git status kubernetes/apps/grafana/dashboards/kubernetes-mixin/
```

### Step 4: Upload Rules to Mimir

Rules must be uploaded manually via mimirtool (until GitOps automation is implemented):

```bash
# Port-forward to mimir gateway
kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &

# Sync rules to Mimir
mimirtool rules sync \
  --address=http://localhost:8080 \
  --id=prod \
  kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml

# Stop port-forward
kill %1
```

You should see output like:
```
Sync Summary: 0 Groups Created, 16 Groups Updated, 0 Groups Deleted
```

### Step 5: Commit and Push

```bash
git add kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml \
        kubernetes/apps/grafana/dashboards/kubernetes-mixin/

git commit -m "Update kubernetes-mixin to version X.Y.Z"
git push
```

Dashboards will deploy automatically via ArgoCD when the grafana app syncs.

### Step 6: Verify

After deployment, verify the update:

1. **Dashboards**: Open Grafana → Dashboards → Kubernetes folder
   - Check that dashboards load without errors
   - Verify data is displayed in panels

2. **Recording rules**: Query a recording rule metric:
   ```promql
   namespace_cpu:kube_pod_container_resource_requests:sum
   ```

3. **List rules in Mimir**:
   ```bash
   kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &
   mimirtool rules list --address=http://localhost:8080 --id=prod
   kill %1
   ```

## Troubleshooting

### Dashboards show "No data"

1. Check that recording rules are loaded:
   ```bash
   kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &
   mimirtool rules list --address=http://localhost:8080 --id=prod | grep kubernetes-mixin
   ```

2. Verify metric relabeling is working:
   ```promql
   kube_pod_info{namespace!="kube-state-metrics"}
   ```
   Should show actual pod namespaces, not "kube-state-metrics".

3. Check that kube-state-metrics is running:
   ```bash
   kubectl get pods -n kube-state-metrics
   ```

### mimirtool sync fails

1. Check port-forward is active:
   ```bash
   curl http://localhost:8080/ready
   ```

2. Verify rules file format:
   ```bash
   head -5 kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml
   # Should start with: namespace: kubernetes-mixin
   ```

3. Check for YAML syntax errors:
   ```bash
   yq eval '.' kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml > /dev/null
   ```

### Dashboard duplicates appear

The update script adds stable UIDs to prevent duplicates. If you see duplicates:

1. Check that UIDs are set:
   ```bash
   jq '.uid' kubernetes/apps/grafana/dashboards/kubernetes-mixin/*.json
   ```

2. Manually delete duplicate dashboards in Grafana UI

### ConfigMap too large

Kubernetes has a 1MB limit on ConfigMap size. If the dashboards exceed this:

1. Split into multiple ConfigMaps (e.g., by category)
2. Or use Grafana's dashboard provisioning from Git directly

## What the Script Does

The `scripts/update-kubernetes-mixin.sh` script:

```bash
# 1. Downloads release zip
curl -sL "https://github.com/kubernetes-monitoring/kubernetes-mixin/releases/download/version-${VERSION}/..." \
  -o /tmp/k8s-mixin.zip

# 2. Extracts rules, adds Mimir namespace key, and renames cluster -> k8s_cluster
{
  echo "namespace: kubernetes-mixin"
  unzip -p /tmp/k8s-mixin.zip prometheus_rules.yaml | \
    sed -E 's/cluster="/k8s_cluster="/g; ...'  # Renames cluster label
} > kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml

# 3. Extracts dashboards
unzip -j /tmp/k8s-mixin.zip "dashboards_out/*.json" -d /tmp/dashboards/

# 4. Removes inapplicable dashboards
rm -f /tmp/dashboards/*windows*.json
rm -f /tmp/dashboards/scheduler.json
rm -f /tmp/dashboards/controller-manager.json

# 5. Renames cluster label to k8s_cluster in dashboard queries
# This avoids collision with CloudNativePG's "cluster" label
for f in /tmp/dashboards/*.json; do
  sed -i.bak -E 's/cluster=\\"/k8s_cluster=\\"/g; s/\$cluster/\$k8s_cluster/g; ...' "$f"
  jq '(.templating.list[] | select(.name == "cluster") | .name) = "k8s_cluster"' "$f" ...
done

# 6. Adds stable UIDs (hash of dashboard name, cross-platform)
for f in /tmp/dashboards/*.json; do
  uid=$(echo -n "k8s-mixin-$(basename $f .json)" | md5hash | cut -c1-12)
  jq --arg uid "$uid" '.uid = $uid' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# 7. Copies to repo
cp /tmp/dashboards/*.json kubernetes/apps/grafana/dashboards/kubernetes-mixin/
```

**Note**: We use `k8s_cluster` instead of the standard `cluster` label to avoid collision with CloudNativePG, which uses `cluster` for database cluster names.

## Related Documentation

- [kubernetes-mixin Reference](../reference/kubernetes-mixin.md) - Full component reference
- [Metrics Architecture](../reference/metrics-architecture.md) - Metrics infrastructure overview
- [Future: GitOps Rule Automation](../tasks/mimir-rules-gitops.md) - Planned automation for rule uploads
