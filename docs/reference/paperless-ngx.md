# Paperless-ngx Document Management

Paperless-ngx is a document management system that scans, indexes, and archives paper documents. Deployed on do-nyc3-prod with strict network isolation to protect sensitive documents.

## Architecture

```
                                   +------------------+
                                   |   Tailscale      |
                                   |   (Ingress)      |
                                   +--------+---------+
                                            |
                                            v
+------------------+              +------------------+
|   1Password      |  Secrets    |   Paperless-ngx  |
|   (via ESO)      +------------>|   Deployment     |
+------------------+              +--------+---------+
                                       |       |
                         +-------------+       +-------------+
                         v                                   v
              +--------------------+              +------------------+
              |   CloudNativePG    |              |   Redis          |
              |   paperless-ngx-db |              |   (Task Broker)  |
              +--------------------+              +------------------+
                         |
                         v
              +--------------------+
              |  DigitalOcean      |
              |  Spaces (Backups)  |
              +--------------------+
```

**Components:**
- **Paperless-ngx**: Single deployment pod for web UI and background workers
- **CloudNativePG**: PostgreSQL cluster for document metadata
- **Redis**: Task broker for Celery background jobs (OCR, classification)
- **Tailscale Ingress**: Private access via `paperless-ngx.marlin-tet.ts.net`
- **Linkerd**: Service mesh for mTLS between pods
- **Barman Cloud**: Daily PostgreSQL backups to DigitalOcean Spaces
- **Restic CronJob**: Encrypted file backups to separate S3 bucket

## Files

| Path | Purpose |
|------|---------|
| `kubernetes/apps/paperless-ngx/` | Custom Helm chart (no external dependencies) |
| `kubernetes/clusters/do-nyc3-prod/apps/paperless-ngx/config.yaml` | App discovery config |
| `kubernetes/clusters/do-nyc3-prod/apps/paperless-ngx/values.yaml` | Cluster-specific values |
| `terraform/clusters/do-nyc3-prod/spaces.tf` | Backup bucket definitions |

## Configuration

### Key Values

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/paperless-ngx/values.yaml

image:
  tag: "2.20.3"

persistence:
  size: 10Gi    # Combined data + media

database:
  instances: 1  # Single instance (add 2nd for HA)
  storage:
    size: 5Gi

backup:
  enabled: true
  retentionPolicy: "28d"

fileBackup:
  enabled: true
  schedule: "0 4 * * *"  # 4 AM UTC daily
  retention:
    keepDaily: 7
    keepWeekly: 4
    keepMonthly: 6
```

### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `PAPERLESS_DBHOST` | Values | PostgreSQL hostname (`paperless-ngx-db-rw`) |
| `PAPERLESS_DBNAME` | Values | Database name (`paperless-ngx`) |
| `PAPERLESS_DBUSER` | Values | Database user (`paperless-ngx`) |
| `PAPERLESS_DBPASS` | CNPG Secret | Database password |
| `PAPERLESS_REDIS` | Values | Redis URL with password |
| `PAPERLESS_SECRET_KEY` | ExternalSecret | Django secret key (50+ chars) |
| `PAPERLESS_ADMIN_USER` | ExternalSecret | Initial admin username |
| `PAPERLESS_ADMIN_PASSWORD` | ExternalSecret | Initial admin password |
| `PAPERLESS_URL` | Values | Public URL for the application |
| `PAPERLESS_DATA_DIR` | Values | Data directory (`/usr/src/paperless/data`) |
| `PAPERLESS_MEDIA_ROOT` | Values | Media directory (`/usr/src/paperless/data/media`) |

## 1Password Items Required

Create these items in 1Password before deployment:

| Item Name | Type | Fields | Description |
|-----------|------|--------|-------------|
| `paperless-ngx-admin` | Login | `username`, `password` | Admin account credentials |
| `paperless-ngx-secret-key` | Password | `key` | Django secret key (50+ random chars) |
| `paperless-ngx-redis` | Password | `password` | Redis password (32+ random chars) |
| `paperless-ngx-restic` | Password | `password` | Restic encryption key (64+ random chars) |

Auto-created by Terraform:
- `do-nyc3-prod-paperless-ngx-postgres-s3` - PostgreSQL backup S3 credentials
- `do-nyc3-prod-paperless-ngx-files-s3` - Restic file backup S3 credentials

## Network Policy

Paperless-ngx has strict egress restrictions to prevent data exfiltration:

### Allowed Egress (paperless-ngx pod)

| Destination | Port | Purpose |
|-------------|------|---------|
| kube-dns | 53/UDP, 53/TCP | DNS resolution |
| paperless-ngx-db | 5432/TCP | PostgreSQL |
| paperless-ngx-redis | 6379/TCP | Redis task broker |

**All other egress is blocked**, including:
- Internet access
- External mail servers (IMAP/SMTP)
- Any external APIs

### Allowed Egress (Restic backup CronJob)

| Destination | Port | Purpose |
|-------------|------|---------|
| kube-dns | 53/UDP, 53/TCP | DNS resolution |
| Any (S3) | 443/TCP | S3 backup uploads |

## Storage

Single 10Gi PVC mounted at `/usr/src/paperless/data`:

```
/usr/src/paperless/data/
├── data/           # Paperless internal data
├── media/          # Original and archived documents
└── ...             # Thumbnails, index, etc.
```

**Note:** Paperless-ngx does not support native S3 storage. Files must be stored on PVC.

## Backups

### PostgreSQL Backups (Barman Cloud)

- **Schedule**: Daily at 3:00 AM UTC
- **Retention**: 28 days
- **Bucket**: `bc4-do-nyc3-prod-paperless-ngx-postgres-backups`
- **WAL Archiving**: Continuous (point-in-time recovery)

```bash
# Check backup status
kubectl get backup,scheduledbackup -n paperless-ngx

# List available backups
kubectl cnpg status paperless-ngx-db -n paperless-ngx
```

### File Backups (Restic)

- **Schedule**: Daily at 4:00 AM UTC
- **Bucket**: `bc4-do-nyc3-prod-paperless-ngx-files`
- **Encryption**: AES-256-CTR with unique password
- **Retention**: 7 daily, 4 weekly, 6 monthly snapshots

```bash
# Check last backup job
kubectl get jobs -n paperless-ngx -l app.kubernetes.io/name=paperless-ngx-backup

# View backup logs
kubectl logs -n paperless-ngx -l app.kubernetes.io/name=paperless-ngx-backup --tail=100

# Trigger manual backup
kubectl create job --from=cronjob/paperless-ngx-backup manual-backup-$(date +%s) -n paperless-ngx
```

### Restore Procedures

**Restore PostgreSQL:**

```bash
# CNPG handles recovery from backup automatically
# For point-in-time recovery, create a new cluster with recovery stanza
```

**Restore Files:**

```bash
# Get a shell into the paperless pod
kubectl exec -it -n paperless-ngx deploy/paperless-ngx -- /bin/bash

# Install restic (if needed)
apt-get update && apt-get install -y restic

# Set environment
export RESTIC_REPOSITORY=s3:nyc3.digitaloceanspaces.com/bc4-do-nyc3-prod-paperless-ngx-files
export RESTIC_PASSWORD=<from 1password>
export AWS_ACCESS_KEY_ID=<from 1password>
export AWS_SECRET_ACCESS_KEY=<from 1password>

# List snapshots
restic snapshots

# Restore latest snapshot
restic restore latest --target /usr/src/paperless/data
```

## Redis

Redis is used as the Celery task broker for background jobs:
- OCR processing
- Document classification
- Thumbnail generation
- Matching and tagging

**Configuration:**
- Image: `redis:7-alpine`
- No persistence (tasks re-queue on restart)
- Password authentication enabled

Redis does not need to persist data - it only holds task queues. If Redis restarts, pending tasks are lost but can be re-triggered.

## Useful Commands

```bash
# Check all resources
kubectl get all -n paperless-ngx

# Application logs
kubectl logs -n paperless-ngx deploy/paperless-ngx -f

# Database cluster status
kubectl cnpg status paperless-ngx-db -n paperless-ngx

# Redis logs
kubectl logs -n paperless-ngx deploy/paperless-ngx-redis

# ExternalSecret status
kubectl get externalsecret -n paperless-ngx

# Network policy
kubectl get networkpolicy -n paperless-ngx

# PVC usage
kubectl exec -n paperless-ngx deploy/paperless-ngx -- df -h /usr/src/paperless/data
```

## Upgrading

1. Check release notes at https://github.com/paperless-ngx/paperless-ngx/releases

2. Update image tag in values:
   ```yaml
   # kubernetes/apps/paperless-ngx/values.yaml or cluster values
   image:
     tag: "2.21.0"  # New version
   ```

3. Push changes - ArgoCD will sync automatically

4. Verify upgrade:
   ```bash
   kubectl get pods -n paperless-ngx
   kubectl logs -n paperless-ngx deploy/paperless-ngx | head -20
   ```

**Breaking changes to watch for:**
- Database migrations (usually automatic)
- Configuration variable changes
- Python dependency updates

## Troubleshooting

### Pod stuck in Init/CrashLoop

Check if database is ready:
```bash
kubectl get cluster -n paperless-ngx
kubectl cnpg status paperless-ngx-db -n paperless-ngx
```

Check ExternalSecrets:
```bash
kubectl get externalsecret -n paperless-ngx
kubectl describe externalsecret paperless-ngx-admin -n paperless-ngx
```

### OCR not working

Check Redis connection:
```bash
kubectl logs -n paperless-ngx deploy/paperless-ngx | grep -i redis
kubectl logs -n paperless-ngx deploy/paperless-ngx | grep -i celery
```

### Documents not appearing

Check consumer logs (even though we use web upload only):
```bash
kubectl logs -n paperless-ngx deploy/paperless-ngx | grep -i consumer
```

Check media permissions:
```bash
kubectl exec -n paperless-ngx deploy/paperless-ngx -- ls -la /usr/src/paperless/data/media/
```

## References

- [Paperless-ngx Documentation](https://docs.paperless-ngx.com/)
- [Paperless-ngx Configuration](https://docs.paperless-ngx.com/configuration/)
- [Paperless-ngx GitHub](https://github.com/paperless-ngx/paperless-ngx)
- [CloudNativePG Documentation](https://cloudnative-pg.io/docs/)
- [Restic Documentation](https://restic.readthedocs.io/)
