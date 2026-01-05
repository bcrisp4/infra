# CloudNativePG Barman Cloud Plugin

Reference for PostgreSQL backups using the Barman Cloud plugin with S3-compatible object storage.

## Overview

The Barman Cloud plugin enables PostgreSQL backup to S3-compatible storage (like DigitalOcean Spaces).

## Architecture

- Plugin runs as a Deployment in `cnpg-system` namespace
- CNPG operator discovers plugin via Service annotations (`cnpg.io/pluginName`, etc.)
- mTLS between operator and plugin via cert-manager certificates
- Plugin injects sidecar containers into CNPG Cluster pods for WAL archiving

## Template Structure

| File | Purpose |
|------|---------|
| `kubernetes/apps/cloudnative-pg/templates/barman-cloud-plugin.yaml` | Templated version of official manifest |
| `kubernetes/apps/cloudnative-pg/templates/barman-cloud-crds.yaml` | ObjectStore CRD |
| `kubernetes/apps/cloudnative-pg/files/barman-cloud-plugin-vX.Y.Z.yaml` | Reference copy of official manifest |

## Updating the Plugin

### 1. Check for new releases

https://github.com/cloudnative-pg/plugin-barman-cloud/releases

### 2. Download the new manifest

```bash
VERSION=v0.11.0  # Update to desired version
curl -sL "https://raw.githubusercontent.com/cloudnative-pg/plugin-barman-cloud/refs/tags/${VERSION}/manifest.yaml" \
  > kubernetes/apps/cloudnative-pg/files/barman-cloud-plugin-${VERSION}.yaml
```

### 3. Compare for breaking changes

```bash
# Compare RBAC rules
diff <(grep -A20 "kind: ClusterRole" files/barman-cloud-plugin-v0.10.0.yaml) \
     <(grep -A20 "kind: ClusterRole" files/barman-cloud-plugin-${VERSION}.yaml)

# Compare Deployment args and env
diff <(grep -A30 "kind: Deployment" files/barman-cloud-plugin-v0.10.0.yaml) \
     <(grep -A30 "kind: Deployment" files/barman-cloud-plugin-${VERSION}.yaml)
```

### 4. Update template and values

If structural changes exist, update the template. Then update values.yaml:

```yaml
barmanCloudPlugin:
  version: "v0.11.0"
```

### 5. Update CRD if needed

Compare `objectstores.barmancloud.cnpg.io` in the manifest.

### 6. Test deployment

```bash
helm template kubernetes/apps/cloudnative-pg -f kubernetes/clusters/do-nyc3-prod/apps/cloudnative-pg/values.yaml
```

## Configuring Backups for an App

1. Create ExternalSecret for S3 credentials (pulls from 1Password)
2. Create ObjectStore CRD pointing to S3 bucket
3. Create ScheduledBackup CRD with cron schedule
4. Add `plugins` section to CNPG Cluster spec for WAL archiving

See `kubernetes/apps/grafana/templates/backup-*.yaml` for examples.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Plugin not discovered | Missing Service annotations | Check `cnpg.io/pluginName` label and annotations |
| TLS errors | Invalid certificates | Verify cert-manager Certificates are Ready |
| RBAC errors | Outdated ClusterRole | Compare with official manifest |
| Backup failures | Configuration issues | Check ObjectStore status and sidecar logs |

## Related

- [External Secrets Operator](external-secrets.md) - For S3 credentials
