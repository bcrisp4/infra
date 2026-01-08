# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: NEVER COMMIT SECRETS OR STATE FILES

**NEVER commit the following to version control under ANY circumstances:**

- `*.tfstate` / `*.tfstate.backup` - Terraform state files (contain sensitive data)
- `*.tfvars` - Variable files (may contain secrets) - use `.tfvars.example` instead
- `.terraform/` - Provider plugins and local state
- API keys, tokens, passwords, or any credentials
- `kubeconfig` / `talosconfig` files
- Private keys (`*.pem`, `*.key`)
- `.env` files with real values

**Before EVERY commit, verify:**
1. Run `git diff --cached --name-only` to review staged files
2. Check for state files: `git diff --cached --name-only | grep -E '\.(tfstate|tfvars)$'`
3. Grep for secrets: `git diff --cached -S"SECRET" -S"TOKEN" -S"PASSWORD" -S"API_KEY"`

**If secrets are accidentally committed, the repository history must be rewritten immediately.**

## Documentation Structure

This repo has two documentation layers:

1. **`docs/`** - Human-centered canonical documentation. Complete, well-structured for reading.
2. **`CLAUDE.md`** - AI-optimized version for Claude Code context. Summaries + key patterns.

Documentation in `docs/` follows the [Divio documentation system](https://documentation.divio.com/):

| Directory | Purpose | When to use |
|-----------|---------|-------------|
| `docs/tutorials/` | Learning-oriented | Step-by-step guides for beginners |
| `docs/how-to/` | Task-oriented | Recipes for specific goals |
| `docs/reference/` | Information-oriented | Technical descriptions, API docs |
| `docs/explanation/` | Understanding-oriented | Background, rationale, concepts |
| `docs/troubleshooting/` | Problem-oriented | Debugging guides, common issues |
| `docs/tasks/` | Work tracking | Pending tasks, future work |

### Adding New Documentation

1. **Always create human-readable docs first** in the appropriate `docs/{category}/` directory
2. Add an entry to `docs/{category}/README.md` index
3. Add an entry to `docs/README.md` main index
4. Update CLAUDE.md with either:
   - **Short/medium content**: Include the full text (AI needs complete context)
   - **Long/complex docs**: Add a summary of key points + link to full doc

### CLAUDE.md Content Guidelines

CLAUDE.md is AI-optimized, not a copy of docs/. It should contain:
- **Commands and quick patterns** - Full text (AI needs exact syntax)
- **Key gotchas and pitfalls** - Full text (critical for avoiding mistakes)
- **Architecture overviews** - Summaries with links to detailed docs
- **Long troubleshooting guides** - Summary + link to `docs/troubleshooting/`
- **Step-by-step tutorials** - Summary + link to `docs/tutorials/`

Example format for summaries:
```
### Topic Name

Brief summary of key points. Main gotchas or patterns.

See [docs/reference/topic.md](docs/reference/topic.md) for full details.
```

## Commands

```bash
# Scaffold new cluster (creates both terraform and kubernetes directories)
./scripts/new-cluster.sh <cluster-name>

# Scaffold new app
./scripts/new-app.sh <app-name> [cluster-name]

# Bootstrap ArgoCD on a cluster
./scripts/bootstrap-argocd.sh <cluster-name>

# Terraform operations
cd terraform/<dir> && terraform init && terraform plan && terraform apply

# Save terraform plan to file (use .tfplan extension - gitignored)
cd terraform/<dir> && terraform plan -out=plan.tfplan && terraform apply plan.tfplan

# Update Helm dependencies for an app
cd kubernetes/apps/<app> && helm dependency update

# Get full values for a Helm chart
helm show values <chart>  # e.g., helm show values oci://registry/chart
```

## Architecture

This is an infrastructure monorepo for multi-cluster Kubernetes deployments using GitOps.

### Terraform Layer

- **terraform/bootstrap/** - Provisions Terraform Cloud workspaces and variable sets (uses local state)
- **terraform/global/** - Cross-cluster resources (Tailscale ACLs, OAuth clients, 1Password items)
- **terraform/clusters/{cluster}/** - Per-cluster infrastructure (compute, storage, networking)
- **terraform/modules/k8s-cluster/{provider}/** - Reusable provider-specific cluster modules

TFC organization: `bc4`. One workspace per root module.

### Terraform Cloud Configuration

All TFC configuration is managed via `terraform/bootstrap/main.tf`:
- Workspaces and their settings
- Variable sets and their attachments to workspaces
- Workspace variables

To attach a variable set to a workspace, add a `tfe_workspace_variable_set` resource in bootstrap:
```hcl
resource "tfe_workspace_variable_set" "global_onepassword" {
  variable_set_id = tfe_variable_set.onepassword.id
  workspace_id    = tfe_workspace.this["global"].id
}
```

Variable sets:
- `tailscale-credentials` - TAILSCALE_API_KEY, TAILSCALE_TAILNET (attached to: global)
- `digitalocean-credentials` - DIGITALOCEAN_TOKEN, SPACES_* (attached to: do-nyc3-prod)
- `onepassword-credentials` - OP_SERVICE_ACCOUNT_TOKEN, onepassword_vault (attached to: global, do-nyc3-prod)

### Kubernetes Layer

- **kubernetes/apps/{app}/** - Umbrella Helm charts wrapping upstream dependencies. Values namespaced under dependency name.
- **kubernetes/clusters/{cluster}/apps/{app}/** - Per-app cluster config:
  - `config.yaml` - Required. App metadata for ApplicationSet (name, namespace labels)
  - `values.yaml` - Cluster-specific Helm value overrides
- **kubernetes/clusters/{cluster}/argocd/** - ArgoCD bootstrap and manifests (Applications, ApplicationSets)

ArgoCD runs per-cluster and auto-discovers apps via Git files generator scanning `kubernetes/clusters/{cluster}/apps/*/config.yaml`.

### Key Patterns

- Cluster naming: `{provider}-{region}-{env}` (e.g., `do-nyc3-prod`, `htz-fsn1-prod`)
- Provider abbreviations: `htz` (Hetzner), `do` (DigitalOcean), `aws`, `gcp`
- Tailscale auth keys flow: global terraform creates keys -> cluster terraform consumes via remote state
- Apps deploy by creating `config.yaml` + `values.yaml` in `kubernetes/clusters/{cluster}/apps/{app}/`

## Current State

- Active cluster: `do-nyc3-prod` (DigitalOcean NYC3)
- Tailnet: `marlin-tet.ts.net`
- Spaces buckets configured for: Loki, Mimir, Tempo, Pyroscope

## Updating Terraform Provider Versions

To check and update provider versions to the latest, query the Terraform Registry API:

```
# Provider version lookup URLs
https://registry.terraform.io/v1/providers/digitalocean/digitalocean
https://registry.terraform.io/v1/providers/1Password/onepassword
https://registry.terraform.io/v1/providers/tailscale/tailscale
https://registry.terraform.io/v1/providers/hashicorp/tfe

# Terraform releases
https://releases.hashicorp.com/terraform/
```

Files to update when changing versions:
- `.terraform-version` - tfenv version (should match required_version)
- `terraform/bootstrap/main.tf` - tfe provider
- `terraform/global/main.tf` - tailscale provider
- `terraform/clusters/do-nyc3-prod/main.tf` - digitalocean, onepassword providers
- `terraform/clusters/_template/main.tf` - required_version only
- `README.md` - prerequisites section

### Dependabot

Dependabot automatically creates PRs to update Helm chart dependencies and Terraform providers. Configuration is in `.github/dependabot.yml`.

**What it monitors:**
- Helm: `kubernetes/apps/*/Chart.yaml` dependencies
- Terraform: providers in `terraform/bootstrap/`, `terraform/global/`, `terraform/clusters/*` (auto-discovers new clusters)

**Schedule:** Weekly on Mondays

**Testing:** Go to Insights > Dependency graph > Dependabot and click "Check for updates"

See [docs/reference/dependabot.md](docs/reference/dependabot.md) for full configuration details.

## Implementation Notes

- Do not use em dashes in generated content
- Keep configurations minimal - avoid over-engineering
- Prefer explicit configuration over clever automation
- Templates use `_template` naming and are copied when creating new clusters/apps

### Deploying New Apps

**1. Create the umbrella chart** in `kubernetes/apps/{app}/`:
```bash
# Check for latest chart versions
helm repo add <name> <url>
helm repo update
helm search repo <chart> --versions | head -5
```

```yaml
# kubernetes/apps/{app}/Chart.yaml
dependencies:
  - name: external-secrets
    version: "1.2.3"
    repository: "https://charts.external-secrets.io"
```

**2. Create cluster config** in `kubernetes/clusters/{cluster}/apps/{app}/`:
```yaml
# config.yaml - Required for app discovery
name: my-app
namespace: my-app-system  # Optional: override namespace (defaults to name)
namespaceLabels: {}       # Optional: add labels to namespace
namespaceAnnotations: {}  # Optional: add annotations like linkerd.io/inject: enabled
```

```yaml
# values.yaml - Cluster-specific overrides
my-app:
  replicas: 2
```

The app will be auto-discovered and deployed by ArgoCD within a few minutes.

### External Secrets Operator

Key learnings from deploying ESO with 1Password:

1. **API Versions**: ESO 1.x uses `external-secrets.io/v1` API (not v1beta1). Always check docs for correct API version.

2. **1Password SDK Provider**: The `onepasswordSDK` provider requires ESO 1.x. Older 0.x versions use different provider config.

3. **Secret Reference Format**: The onepasswordSDK provider uses `<item>/<field>` format (vault is in ClusterSecretStore):
   ```yaml
   remoteRef:
     key: "<item>/<field>"
   ```
   Example: `my-app-credentials/password`

4. **Memory Limits**: Default chart memory limits (128Mi) are too low and cause OOMKilled. Use at least 256Mi:
   ```yaml
   external-secrets:
     resources:
       limits:
         memory: 256Mi
   ```

5. **CRD Upgrades**: When upgrading ESO from 0.x to 1.x, you may need to delete old CRDs due to conversion webhook conflicts:
   ```bash
   kubectl get crd -o name | grep external-secrets.io | xargs kubectl delete
   ```
   ArgoCD will recreate them with the new version.

6. **ExternalSecret Default Values**: The ESO webhook injects default values that cause ArgoCD diff. Always specify explicitly:
   ```yaml
   remoteRef:
     key: "item/field"
     conversionStrategy: Default
     decodingStrategy: None
     metadataPolicy: None
   ```

7. **1Password Service Account**: Create via CLI, store token in K8s secret before deploying:
   ```bash
   kubectl create namespace external-secrets
   kubectl create secret generic onepassword-token \
     --namespace external-secrets \
     --from-literal=token="$(op service-account create 'name' --vault 'Vault' --permissions read_items --format json | jq -r '.token')"
   ```

8. **1Password Rate Limits**: Service accounts have strict rate limits that ESO can easily hit:
   - 1Password Teams/Families: 1,000 reads/hour (account-wide, not per-token)
   - 1Password Business: 10,000 reads/hour, 50,000/day
   - Check current usage: `op service-account ratelimit <service-account-name>`

   To avoid rate limits:
   - Use `refreshInterval: 24h` (or longer) for secrets that rarely change
   - Set `refreshInterval: 3600` on ClusterSecretStore to reduce validation calls
   - Consider `refreshPolicy: CreatedOnce` for truly static secrets
   - Pod restarts and ArgoCD syncs trigger immediate re-fetches regardless of interval

9. **Force Refresh an ExternalSecret**: To immediately sync after changing a secret in 1Password:
   ```bash
   # Add/update annotation to trigger reconciliation
   kubectl annotate externalsecret <name> -n <namespace> force-sync=$(date +%s) --overwrite

   # Example:
   kubectl annotate externalsecret mimir-s3-credentials -n mimir force-sync=$(date +%s) --overwrite
   ```

### 1Password Terraform Provider

- Use v3.0+ which uses pure SDK (no CLI required) - works in TFC without installing `op`
- Store OAuth credentials with `category = "login"` and use `username`/`password` fields
- The provider uses `OP_SERVICE_ACCOUNT_TOKEN` env var for authentication

### Tailscale Kubernetes Operator

- OAuth client tags must own `tag:k8s` for ingresses to work (operator uses `tag:k8s` by default)
- ACL example: `"tag:k8s" = ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"]`
- If ingresses fail with "requested tags invalid or not permitted", check ACL tag ownership
- Scopes needed: `devices`, `auth_keys`, `routes`, `dns`, `services` (services required for ProxyGroup)

### Tailscale ProxyGroup HA Ingress

ProxyGroup consolidates per-ingress proxies into shared, multi-replica proxies for HA.

**ACL requirements:**
- `tag:k8s-ingress` - Applied to ProxyGroup proxies (owned by operator tags)
- `tag:k8s-services` - Applied to Tailscale Services (owned by operator tags)
- `autoApprovers.services` - Allows `tag:k8s-ingress` to approve `tag:k8s-services`

**Ingress format for ProxyGroup** (different from standard K8s Ingress):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  annotations:
    tailscale.com/proxy-group: ingress-proxies
    tailscale.com/tags: tag:k8s-services
spec:
  ingressClassName: tailscale
  defaultBackend:           # Use defaultBackend, NOT rules with host
    service:
      name: myapp
      port:
        number: 8080
  tls:
    - hosts:
        - myapp             # Hostname only in tls.hosts, not in rules
```

**Key differences from standard Ingress:**
- Uses `defaultBackend` instead of `rules` with `host` field
- Hostname only in `tls.hosts`, NOT in rules (will fail with "rule with host ignored, unsupported")
- No `tls.secretName` - Tailscale provides certs automatically
- Requires `tailscale.com/proxy-group` annotation

**When NOT to use ProxyGroup:**
- **Tailscale Funnel ingresses** - Funnel requires path-based routing (`rules` with `paths`), which ProxyGroup doesn't support. Funnel ingresses use standalone proxies.
- Example: `argocd-webhook-funnel` uses standalone proxy for GitHub webhooks

**Current ingress configuration (do-nyc3-prod):**
| Ingress | Type | Notes |
|---------|------|-------|
| miniflux, grafana, grafana-mcp, argocd-server | ProxyGroup | Shared HA proxies |
| argocd-webhook-funnel | Standalone | Funnel for public webhook endpoint |

**Known issue:** Operator 1.92.x has pod-level resources bug - can't use custom container resources or Linkerd injection until 1.94+.

See [docs/reference/tailscale-operator.md](docs/reference/tailscale-operator.md) for full reference and [docs/how-to/tailscale-proxygroup-ingress.md](docs/how-to/tailscale-proxygroup-ingress.md) for migration guide.

### Tailscale MagicDNS Naming

MagicDNS uses **flat naming only** - no nested subdomains are supported:
- Valid: `argocd-do-nyc3-prod.marlin-tet.ts.net`
- Invalid: `argocd.do-nyc3-prod.marlin-tet.ts.net` (dots create DNS hierarchy)

Naming pattern: `{hostname}.{tailnet}.ts.net`

Use dashes to create logical groupings: `{app}-{cluster}.{tailnet}.ts.net`

For custom subdomain structures, alternatives require additional infrastructure:
- Own domain + split DNS (e.g., `argocd.do-nyc3-prod.internal.example.com`)
- Gateway API + ExternalDNS + cert-manager

### Linkerd Service Mesh

Linkerd provides automatic mTLS between meshed workloads using a sidecar proxy model.

**Architecture:**
- Linkerd control plane runs in `linkerd` namespace
- Certificates managed by cert-manager with a self-signed CA
- Trust bundles distributed via trust-manager to all namespaces
- Sidecar injection controlled via namespace annotations

**Adding a namespace to the mesh:**

Add the annotation to the app's `config.yaml`:

```yaml
# kubernetes/clusters/{cluster}/apps/{app}/config.yaml
name: my-app
namespaceAnnotations:
  linkerd.io/inject: enabled
```

ArgoCD applies this annotation via `managedNamespaceMetadata`. New pods in the namespace will automatically get Linkerd sidecar proxies injected.

**What happens:**
1. ArgoCD creates/updates the namespace with the annotation
2. Linkerd's proxy-injector webhook intercepts pod creation
3. A `linkerd-proxy` sidecar container is added to each pod
4. mTLS is automatically enabled between meshed pods

**Verify pods are in the mesh:**

1. Check namespace has the annotation:
```bash
kubectl get ns <namespace> -o jsonpath='{.metadata.annotations.linkerd\.io/inject}'
# Should output: enabled
```

2. Check pods have 2/2 containers (app + linkerd-proxy):
```bash
kubectl get pods -n <namespace>
# READY column should show 2/2 (or 3/3 for pods with multiple containers)
```

3. Verify mTLS is working with linkerd viz:
```bash
linkerd viz stat deploy -n <namespace>
# Should show MESHED=1/1 and SUCCESS rate
```

4. Check a specific pod has the proxy:
```bash
kubectl get pod -n <namespace> <pod-name> -o jsonpath='{.spec.containers[*].name}'
# Should include "linkerd-proxy"
```

**After adding annotation, restart pods:**
```bash
kubectl rollout restart deployment -n <namespace>
kubectl rollout restart statefulset -n <namespace>
```

**To remove from mesh:** Remove the `namespaceAnnotations` section or set it to `{}`.

**Known issues:**
- cert-manager namespace cannot have Linkerd injection (circular dependency - Linkerd excludes it automatically)
- Tailscale operator proxies require Tailscale 1.94.0+ for Linkerd compatibility (see [docs/tasks/tailscale-operator-1.94-linkerd.md](docs/tasks/tailscale-operator-1.94-linkerd.md))
- Strimzi Kafka requires special Linkerd annotations and a supplementary NetworkPolicy (see [docs/how-to/strimzi-kafka-linkerd.md](docs/how-to/strimzi-kafka-linkerd.md))
- **NetworkPolicies must allow port 4143** for meshed pod-to-pod traffic. Linkerd's inbound proxy listens on port 4143 for mTLS connections. If your NetworkPolicy only allows the application port (e.g., 6379 for Redis, 5432 for PostgreSQL), the Linkerd proxy-to-proxy connection will fail with "connect timed out". Add port 4143 alongside each application port in egress rules:
  ```yaml
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: my-redis
      ports:
        - port: 6379    # Application port
        - port: 4143    # Linkerd inbound proxy
  ```

### Linkerd Edge Releases

We use Linkerd Edge releases (not stable) because:
- Open-source stable releases stopped after 2.14 (February 2024)
- Edge releases include native sidecar support (fixes Jobs never completing)
- Edge releases get all bugfixes and security patches

**Version format:** `edge-YY.MM.N` (e.g., `edge-25.12.3`)

**Native sidecars:** Enabled via `proxy.nativeSidecar: true` in values.yaml. Requires Kubernetes 1.29+. This fixes the issue where Jobs with Linkerd sidecars never complete because the proxy keeps running after the main container exits.

**Upgrading Linkerd Edge:**

1. Check for new releases and any "not recommended" warnings:
```bash
# List available versions
helm search repo linkerd-edge/linkerd-control-plane --versions | head -10

# Check release notes for issues
# https://github.com/linkerd/linkerd2/releases
# https://linkerd.io/blog/ (monthly roundups)
```

2. Look for breaking changes in release notes - edge releases are NOT semantically versioned

3. Update Chart.yaml versions:
```yaml
# kubernetes/apps/linkerd/Chart.yaml
dependencies:
  - name: linkerd-crds
    version: "~2025.12"  # Update to new month
    repository: https://helm.linkerd.io/edge
  - name: linkerd-control-plane
    version: "~2025.12"  # Update to new month
    repository: https://helm.linkerd.io/edge
```

4. Update dependencies and push:
```bash
cd kubernetes/apps/linkerd && helm dependency update
cd kubernetes/apps/linkerd-viz && helm dependency update
```

**Key resources:**
- Release notes: https://github.com/linkerd/linkerd2/releases
- Monthly roundups: https://linkerd.io/blog/ (search "Edge Release Roundup")
- Upgrade guide: https://linkerd.io/2-edge/tasks/upgrade/

**Risk mitigation:**
- Check GitHub releases for "not recommended" labels before upgrading
- Read the monthly roundup blog posts for known issues
- Test in non-production first if possible
- Edge releases marked "not recommended" should be skipped

### ArgoCD Manifests

The `argocd/manifests/` directory contains:
- `argocd.yaml` - Application for ArgoCD self-management
- `apps.yaml` - ApplicationSet for cluster app discovery

**Testing locally before pushing:**
```bash
# Validate YAML syntax (catches structural errors)
yq eval '.' kubernetes/clusters/*/argocd/manifests/*.yaml > /dev/null

# Dry-run with kubectl (validates K8s schema)
kubectl apply --dry-run=client -f kubernetes/clusters/*/argocd/manifests/*.yaml
```

**Key limitations:**
- Go templates only work on string fields, not object fields
- Control structures (`{{- range }}`, `{{- if }}`) break YAML parsing when used directly in templates
- Use `templatePatch` for conditional configuration (supports full Go templating)

**Per-app namespace labels and annotations:**

Apps use `config.yaml` files that the ApplicationSet reads via Git files generator:
```yaml
# kubernetes/clusters/{cluster}/apps/{app}/config.yaml
name: my-app
namespaceLabels:
  example.com/team: platform  # Optional: adds labels to app namespace
namespaceAnnotations:
  linkerd.io/inject: enabled  # Optional: adds annotations to app namespace
```

The `templatePatch` conditionally applies these to `managedNamespaceMetadata`. This works because `templatePatch` is a string field that gets Go template processing before being applied as a patch.

**Common errors:**
- `yaml: line X: could not find expected ':'` - Template control structures at wrong indentation or outside templatePatch
- Go template syntax (`{{ .path.basename }}`) should NOT use Helm escaping backticks when the YAML is applied directly (not via Helm)
- If you see "duplicate name" errors with literal `{{ ... }}`, check if backtick escaping was incorrectly added

### ArgoCD GitHub Webhooks

GitHub webhooks enable instant sync on push instead of 3-minute polling. The webhook endpoint is exposed publicly via Tailscale Funnel while keeping the ArgoCD UI private.

**Important:** This uses a **standalone proxy**, not ProxyGroup. Funnel requires path-based routing which ProxyGroup doesn't support.

**Current setup (do-nyc3-prod):**
- Webhook URL: `https://argocd-webhook-do-nyc3-prod.marlin-tet.ts.net/api/webhook`
- Configured in: GitHub repo Settings > Webhooks
- Secret stored in: `argocd-secret` (key: `webhook.github.secret`)

**How it works:**
1. Tailscale Funnel exposes only `/api/webhook` publicly via `argocd-webhook-{cluster}` ingress
2. GitHub sends push events to this endpoint
3. ArgoCD immediately refreshes affected applications

**Note:** Apps sync automatically on push, so manual syncing should not be necessary under normal circumstances.

**Files involved:**
- `kubernetes/clusters/{cluster}/argocd/bootstrap/templates/webhook-funnel-ingress.yaml` - Funnel ingress
- `kubernetes/clusters/{cluster}/argocd/bootstrap/values.yaml` - Webhook secret in `configs.secret.extra`
- `terraform/global/tailscale.tf` - ACL with `funnel` attribute for `tag:k8s`

**Adding webhooks to a new cluster:**
1. Generate secret: `openssl rand -hex 32`
2. Add to values.yaml: `configs.secret.extra.webhook.github.secret: "<secret>"`
3. Create webhook-funnel-ingress.yaml template (copy from existing cluster)
4. Configure GitHub webhook with the cluster's funnel URL

See [docs/how-to/argocd-webhook-tailscale-funnel.md](docs/how-to/argocd-webhook-tailscale-funnel.md) for detailed setup guide.

### CloudNativePG Barman Cloud Plugin

The Barman Cloud plugin enables PostgreSQL backup to S3-compatible object storage (like DigitalOcean Spaces).

**Plugin architecture:**
- Plugin runs as a Deployment in `cnpg-system` namespace
- CNPG operator discovers plugin via Service annotations (`cnpg.io/pluginName`, etc.)
- mTLS between operator and plugin via cert-manager certificates
- Plugin injects sidecar containers into CNPG Cluster pods for WAL archiving

**Template structure:**
- `kubernetes/apps/cloudnative-pg/templates/barman-cloud-plugin.yaml` - Templated version of official manifest
- `kubernetes/apps/cloudnative-pg/templates/barman-cloud-crds.yaml` - ObjectStore CRD
- `kubernetes/apps/cloudnative-pg/files/barman-cloud-plugin-vX.Y.Z.yaml` - Reference copy of official manifest

**Updating the plugin:**

1. Check for new releases at https://github.com/cloudnative-pg/plugin-barman-cloud/releases

2. Download the new official manifest:
```bash
VERSION=v0.11.0  # Update to desired version
curl -sL "https://raw.githubusercontent.com/cloudnative-pg/plugin-barman-cloud/refs/tags/${VERSION}/manifest.yaml" \
  > kubernetes/apps/cloudnative-pg/files/barman-cloud-plugin-${VERSION}.yaml
```

3. Compare key sections for breaking changes:
```bash
# Compare RBAC rules
diff <(grep -A20 "kind: ClusterRole" files/barman-cloud-plugin-v0.10.0.yaml) \
     <(grep -A20 "kind: ClusterRole" files/barman-cloud-plugin-${VERSION}.yaml)

# Compare Deployment args and env
diff <(grep -A30 "kind: Deployment" files/barman-cloud-plugin-v0.10.0.yaml) \
     <(grep -A30 "kind: Deployment" files/barman-cloud-plugin-${VERSION}.yaml)
```

4. Update the template if there are structural changes (new args, env vars, RBAC rules)

5. Update `barmanCloudPlugin.version` in values.yaml:
```yaml
barmanCloudPlugin:
  version: "v0.11.0"
```

6. Update the CRD if needed (compare `objectstores.barmancloud.cnpg.io` in the manifest)

7. Test deployment:
```bash
helm template kubernetes/apps/cloudnative-pg -f kubernetes/clusters/do-nyc3-prod/apps/cloudnative-pg/values.yaml
```

**Configuring backups for an app:**

1. Create ExternalSecret for S3 credentials (pulls from 1Password)
2. Create ObjectStore CRD pointing to S3 bucket
3. Create ScheduledBackup CRD with cron schedule
4. Add `plugins` section to CNPG Cluster spec for WAL archiving

See `kubernetes/apps/grafana/templates/backup-*.yaml` for examples.

**Creating S3 backup buckets:**

Backup buckets and credentials are managed via Terraform in `terraform/clusters/do-nyc3-prod/spaces.tf`:

1. Add entry to `backup_buckets` local:
```hcl
n8n-postgres = {
  name        = "${local.bucket_prefix}-n8n-postgres-backups"
  description = "n8n PostgreSQL database backups"
}
```

2. Run `terraform plan` and `terraform apply` - this automatically creates:
   - DigitalOcean Spaces bucket
   - Per-bucket access key via `digitalocean_spaces_key`
   - 1Password item via `onepassword_item.backup_credentials` (named `{cluster}-{key}-s3`)

3. Reference in Kubernetes values.yaml:
```yaml
backup:
  s3:
    itemName: do-nyc3-prod-n8n-postgres-s3  # Matches 1Password item title
    bucket: bc4-do-nyc3-prod-n8n-postgres-backups
    endpoint: nyc3.digitaloceanspaces.com
```

**Troubleshooting:**

- Plugin not discovered: Check Service has `cnpg.io/pluginName` label and annotations
- TLS errors: Verify cert-manager Certificates are Ready
- RBAC errors: Compare ClusterRole with official manifest
- Backup failures: Check ObjectStore status and sidecar logs

### Grafana Datasource Provisioning

Grafana datasources are provisioned via the Helm chart's `datasources` value, which creates a ConfigMap mounted at `/etc/grafana/provisioning/datasources/`.

**Key pitfalls:**

1. **Name is the identifier**: Grafana uses datasource `name` as the primary identifier. Changing the name creates a NEW datasource instead of updating the existing one. The old datasource remains in the database.

2. **Don't use `deleteDatasources`**: The `deleteDatasources` directive crashes Grafana if the datasource to delete doesn't exist:
   ```
   Datasource provisioning error: data source not found
   ```
   Avoid using it - manually delete old datasources via the UI instead.

3. **Don't use `uid` for existing datasources**: If a datasource already exists without a uid (or with a different uid), adding `uid` to provisioning can cause conflicts and crashes. Only use `uid` for new datasources.

4. **Datasources persist in database**: Even though provisioning is via ConfigMap, Grafana stores datasources in its database (PostgreSQL). The ConfigMap is only read on startup to sync state.

**Example Mimir/Prometheus datasource:**

```yaml
grafana:
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
        - name: mimir-do-nyc3-prod
          type: prometheus
          access: proxy
          url: http://mimir-gateway.mimir.svc.cluster.local/prometheus
          isDefault: true
          editable: false
          jsonData:
            prometheusType: Mimir
            prometheusVersion: 2.9.1
            timeInterval: 30s
            cacheLevel: High
            incrementalQuerying: true
            incrementalQueryOverlapWindow: 10m
            httpHeaderName1: X-Scope-OrgID
          secureJsonData:
            httpHeaderValue1: prod
```

**Valid `prometheusVersion` values for Mimir:**

The version dropdown uses specific values (from Grafana source code):
- `2.0.0` through `2.9.0` for specific minor versions
- `2.9.1` = "> 2.9.x" (use this for Mimir 3.0+)

These are NOT actual Mimir versions - they're Grafana's internal version identifiers that enable specific API features.

**Key `jsonData` fields:**

| Field | Description |
|-------|-------------|
| `prometheusType` | `Prometheus`, `Mimir`, `Cortex`, or `Thanos` |
| `prometheusVersion` | Version identifier (see above) |
| `timeInterval` | Scrape interval (e.g., `30s`) - should match your scraper config |
| `cacheLevel` | `Low`, `Medium`, `High`, or `None` - higher is better for high cardinality |
| `incrementalQuerying` | `true` to cache query results and only fetch new data |
| `incrementalQueryOverlapWindow` | Overlap window for incremental queries (e.g., `10m`) |
| `httpHeaderName1` / `httpHeaderValue1` | Custom headers (use `secureJsonData` for sensitive values) |

**Renaming a datasource:**

If you need to rename a datasource:
1. Update the provisioning config with the new name
2. Deploy and let Grafana create the new datasource
3. Manually delete the old datasource via Grafana UI (Connections > Data sources)
4. Update any dashboards that reference the old datasource name

### Grafana Datasources

Available datasources for use with the Grafana MCP tools:

| Name | UID | Type | Description |
|------|-----|------|-------------|
| `mimir-do-nyc3-prod` | `PDFDDA34E6E7D2823` | prometheus | Mimir metrics (PromQL) |
| `loki-do-nyc3-prod` | `PF99E8F4CDB5B6FB2` | loki | Loki logs (LogQL) |
| `tempo-do-nyc3-prod` | `P3FE448E25097FAF8` | tempo | Tempo traces (TraceQL) |

**Keeping this list updated:**

When datasources are added or removed, update this table. To get the current list:
1. Use the `mcp__grafana-mcp-do-nyc3-prod__list_datasources` tool
2. Or query Grafana API: `curl -s https://grafana-do-nyc3-prod.../api/datasources | jq '.[] | {name, uid, type}'`

**Usage with MCP tools:**

Most Grafana MCP query tools require a `datasourceUid` parameter:
```
# Query Prometheus/Mimir metrics
mcp__grafana-mcp-do-nyc3-prod__query_prometheus(datasourceUid: "PDFDDA34E6E7D2823", expr: "up", ...)

# Query Loki logs
mcp__grafana-mcp-do-nyc3-prod__query_loki_logs(datasourceUid: "PF99E8F4CDB5B6FB2", logql: "{k8s_namespace_name=\"argocd\"}", ...)
```

### Mimir Tenant Endpoint

Mimir requires the `X-Scope-OrgID` header for multi-tenancy. Some clients (like linkerd-viz) cannot set custom HTTP headers. For these clients, use the gateway's tenant endpoint.

**How it works:**

The Mimir gateway nginx is configured with a `/tenant/{tenant}/` path that adds the `X-Scope-OrgID` header before forwarding to internal Mimir components.

```
Client (no header support)
    |
    v
mimir-gateway/tenant/prod/ (adds X-Scope-OrgID: prod)
    |
    v
Mimir query components
```

**Configuration:**

Add serverSnippet to the gateway in cluster values:

```yaml
# kubernetes/clusters/{cluster}/apps/mimir/values.yaml
mimir-distributed:
  gateway:
    nginx:
      config:
        serverSnippet: |
          location /tenant/prod/ {
            proxy_pass http://localhost:8080/;
            proxy_set_header X-Scope-OrgID prod;
            proxy_http_version 1.1;
          }
```

**Usage example (linkerd-viz):**

```yaml
# kubernetes/clusters/{cluster}/apps/linkerd-viz/values.yaml
linkerd-viz:
  prometheus:
    enabled: false
  prometheusUrl: http://mimir-gateway.mimir.svc.cluster.local/tenant/prod/prometheus
```

### Logging with Loki

Logs are collected by OpenTelemetry Collector DaemonSets (`otel-logs`) and shipped to Loki via native OTLP.

**Architecture:**
- `otel-logs` DaemonSet runs on each node
- Reads container logs from `/var/log/pods` via filelog receiver
- Enriches with Kubernetes metadata (namespace, pod, container, deployment, etc.)
- Ships to Loki gateway via OTLP with tenant header `X-Scope-OrgID: prod`

**Key labels for querying:**
- `cluster` - Cluster identifier (e.g., `do-nyc3-prod`)
- `log_source` - Always `pods` (host logs not yet implemented)
- `k8s_namespace_name`, `k8s_pod_name`, `k8s_container_name` - Kubernetes metadata
- `k8s_deployment_name`, `k8s_statefulset_name`, `k8s_daemonset_name` - Workload type
- `detected_level` - Auto-detected log level (error, warn, info, debug)

**Quick LogQL examples:**

```logql
# All logs from a namespace
{k8s_namespace_name="argocd"}

# Error logs
{k8s_namespace_name="mimir"} |= "error"

# Logs from specific deployment
{k8s_deployment_name="loki-gateway"}

# Filter by detected level
{k8s_namespace_name="grafana", detected_level="error"}
```

**Limitations:**
- Only pod logs are collected (no host/systemd logs)
- Host logs require a custom collector image with `journalctl` binary

See [docs/reference/logging-architecture.md](docs/reference/logging-architecture.md) for system design and [docs/how-to/query-logs.md](docs/how-to/query-logs.md) for query examples.

### Tracing with Tempo

Traces are stored in Grafana Tempo with S3-compatible storage (DigitalOcean Spaces).

**Architecture:**
- `tempo-distributed` Helm chart in distributed mode
- S3 storage: `bc4-do-nyc3-prod-tempo` bucket
- Multi-tenant with `X-Scope-OrgID: prod` header
- Metrics generator enabled for service graphs and span metrics

**Metrics Generator:**

The metrics generator derives metrics from ingested traces and writes them to Mimir:

| Processor | Metrics Generated | Purpose |
|-----------|-------------------|---------|
| service-graphs | `traces_service_graph_*` | Service relationship graphs |
| span-metrics | `traces_spanmetrics_calls_total`, `traces_spanmetrics_latency` | RED metrics per service/operation |

**Grafana Features:**
- **Service Graph**: Visualize service dependencies (requires traces with service names)
- **Trace to Logs**: Jump from trace spans to correlated logs in Loki
- **Trace to Metrics**: Jump from traces to related Mimir metrics

**Quick TraceQL examples:**

```traceql
# Find traces by service name
{ resource.service.name = "my-service" }

# Find traces with errors
{ status = error }

# Find slow traces (duration > 1s)
{ duration > 1s }

# Combine filters
{ resource.service.name = "api-gateway" && status = error && duration > 500ms }
```

**Key Gotcha - tempo-distributed chart:**

Do NOT use `global.extraArgs` or `global.extraEnvFrom` in the tempo-distributed chart. These apply to ALL components including memcached, which doesn't understand Tempo's `-config.expand-env=true` flag. Instead, configure `extraArgs` and `extraEnvFrom` per-component (ingester, distributor, querier, etc.).

See [docs/reference/tracing-architecture.md](docs/reference/tracing-architecture.md) for full architecture details including OTLP endpoints and service graph configuration.

### Trace Ingestion

Traces are collected by OpenTelemetry Collector DaemonSets (`otel-traces`) and shipped to Tempo via OTLP.

**Architecture:**
- `otel-traces` DaemonSet runs on each node (same pattern as otel-logs)
- Service with `internalTrafficPolicy: Local` for node-local routing
- Enriches with Kubernetes metadata (namespace, pod, container, deployment, etc.)
- Ships to Tempo gateway via OTLP gRPC with tenant header `X-Scope-OrgID: prod`
- Linkerd mesh injection for mTLS

**Application Configuration:**

Applications send traces to the OTel collector via OTLP:

```bash
# gRPC (recommended)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-traces.otel-traces.svc.cluster.local:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc

# HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-traces.otel-traces.svc.cluster.local:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

**Processor Pipeline:**
```
OTLP Receiver -> memory_limiter -> k8sattributes -> resource (cluster label) -> batch -> Tempo
```

**Sampling:** No sampling enabled by default. All traces are kept. If volume becomes an issue, add probabilistic sampling to the collector config.

See [docs/reference/tracing-architecture.md](docs/reference/tracing-architecture.md) for full collector configuration and sampling options.

### Push-based Metrics with otel-metrics-push

Push-based metrics are collected by OpenTelemetry Collector DaemonSets (`otel-metrics-push`) and shipped to Mimir via OTLP.

**Architecture:**
- `otel-metrics-push` DaemonSet runs on each node (same pattern as otel-traces)
- Service with `internalTrafficPolicy: Local` for node-local routing
- Enriches with Kubernetes metadata (namespace, pod, container, deployment, etc.)
- Ships to Mimir gateway via OTLP HTTP with tenant header `X-Scope-OrgID: prod`
- Linkerd mesh injection for mTLS

**Application Configuration:**

Applications send metrics to the OTel collector via OTLP:

```bash
# gRPC (recommended)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-metrics-push.otel-metrics-push.svc.cluster.local:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc

# HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-metrics-push.otel-metrics-push.svc.cluster.local:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

**Processor Pipeline:**
```
OTLP Receiver -> memory_limiter -> k8sattributes -> resource (cluster label) -> batch -> Mimir
```

### Miniflux RSS Reader

Miniflux is deployed on do-nyc3-prod with CNPG PostgreSQL (2 instances for HA), Tailscale ingress, Linkerd mesh, and Barman Cloud backups.

**Files:**
- `kubernetes/apps/miniflux/` - Umbrella chart
- `kubernetes/clusters/do-nyc3-prod/apps/miniflux/` - Cluster config

**Key tips from migration:**

1. **pg_restore needs `--clean --if-exists`**: Miniflux runs migrations on startup, creating schema before restore. Use these flags to drop existing objects first.

2. **Use `postgres` user for psql**: The `miniflux` user has peer auth issues. Use `postgres` instead:
   ```bash
   kubectl exec -n miniflux miniflux-db-1 -c postgres -- psql -U postgres -d miniflux
   ```

3. **Speed up replica join**: New replicas wait for checkpoint (up to 15 min). Trigger manually:
   ```bash
   kubectl exec -n miniflux miniflux-db-1 -c postgres -- psql -U postgres -c "CHECKPOINT;"
   ```

4. **Horizontal scaling supported** via `DISABLE_SCHEDULER_SERVICE=1` (HTTP-only) and `DISABLE_HTTP_SERVICE=1` (scheduler-only), but single instance is recommended for personal use.

5. **RUN_MIGRATIONS=1 is safe** with multiple instances - Miniflux uses PostgreSQL advisory locks.

See [docs/reference/miniflux.md](docs/reference/miniflux.md) for full deployment reference.

### n8n Workflow Automation

n8n is deployed on do-nyc3-prod with CNPG PostgreSQL, Tailscale ingress, Linkerd mesh, and Barman Cloud backups.

**Files:**
- `kubernetes/apps/n8n/` - Umbrella chart wrapping upstream 8gears Helm chart
- `kubernetes/clusters/do-nyc3-prod/apps/n8n/` - Cluster config

**Key configuration:**

1. **PostgreSQL via environment variables**: n8n uses `DB_TYPE=postgresdb` and `DB_POSTGRESDB_*` env vars. The password is injected from CNPG-generated secret `n8n-db-app`.

2. **Encryption key required**: n8n encrypts stored credentials with `N8N_ENCRYPTION_KEY`. This key must remain consistent - changing it makes existing credentials unreadable. Stored in 1Password as `n8n-encryption-key` with field `key`.

3. **Single replica only**: Multiple replicas require n8n enterprise license. Use `replicaCount: 1`.

4. **Metrics enabled**: Prometheus scraping configured on port 5678 at `/metrics`.

**Upstream chart structure:**

The 8gears n8n chart uses nested config under `n8n.main.config` which converts to environment variables:
```yaml
n8n:
  main:
    config:
      db:
        type: postgresdb
        postgresdb:
          host: n8n-db-rw
    extraEnv:
      DB_POSTGRESDB_PASSWORD:
        valueFrom:
          secretKeyRef:
            name: n8n-db-app
            key: password
```

**Initial setup note:** n8n requires manual owner account setup on first access (no env var automation available). Credentials persist in PostgreSQL.

**Future enhancements:**
- Tailscale Funnel for public webhook endpoint (for external integrations)

See [docs/reference/n8n.md](docs/reference/n8n.md) for full deployment reference.
