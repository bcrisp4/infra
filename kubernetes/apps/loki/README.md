# Loki

Grafana Loki log aggregation system deployed in distributed mode with S3-compatible object storage.

## Architecture

Loki runs in **distributed mode** with separate components for the read and write paths:

| Component | Purpose |
|-----------|---------|
| Distributor | Receives and validates incoming log streams |
| Ingester | Writes log data to long-term storage |
| Querier | Executes LogQL queries against storage |
| Query Frontend | Caches and splits queries for performance |
| Query Scheduler | Distributes queries across queriers |
| Index Gateway | Serves index queries from object storage |
| Compactor | Compacts and retains index data |
| Gateway | nginx reverse proxy for routing requests |

## S3 Storage

Loki stores all log data in S3-compatible object storage (DO Spaces, AWS S3, MinIO, etc.).

### Credentials

Credentials are injected via environment variables from a Kubernetes secret named `s3-credentials`:

- `AWS_ACCESS_KEY_ID` - S3 access key
- `AWS_SECRET_ACCESS_KEY` - S3 secret key

The ExternalSecret template (`templates/externalsecret.yaml`) syncs these from 1Password.

### 1Password Item Structure

Terraform creates 1Password items with the naming convention `{cluster}-loki-s3`:

```
Item: do-nyc3-prod-loki-s3
Category: login
Fields:
  - username: <access key>
  - password: <secret key>
Section "S3 Configuration":
  - bucket: bc4-do-nyc3-prod-loki
  - endpoint: https://nyc3.digitaloceanspaces.com
  - region: nyc3
```

## Cluster Configuration

Each cluster provides its own `values.yaml` with storage settings:

```yaml
externalSecret:
  enabled: true
  itemName: do-nyc3-prod-loki-s3

loki:
  loki:
    storage:
      bucketNames:
        chunks: bc4-do-nyc3-prod-loki
        ruler: bc4-do-nyc3-prod-loki
        admin: bc4-do-nyc3-prod-loki
      s3:
        endpoint: nyc3.digitaloceanspaces.com
        accessKeyId: ${AWS_ACCESS_KEY_ID}
        secretAccessKey: ${AWS_SECRET_ACCESS_KEY}
```

The `${VAR}` syntax works because Loki is started with `-config.expand-env=true`.

## Linkerd Integration

To add Loki to the service mesh, set the namespace annotation in `config.yaml`:

```yaml
name: loki
namespaceAnnotations:
  linkerd.io/inject: enabled
```

All Loki pods will receive Linkerd sidecar proxies with automatic mTLS.

## Retention

Default retention is 28 days (672h), configured via:

```yaml
loki:
  loki:
    limits_config:
      retention_period: 672h
```

The compactor handles deletion of expired data from object storage.
