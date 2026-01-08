# Mimir Rules GitOps Automation

Automate Mimir recording/alerting rules deployment instead of manual mimirtool uploads.

## Current State

Recording rules (like kubernetes-mixin) are stored in the repo at `kubernetes/apps/mimir/files/` but must be manually uploaded to Mimir via mimirtool:

```bash
kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &
mimirtool rules sync --address=http://localhost:8080 --id=prod \
  kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml
```

This is not GitOps-friendly because:
- Rules changes require manual intervention after merge
- No audit trail of when rules were actually applied
- Easy to forget the upload step

## Goal

Rules should deploy automatically when changes are pushed, just like dashboards deploy via ArgoCD.

## Options

### Option 1: Kubernetes Job with Helm Hook

Create a Job that runs mimirtool on Helm install/upgrade:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mimir-rules-sync
  annotations:
    helm.sh/hook: post-install,post-upgrade
    helm.sh/hook-delete-policy: hook-succeeded
spec:
  template:
    spec:
      containers:
        - name: mimirtool
          image: grafana/mimirtool:latest
          command:
            - mimirtool
            - rules
            - sync
            - --address=http://mimir-gateway.mimir.svc.cluster.local
            - --id=prod
            - /rules/kubernetes-mixin-rules.yaml
          volumeMounts:
            - name: rules
              mountPath: /rules
      volumes:
        - name: rules
          configMap:
            name: mimir-rules
      restartPolicy: Never
```

**Pros:**
- Runs automatically on deploy
- Native Kubernetes/Helm approach
- Clear audit trail via Job history

**Cons:**
- Job runs every deploy even if rules unchanged
- Need to manage ConfigMap for rules files
- Hook timing can be tricky with ArgoCD

### Option 2: GitHub Actions Pipeline

Add a workflow that runs mimirtool when rules files change:

```yaml
on:
  push:
    paths:
      - 'kubernetes/apps/mimir/files/**'
    branches: [main]

jobs:
  sync-rules:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install mimirtool
        run: |
          curl -sL https://github.com/grafana/mimir/releases/download/mimir-2.14.0/mimirtool-linux-amd64 -o mimirtool
          chmod +x mimirtool
      - name: Sync rules
        run: |
          ./mimirtool rules sync \
            --address=${{ secrets.MIMIR_ADDRESS }} \
            --id=prod \
            kubernetes/apps/mimir/files/*.yaml
```

**Pros:**
- Only runs when rules actually change
- Clear CI/CD integration
- Works independently of Kubernetes

**Cons:**
- Requires network access to Mimir (Tailscale or public endpoint)
- Separate from ArgoCD deployment flow
- Need to manage secrets in GitHub

### Option 3: Mimir Rules Controller/Operator

Use a Kubernetes operator that watches ConfigMaps/CRDs and syncs to Mimir:

- [prometheus-operator](https://github.com/prometheus-operator/prometheus-operator) PrometheusRule CRDs (if using Prometheus compatibility)
- Custom controller using mimirtool

**Pros:**
- Fully GitOps native
- Watches for changes continuously
- Standard Kubernetes patterns

**Cons:**
- Additional component to deploy and maintain
- May not exist as mature solution for Mimir

## Recommendation

**Option 1 (Kubernetes Job)** is probably the best balance:
- Integrates with existing Helm/ArgoCD flow
- No external dependencies
- Relatively simple to implement

The Job can be made idempotent by using `mimirtool rules sync` which only updates changed rules.

## Implementation Checklist

- [ ] Research if ArgoCD resource hooks work better than Helm hooks
- [ ] Create ConfigMap template for rules files
- [ ] Create Job template with mimirtool
- [ ] Test hook timing with ArgoCD sync
- [ ] Verify rules are uploaded after deploy
- [ ] Add error handling / alerting for failed syncs
- [ ] Document the new workflow
- [ ] Remove manual upload instructions from update script

## Related

- [kubernetes-mixin-dashboards.md](kubernetes-mixin-dashboards.md) - Original task that introduced rules
- `scripts/update-kubernetes-mixin.sh` - Script to update mixin rules and dashboards
