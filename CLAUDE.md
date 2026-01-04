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

Use pessimistic constraints (`~> X.Y`) pinned to minor version for stability while allowing patches.

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

Use pessimistic constraints (`~X.Y`) pinned to latest minor version:
```yaml
# kubernetes/apps/{app}/Chart.yaml
dependencies:
  - name: external-secrets
    version: "~1.2"
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

### 1Password Terraform Provider

- Use v3.0+ which uses pure SDK (no CLI required) - works in TFC without installing `op`
- Store OAuth credentials with `category = "login"` and use `username`/`password` fields
- The provider uses `OP_SERVICE_ACCOUNT_TOKEN` env var for authentication

### Tailscale Kubernetes Operator

- OAuth client tags must own `tag:k8s` for ingresses to work (operator uses `tag:k8s` by default)
- ACL example: `"tag:k8s" = ["tag:k8s-operator", "tag:k8s-operator-do-nyc3-prod"]`
- If ingresses fail with "requested tags invalid or not permitted", check ACL tag ownership
- Scopes needed: `devices`, `auth_keys`, `routes`, `dns`

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
- Tailscale operator proxies require Tailscale 1.94.0+ for Linkerd compatibility (see `docs/tasks/tailscale-operator-1.94-linkerd.md`)

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

See `docs/guides/argocd-webhook-tailscale-funnel.md` for detailed setup guide.
