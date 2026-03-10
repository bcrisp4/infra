# CLAUDE.md

Guidance for Claude Code when working with this infrastructure monorepo.

## CRITICAL: NEVER COMMIT SECRETS OR STATE FILES

**NEVER commit:**
- `*.tfstate` / `*.tfstate.backup` / `*.tfvars` / `.terraform/`
- API keys, tokens, passwords, credentials
- `kubeconfig` / `talosconfig` / private keys (`*.pem`, `*.key`)
- `.env` files with real values

**Before EVERY commit:**
```bash
git diff --cached --name-only | grep -E '\.(tfstate|tfvars)$'
git diff --cached -S"SECRET" -S"TOKEN" -S"PASSWORD" -S"API_KEY"
```

## Commands

```bash
# Scaffold new cluster/app
./scripts/new-cluster.sh <cluster-name>
./scripts/new-app.sh <app-name> [cluster-name]
./scripts/bootstrap-argocd.sh <cluster-name>

# Terraform
cd terraform/<dir> && terraform init && terraform plan && terraform apply

# Helm
cd kubernetes/apps/<app> && helm dependency update
helm show values <chart>  # Get full chart values
helm template test kubernetes/apps/<app> -f kubernetes/clusters/<cluster>/apps/<app>/values.yaml  # Validate templates
```

## Architecture

Infrastructure monorepo for multi-cluster Kubernetes with GitOps. See [docs/reference/architecture.md](docs/reference/architecture.md).

**Terraform:** `bootstrap/` (TFC workspaces) | `global/` (cross-cluster) | `clusters/{cluster}/` (per-cluster)

**Kubernetes:** `apps/{app}/` (Helm charts) | `clusters/{cluster}/apps/{app}/` (config.yaml + values.yaml)
- Umbrella charts (prometheus, grafana, loki) wrap upstream charts via `Chart.yaml` dependencies
- Custom charts (miniflux, thanos) use pure templates with no dependencies

**Patterns:**
- Cluster naming: `{provider}-{region}-{env}` (e.g., `do-nyc3-prod`)
- Apps auto-deploy when `config.yaml` + `values.yaml` added to cluster
- ArgoCD uses the `name` field from `config.yaml` as the Helm release name (affects service DNS names)

## Current State

- Active cluster: `do-nyc3-prod` (DigitalOcean NYC3)
- Tailnet: `marlin-tet.ts.net`
- Object storage: Spaces buckets for Loki, Thanos

## Implementation Notes

- ExternalSecret `remoteRef` entries must include explicit `conversionStrategy: Default`, `decodingStrategy: None`, `metadataPolicy: None` to prevent ArgoCD sync drift from ESO webhook-injected defaults
- StatefulSet `volumeClaimTemplates` must include explicit `volumeMode: Filesystem`, `apiVersion: v1`, `kind: PersistentVolumeClaim` to prevent ArgoCD sync drift from Kubernetes-injected defaults
- StatefulSet `spec` must include explicit `updateStrategy: {type: RollingUpdate, rollingUpdate: {partition: 0}}` to prevent ArgoCD sync drift
- kube-prometheus-stack uses `kube-prometheus` (not `kube-prometheus-stack`) in resource names: `{release}-kube-prometheus-{component}`
- kube-prometheus-stack Thanos sidecar needs `thanosService.enabled: true` to expose gRPC port 10901; service name: `{release}-kube-prometheus-thanos-discovery`
- kube-prometheus-stack provides Kubernetes dashboards via `grafana.forceDeployDashboards: true` (needed because `grafana.enabled: false`); dashboards use `cluster` label and `job="kubelet"` -- do not reintroduce custom kubernetes-mixin dashboards
- When editing umbrella chart values (e.g. kube-prometheus-stack), verify YAML nesting with `helm template --show-only` after inserting new sibling keys -- indentation errors silently move config to the wrong parent
- `helm template --show-only` does not work for subchart templates in umbrella charts; grep the full `helm template` output instead
- Tailscale ProxyGroup ingress requires custom templates with `defaultBackend` (charts' built-in ingress uses `rules` which doesn't work)
- Do not use em dashes in generated content
- Keep configurations minimal
- Prefer explicit configuration over clever automation
- Templates use `_template` naming

## Grafana Datasources

| Name | UID | Type |
|------|-----|------|
| `prometheus-do-nyc3-prod` | `PC10E5D72BE95A5D2` | prometheus |
| `loki-do-nyc3-prod` | `PF99E8F4CDB5B6FB2` | loki |
| `thanos-do-nyc3-prod` | `P8C36202C1551FB13` | prometheus (Thanos) |

## Service URLs (do-nyc3-prod)

| Service | URL |
|---------|-----|
| Prometheus | `http://prometheus-kube-prometheus-prometheus.prometheus.svc.cluster.local:9090` |
| Alertmanager | `http://prometheus-kube-prometheus-alertmanager.prometheus.svc.cluster.local:9093` |
| Loki Gateway | `http://loki-gateway.loki.svc.cluster.local` |
| Thanos Query | `http://thanos-query.thanos.svc.cluster.local:10902` |
| Thanos Sidecar (gRPC) | `prometheus-kube-prometheus-thanos-discovery.prometheus.svc.cluster.local:10901` |

## Quick Reference

| Topic | Documentation |
|-------|---------------|
| Deploy new app | [docs/how-to/deploy-new-app.md](docs/how-to/deploy-new-app.md) |
| Update Terraform providers | [docs/how-to/update-terraform-providers.md](docs/how-to/update-terraform-providers.md) |
| ArgoCD webhooks | [docs/how-to/argocd-webhook-tailscale-funnel.md](docs/how-to/argocd-webhook-tailscale-funnel.md) |
| Tailscale ProxyGroup ingress | [docs/how-to/tailscale-proxygroup-ingress.md](docs/how-to/tailscale-proxygroup-ingress.md) |
| Query logs (LogQL) | [docs/how-to/query-logs.md](docs/how-to/query-logs.md) |

| Component | Reference |
|-----------|-----------|
| External Secrets / 1Password | [docs/reference/external-secrets.md](docs/reference/external-secrets.md) |
| Tailscale Operator | [docs/reference/tailscale-operator.md](docs/reference/tailscale-operator.md) |
| ArgoCD manifests | [docs/reference/argocd-manifests.md](docs/reference/argocd-manifests.md) |
| CloudNativePG backups | [docs/reference/cloudnative-pg-backup.md](docs/reference/cloudnative-pg-backup.md) |
| Grafana datasources | [docs/reference/grafana-datasources.md](docs/reference/grafana-datasources.md) |
| Logging architecture | [docs/reference/logging-architecture.md](docs/reference/logging-architecture.md) |
| Metrics architecture | [docs/reference/metrics-architecture.md](docs/reference/metrics-architecture.md) |
| Miniflux | [docs/reference/miniflux.md](docs/reference/miniflux.md) |

## Documentation

Full docs at [docs/README.md](docs/README.md) following [Divio system](https://documentation.divio.com/):
- `docs/tutorials/` - Learning-oriented guides
- `docs/how-to/` - Task-oriented recipes
- `docs/reference/` - Technical specifications
- `docs/troubleshooting/` - Debugging guides
