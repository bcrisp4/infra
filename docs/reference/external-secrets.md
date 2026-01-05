# External Secrets Operator

Reference documentation for External Secrets Operator (ESO) with 1Password integration.

## Overview

ESO syncs secrets from external providers (like 1Password) into Kubernetes Secrets. We use the `onepasswordSDK` provider with a ClusterSecretStore.

## Key Configuration

### API Versions

ESO 1.x uses `external-secrets.io/v1` API (not v1beta1). Always check the docs for the correct API version.

### 1Password SDK Provider

The `onepasswordSDK` provider requires ESO 1.x. Older 0.x versions use different provider config.

### Secret Reference Format

The onepasswordSDK provider uses `<item>/<field>` format (vault is configured in ClusterSecretStore):

```yaml
remoteRef:
  key: "<item>/<field>"
```

Example: `my-app-credentials/password`

## Common Issues and Solutions

### 1. OOMKilled Pods

Default chart memory limits (128Mi) are too low and cause OOMKilled. Use at least 256Mi:

```yaml
external-secrets:
  resources:
    limits:
      memory: 256Mi
```

### 2. CRD Upgrade Conflicts

When upgrading ESO from 0.x to 1.x, you may need to delete old CRDs due to conversion webhook conflicts:

```bash
kubectl get crd -o name | grep external-secrets.io | xargs kubectl delete
```

ArgoCD will recreate them with the new version.

### 3. ArgoCD Diff on Default Values

The ESO webhook injects default values that cause ArgoCD diff. Always specify explicitly:

```yaml
remoteRef:
  key: "item/field"
  conversionStrategy: Default
  decodingStrategy: None
  metadataPolicy: None
```

### 4. 1Password Rate Limits

Service accounts have strict rate limits that ESO can easily hit:

| Plan | Rate Limit |
|------|------------|
| Teams/Families | 1,000 reads/hour (account-wide, not per-token) |
| Business | 10,000 reads/hour, 50,000/day |

Check current usage:
```bash
op service-account ratelimit <service-account-name>
```

**Mitigation strategies:**
- Use `refreshInterval: 24h` (or longer) for secrets that rarely change
- Set `refreshInterval: 3600` on ClusterSecretStore to reduce validation calls
- Consider `refreshPolicy: CreatedOnce` for truly static secrets
- Note: Pod restarts and ArgoCD syncs trigger immediate re-fetches regardless of interval

## Initial Setup

### Create 1Password Service Account

```bash
kubectl create namespace external-secrets
kubectl create secret generic onepassword-token \
  --namespace external-secrets \
  --from-literal=token="$(op service-account create 'name' --vault 'Vault' --permissions read_items --format json | jq -r '.token')"
```

## Operations

### Force Refresh an ExternalSecret

To immediately sync after changing a secret in 1Password:

```bash
# Add/update annotation to trigger reconciliation
kubectl annotate externalsecret <name> -n <namespace> force-sync=$(date +%s) --overwrite

# Example:
kubectl annotate externalsecret mimir-s3-credentials -n mimir force-sync=$(date +%s) --overwrite
```

## Related

- [1Password Terraform Provider](onepassword-terraform.md)
