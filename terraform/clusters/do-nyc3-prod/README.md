# do-nyc3-prod Cluster

DigitalOcean NYC3 production cluster.

## Resources

- **DOKS Cluster** - Managed Kubernetes (to be added)
- **Spaces Buckets** - S3-compatible storage for observability stack
- **Spaces Access Keys** - Per-bucket scoped credentials
- **1Password Items** - Credentials stored for external-secrets operator

### Observability Storage

| Component | Bucket | Purpose |
|-----------|--------|---------|
| Loki | `bc4-do-nyc3-prod-loki` | Log storage |
| Mimir | `bc4-do-nyc3-prod-mimir` | Metrics storage |
| Tempo | `bc4-do-nyc3-prod-tempo` | Trace storage |
| Pyroscope | `bc4-do-nyc3-prod-pyroscope` | Profile storage |

Each bucket has its own scoped access key with read/write permissions, stored in 1Password.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Terraform      │────▶│  1Password       │────▶│  Kubernetes     │
│  (creates keys) │     │  (stores creds)  │     │  (ext-secrets)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                                │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│  DO Spaces      │◀─────────────────────────────│  Loki/Mimir/    │
│  (buckets)      │      (per-bucket keys)       │  Tempo/Pyroscope│
└─────────────────┘                              └─────────────────┘
```

## Prerequisites

1. Run `terraform/bootstrap` to create TFC workspace
2. Set credentials in TFC variable sets:
   - **digitalocean-credentials**: `DIGITALOCEAN_TOKEN`
   - **onepassword-credentials**: `OP_SERVICE_ACCOUNT_TOKEN`, `onepassword_vault`
3. Add cluster to `terraform/global/terraform.tfvars` and apply

## Deploy

```bash
terraform init
terraform plan
terraform apply
```

## Outputs

| Output | Description |
|--------|-------------|
| `spaces_buckets` | Bucket names and endpoints for each component |
| `spaces_endpoint` | S3-compatible endpoint URL |
| `spaces_region` | Spaces region (nyc3) |
| `onepassword_items` | 1Password item references for external-secrets |

## Files

| File | Purpose |
|------|---------|
| `main.tf` | Provider config and remote state |
| `backend.tf` | Terraform Cloud backend |
| `variables.tf` | Input variables |
| `spaces.tf` | Spaces buckets and per-bucket access keys |
| `onepassword.tf` | 1Password items for S3 credentials |

## 1Password Integration

Terraform creates 1Password items containing S3 credentials for each bucket:

| Item | Contents |
|------|----------|
| `do-nyc3-prod-loki-s3` | Loki bucket credentials |
| `do-nyc3-prod-mimir-s3` | Mimir bucket credentials |
| `do-nyc3-prod-tempo-s3` | Tempo bucket credentials |
| `do-nyc3-prod-pyroscope-s3` | Pyroscope bucket credentials |

Each item contains:
- `username` - Spaces access key ID
- `password` - Spaces secret access key
- `bucket` - Bucket name
- `endpoint` - S3 endpoint URL
- `region` - Spaces region

### Using with External Secrets Operator

Configure a `ClusterSecretStore` pointing to 1Password:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: onepassword
spec:
  provider:
    onepassword:
      connectHost: https://onepassword-connect.example.com
      vaults:
        infra: 1  # vault ID priority
      auth:
        secretRef:
          connectTokenSecretRef:
            name: onepassword-connect-token
            key: token
            namespace: external-secrets
```

Then create an `ExternalSecret` for each app:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: loki-s3
  namespace: loki
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: onepassword
  target:
    name: loki-s3-credentials
  data:
    - secretKey: AWS_ACCESS_KEY_ID
      remoteRef:
        key: do-nyc3-prod-loki-s3
        property: username
    - secretKey: AWS_SECRET_ACCESS_KEY
      remoteRef:
        key: do-nyc3-prod-loki-s3
        property: password
    - secretKey: BUCKET
      remoteRef:
        key: do-nyc3-prod-loki-s3
        property: .bucket  # from S3 Configuration section
    - secretKey: ENDPOINT
      remoteRef:
        key: do-nyc3-prod-loki-s3
        property: .endpoint
```

## Next Steps

After Terraform apply:

1. Add DOKS cluster module when ready
2. Export kubeconfig: `terraform output -raw kubeconfig > ~/.kube/do-nyc3-prod`
3. Bootstrap ArgoCD: `./scripts/bootstrap-argocd.sh do-nyc3-prod`
4. Deploy external-secrets operator
5. Configure ClusterSecretStore for 1Password
