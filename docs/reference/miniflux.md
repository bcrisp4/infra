# Miniflux RSS Reader

Miniflux is a minimalist, self-hosted RSS reader deployed on do-nyc3-prod.

## Architecture

```
                                   +------------------+
                                   |   Tailscale      |
                                   |   (Ingress)      |
                                   +--------+---------+
                                            |
                                            v
+------------------+              +------------------+
|   1Password      |  Secrets    |    Miniflux      |
|   (via ESO)      +------------>|    Deployment    |
+------------------+              +--------+---------+
                                            |
                                            v
                                 +--------------------+
                                 |   CloudNativePG    |
                                 |   miniflux-db      |
                                 | (Primary+Standby)  |
                                 +--------------------+
                                            |
                                            v
                                 +--------------------+
                                 |  DigitalOcean      |
                                 |  Spaces (Backups)  |
                                 +--------------------+
```

**Components:**
- **Miniflux**: Single deployment pod handling HTTP and background feed polling
- **CloudNativePG**: PostgreSQL cluster with streaming replication (2 instances)
- **Tailscale Ingress**: Private access via `miniflux-do-nyc3-prod.marlin-tet.ts.net`
- **Linkerd**: Service mesh for mTLS between pods
- **Barman Cloud**: Daily backups to DigitalOcean Spaces

## Files

| Path | Purpose |
|------|---------|
| `kubernetes/apps/miniflux/` | Umbrella chart (templates, values) |
| `kubernetes/clusters/do-nyc3-prod/apps/miniflux/config.yaml` | App discovery config |
| `kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml` | Cluster-specific values |
| `terraform/clusters/do-nyc3-prod/spaces.tf` | Backup bucket definition |

## Configuration

### Key Values

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/miniflux/values.yaml

image:
  tag: "2.2.15"

config:
  baseUrl: https://miniflux-do-nyc3-prod.marlin-tet.ts.net
  pollingFrequency: 60        # Minutes between scheduler runs
  pollingScheduler: entry_frequency  # Adapts to feed update patterns
  workerPoolSize: 16          # Concurrent feed fetchers
  logLevel: info

database:
  instances: 2            # Primary + standby for HA
  storage:
    size: 5Gi

backup:
  enabled: true
  retentionPolicy: "28d"
```

### Polling Scheduler

Miniflux supports two scheduler modes:

| Scheduler | Behavior |
|-----------|----------|
| `round_robin` | Polls all feeds equally in rotation |
| `entry_frequency` | Adapts polling interval based on each feed's update frequency |

**entry_frequency** (recommended) is more efficient - frequently updated feeds are polled more often, while dormant feeds are polled less.

Related settings (with defaults):
- `SCHEDULER_ENTRY_FREQUENCY_MIN_INTERVAL`: 5 minutes
- `SCHEDULER_ENTRY_FREQUENCY_MAX_INTERVAL`: 1440 minutes (24 hours)
- `BATCH_SIZE`: 100 feeds per scheduler run
- `HTTP_CLIENT_TIMEOUT`: 30 seconds

### Environment Variables

Miniflux configuration is passed via environment variables in the deployment:

| Variable | Source | Description |
|----------|--------|-------------|
| `DATABASE_URL` | CNPG Secret (`miniflux-db-app`) | PostgreSQL connection string |
| `ADMIN_USERNAME` | ExternalSecret (`miniflux-admin`) | Initial admin username |
| `ADMIN_PASSWORD` | ExternalSecret (`miniflux-admin`) | Initial admin password |
| `RUN_MIGRATIONS` | Values | Run DB migrations on startup (default: 1) |
| `CREATE_ADMIN` | Values | Create admin user if not exists (default: 1) |
| `POLLING_SCHEDULER` | Values | Scheduler mode: `round_robin` or `entry_frequency` |
| `WORKER_POOL_SIZE` | Values | Concurrent feed fetchers (default: 16) |

## Horizontal Scaling

Miniflux supports running multiple instances via configuration flags.

### Architecture Options

**Single Instance (Current)**
- One pod handles both HTTP requests and background feed polling
- Simpler architecture, adequate for personal use

**Multi-Instance (If Needed)**
- Multiple HTTP instances with `DISABLE_SCHEDULER_SERVICE=1`
- Single scheduler instance with `DISABLE_HTTP_SERVICE=1`
- All instances share the same PostgreSQL database

### Configuration Variables

| Variable | Purpose |
|----------|---------|
| `DISABLE_SCHEDULER_SERVICE` | Set to `1` to disable background feed polling |
| `DISABLE_HTTP_SERVICE` | Set to `1` to disable web server |
| `WORKER_POOL_SIZE` | Number of concurrent feed fetchers (default: 16) |

### Migration Safety

`RUN_MIGRATIONS=1` is safe with multiple instances. Miniflux uses PostgreSQL advisory locks to prevent concurrent migrations.

### Recommendation

Keep single instance unless you need:
- Zero-downtime HTTP during pod restarts
- High concurrent user load

Database HA (2 CNPG instances) provides more valuable resilience for a personal RSS reader.

## Database HA

The PostgreSQL cluster runs with 2 instances for high availability.

### How It Works

- **miniflux-db-1**: Primary (read-write)
- **miniflux-db-2**: Standby with async streaming replication
- **miniflux-db-rw** Service: Always routes to current primary
- CNPG handles automatic failover if primary fails
- Pod anti-affinity spreads instances across nodes

### Verify Replication

```bash
kubectl cnpg status miniflux-db -n miniflux
```

Look for:
- `Status: Cluster in healthy state`
- `Ready instances: 2`
- `Streaming Replication status` showing both instances with 0 lag

## Backups

Daily backups via Barman Cloud Plugin to DigitalOcean Spaces.

- **Schedule**: Daily at 3:00 AM UTC
- **Retention**: 28 days
- **Bucket**: `bc4-do-nyc3-prod-miniflux-postgres-backups`
- **WAL Archiving**: Continuous, enables point-in-time recovery

### Check Backup Status

```bash
# List backups
kubectl get backup -n miniflux

# Check backup health in cluster status
kubectl cnpg status miniflux-db -n miniflux
```

## Tips and Tricks

### Database Migration (pg_dump/pg_restore)

When migrating data to a new CNPG cluster:

1. **Use `--clean --if-exists` flags**: Miniflux runs migrations on startup, creating schema before you can restore. The `--clean` flag drops existing objects first.

   ```bash
   # Export from source
   kubectl exec -n miniflux <source-pod> -c postgres -- \
     pg_dump -Fc -d miniflux > miniflux.dump

   # Restore to target (note the flags)
   kubectl exec -i -n miniflux <target-pod> -c postgres -- \
     pg_restore --no-owner --role=miniflux --clean --if-exists \
     -d miniflux --verbose < miniflux.dump
   ```

2. **Use `postgres` user for psql**: The `miniflux` database user uses peer authentication which can cause issues. Use `postgres` user instead:

   ```bash
   kubectl exec -n miniflux miniflux-db-1 -c postgres -- \
     psql -U postgres -d miniflux -c "SELECT count(*) FROM entries;"
   ```

### Speed Up Replica Join

When adding a new PostgreSQL replica, the join process waits for a checkpoint. With low write activity, this can take up to `checkpoint_timeout` (15 minutes).

Trigger a manual checkpoint to speed it up:

```bash
kubectl exec -n miniflux miniflux-db-1 -c postgres -- \
  psql -U postgres -c "CHECKPOINT;"
```

### cnpg kubectl Plugin

The `kubectl cnpg` plugin provides useful shortcuts:

```bash
# Cluster status with replication details
kubectl cnpg status miniflux-db -n miniflux

# Interactive psql session
kubectl cnpg psql miniflux-db -n miniflux

# Note: cnpg psql with -c flag may fail due to TTY issues
# Use kubectl exec directly for non-interactive queries
```

### Linkerd Mesh

The namespace has `linkerd.io/inject: enabled` annotation. All pods get Linkerd sidecar proxies automatically.

Verify pods are meshed (should show 2/2 or 3/3 containers):

```bash
kubectl get pods -n miniflux
```

## Useful Commands

```bash
# Check all resources
kubectl get all -n miniflux

# Database cluster status
kubectl cnpg status miniflux-db -n miniflux

# Application logs
kubectl logs -n miniflux -l app.kubernetes.io/name=miniflux

# Database logs
kubectl logs -n miniflux miniflux-db-1 -c postgres

# ExternalSecret status
kubectl get externalsecret -n miniflux

# Backup status
kubectl get backup,scheduledbackup,objectstore -n miniflux
```

## References

- [Miniflux Documentation](https://miniflux.app/docs/)
- [Miniflux Configuration](https://miniflux.app/docs/configuration.html)
- [CloudNativePG Emergency Backup](https://cloudnative-pg.io/docs/devel/troubleshooting/#emergency-backup)
