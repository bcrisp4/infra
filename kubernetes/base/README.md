# Kubernetes Base Configuration

This directory contains shared configuration and values used across all clusters.

## Files

| File | Purpose |
|------|---------|
| `values-common.yaml` | Common Helm values applied to all applications |

## Usage

Reference base values in ArgoCD ApplicationSet value files:

```yaml
helm:
  valueFiles:
    - ../../base/values-common.yaml
    - values.yaml
    - ../../clusters/{{cluster_name}}/apps/{{app}}/values.yaml
```

## Common Labels

All resources should include these standard labels for consistency:

```yaml
labels:
  app.kubernetes.io/managed-by: argocd
  app.kubernetes.io/part-of: infra
```
