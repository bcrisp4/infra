# n8n Workflow Automation

n8n is a workflow automation tool deployed on do-nyc3-prod with PostgreSQL database and encrypted credential storage.

## Architecture

```
                                   +------------------+
                                   |   Tailscale      |
                                   |   (Ingress)      |
                                   +--------+---------+
                                            |
                                            v
+------------------+              +------------------+
|   1Password      |  Secrets    |      n8n         |
|   (via ESO)      +------------>|    Deployment    |
+------------------+              +--------+---------+
                                            |
                                            v
                                 +--------------------+
                                 |   CloudNativePG    |
                                 |      n8n-db        |
                                 |  (Single Instance) |
                                 +--------------------+
                                            |
                                            v
                                 +--------------------+
                                 |  DigitalOcean      |
                                 |  Spaces (Backups)  |
                                 +--------------------+
```

**Components:**
- **n8n**: Single deployment pod running workflow execution engine
- **CloudNativePG**: PostgreSQL cluster (single instance for simplicity)
- **Tailscale Ingress**: Private access via `n8n.marlin-tet.ts.net`
- **Linkerd**: Service mesh for mTLS between pods
- **Barman Cloud**: Daily backups to DigitalOcean Spaces

## Files

| Path | Purpose |
|------|---------|
| `kubernetes/apps/n8n/` | Umbrella chart (templates, values) |
| `kubernetes/clusters/do-nyc3-prod/apps/n8n/config.yaml` | App discovery config |
| `kubernetes/clusters/do-nyc3-prod/apps/n8n/values.yaml` | Cluster-specific values |
| `terraform/clusters/do-nyc3-prod/spaces.tf` | Backup bucket definition |

## Configuration

### Key Values

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/n8n/values.yaml

n8n:
  main:
    config:
      n8n:
        host: n8n.marlin-tet.ts.net
        protocol: https
        metrics: true
      webhook:
        url: https://n8n.marlin-tet.ts.net

ingress:
  enabled: true
  className: tailscale
  host: n8n
  annotations:
    tailscale.com/proxy-group: ingress-proxies
    tailscale.com/tags: tag:k8s-services

database:
  instances: 1
  storage:
    size: 5Gi

backup:
  enabled: true
  retentionPolicy: "28d"
```

### PostgreSQL Configuration

n8n connects to PostgreSQL via environment variables set in the umbrella chart:

| Variable | Value | Source |
|----------|-------|--------|
| `DB_TYPE` | `postgresdb` | Chart values |
| `DB_POSTGRESDB_HOST` | `n8n-db-rw` | Chart values (CNPG service) |
| `DB_POSTGRESDB_PORT` | `5432` | Chart values |
| `DB_POSTGRESDB_DATABASE` | `n8n` | Chart values |
| `DB_POSTGRESDB_USER` | `n8n` | Chart values |
| `DB_POSTGRESDB_PASSWORD` | (from secret) | CNPG secret `n8n-db-app` |
| `DB_POSTGRESDB_SCHEMA` | `public` | Chart values |

### Encryption Key

n8n encrypts stored credentials using `N8N_ENCRYPTION_KEY`. This key is stored in 1Password and injected via ExternalSecret.

**Critical**: This key must remain consistent. Changing it will make existing credentials unreadable.

The key is stored in 1Password item `n8n-encryption-key` with field `key`. Generate with:

```bash
openssl rand -hex 32
```

## Initial Setup

n8n requires a manual owner account setup on first access. This is a one-time task that takes about 30 seconds.

1. Navigate to `https://n8n.marlin-tet.ts.net`
2. Complete the "Set up owner account" wizard
3. Credentials are stored in PostgreSQL (backed up daily)

**Note**: There is no way to automate this via environment variables. The owner account persists in the database across restarts.

## Backups

Daily backups via Barman Cloud Plugin to DigitalOcean Spaces.

- **Schedule**: Daily at 4:00 AM UTC
- **Retention**: 28 days
- **Bucket**: `bc4-do-nyc3-prod-n8n-postgres-backups`
- **WAL Archiving**: Continuous, enables point-in-time recovery

### Check Backup Status

```bash
# List backups
kubectl get backup -n n8n

# Check scheduled backup
kubectl get scheduledbackup -n n8n

# Check backup health in cluster status
kubectl cnpg status n8n-db -n n8n
```

## Webhooks

n8n webhooks are accessible at `https://n8n.marlin-tet.ts.net/webhook/*` and `https://n8n.marlin-tet.ts.net/webhook-test/*`.

Currently webhooks are only accessible via Tailscale (private). For public webhook endpoints, Tailscale Funnel would need to be configured (not yet implemented).

## Linkerd Mesh

The namespace has `linkerd.io/inject: enabled` annotation. All pods get Linkerd sidecar proxies automatically.

Verify pods are meshed (should show 2/2 containers):

```bash
kubectl get pods -n n8n
```

## Useful Commands

```bash
# Check all resources
kubectl get all -n n8n

# Database cluster status
kubectl cnpg status n8n-db -n n8n

# Application logs
kubectl logs -n n8n -l app.kubernetes.io/name=n8n

# Database logs
kubectl logs -n n8n n8n-db-1 -c postgres

# ExternalSecret status
kubectl get externalsecret -n n8n

# Backup status
kubectl get backup,scheduledbackup,objectstore -n n8n

# Check ingress
kubectl get ingress -n n8n
```

## Scaling Considerations

n8n supports horizontal scaling for enterprise use with separate main and worker processes. For personal use, a single instance is sufficient.

If scaling is needed:
- Use `queue` execution mode instead of default `main`
- Deploy separate worker pods with `EXECUTIONS_MODE=queue`
- Add Redis for queue backend

## References

- [n8n Documentation](https://docs.n8n.io/)
- [n8n Environment Variables](https://docs.n8n.io/hosting/configuration/environment-variables/)
- [n8n PostgreSQL Configuration](https://docs.n8n.io/hosting/configuration/environment-variables/database/)
- [8gears n8n Helm Chart](https://artifacthub.io/packages/helm/8gears/n8n)
